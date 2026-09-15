# -*- coding: utf-8 -*-
"""Levanta a evidencia de cada receita do Q2 ainda sem PEP cujo cliente tem varios
projetos, pra escolher o mais pertinente com criterio (nao no chute).

Evidencias por candidato:
  - valor identico ja lancado nesse PEP (Fee/WIP costumam ser recorrentes)
  - o PEP esta ativo no mes vizinho (continuidade)
  - o PEP ja recebeu esse MESMO TIPO de receita (Fee/WIP/Usage)
  - volume do PEP no cliente
Fontes: nova_base (todos os periodos) + razao do SAP (WBSElementExternal).
"""
import os, re, unicodedata, json
from collections import Counter, defaultdict
import openpyxl

os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}'}
PERS = ('2026-04', '2026-05', '2026-06')
RAZAO = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos\C - Razão P&L (SAP)'
         r'\C_Razao_PL_2026-01_a_2026-09_extraido_2026-09-04.xlsx')


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def raiz(p):
    return str(p).split('.')[0]


def pep_ok(v):
    v = str(v or '').strip().upper()
    return v if re.match(r'^BR\d{2}[A-Z]{2,4}\d+', v) else None


# ---------- nova_base inteira ----------
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,empresa,pep,pep_base,nome_cliente,nome_pessoa,'
                                    'receita,fonte,tipos',
                          'order': 'id', 'limit': '1000', 'offset': str(off)}, headers=H, timeout=120)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(str(b)[:200])
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000

hist = defaultdict(list)        # cliente -> linhas com pep
for x in rows:
    if x['pep'] and x['nome_cliente'] and (x['receita'] or 0) != 0:
        hist[npn(x['nome_cliente'])].append(x)

# ---------- razao SAP ----------
sap = defaultdict(list)         # cliente -> (periodo, pep, valor)
wb = openpyxl.load_workbook(RAZAO, read_only=True)
ws = wb[wb.sheetnames[0]]
for row in ws.iter_rows(min_row=2, values_only=True):
    pep = pep_ok(row[27])
    if not pep or not row[21]:
        continue
    try:
        if int(str(row[4]).strip()) != 2026:
            continue
        mm = int(str(row[5]).strip())
    except (TypeError, ValueError):
        continue
    sap[npn(row[21])].append((f'2026-{mm:02d}', pep, float(row[11] or 0)))
wb.close()
CLI_SAP = list(sap)


def sap_do_cliente(k):
    if k in sap:
        return sap[k]
    c = [x for x in CLI_SAP if x.startswith(k[:14]) or k.startswith(x[:14])]
    return sap[c[0]] if len(c) == 1 else []


sem = [x for x in rows if x['periodo'] in PERS and (x['receita'] or 0) != 0
       and x['fonte'] != 'Budget' and not x['pep']]
print(f'receitas do Q2 sem PEP: {len(sem)} | R$ {sum(x["receita"] for x in sem):,.0f}\n')

MESES = ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06']
saida = []
for cli, linhas in sorted(
        {npn(x['nome_cliente']): [y for y in sem if npn(y['nome_cliente']) == npn(x['nome_cliente'])]
         for x in sem}.items(),
        key=lambda t: -sum(y['receita'] for y in t[1])):
    h = hist.get(cli, [])
    s = sap_do_cliente(cli)
    peps = Counter(x['pep'] for x in h)
    print(f'=== {cli[:40]} — {len(linhas)} linhas, R$ {sum(x["receita"] for x in linhas):,.0f} ===')
    if not peps and not s:
        print('   sem historico em lugar nenhum\n')
        continue
    # perfil de cada PEP: meses ativos, tipos de receita, valores
    print('   PEPs do cliente na nossa base:')
    for p, n in peps.most_common(6):
        ll = [x for x in h if x['pep'] == p]
        mm = sorted({x['periodo'] for x in ll})
        tt = Counter(str(x['tipos']) for x in ll)
        vv = Counter(round(x['receita'], 2) for x in ll)
        print(f'      {p:22} {n:>3}ln | meses {mm[0]}..{mm[-1]} ({len(mm)}) | tipos {list(tt)[:2]} | valores top {[v for v,_ in vv.most_common(2)]}')
    if s:
        sp = Counter(p for _, p, _ in s)
        print(f'   PEPs no razao SAP: {[(p,n) for p,n in sp.most_common(5)]}')
    for x in linhas:
        v = round(x['receita'], 2)
        # evidencia 1: mesmo valor ja lancado em algum PEP
        iguais = Counter(y['pep'] for y in h if abs(y['receita'] - x['receita']) < 0.01)
        # evidencia 2: PEP ativo no mes vizinho com o mesmo tipo
        i = MESES.index(x['periodo'])
        viz = [MESES[j] for j in (i - 1, i + 1) if 0 <= j < len(MESES)]
        vizinhos = Counter(y['pep'] for y in h
                           if y['periodo'] in viz and str(y['tipos']) == str(x['tipos']))
        # evidencia 3: mesmo tipo em qualquer mes
        mesmo_tipo = Counter(y['pep'] for y in h if str(y['tipos']) == str(x['tipos']))
        print(f'   -> {x["periodo"]} {str(x["tipos"])[:12]:12} R$ {v:>10,.0f}')
        print(f'      valor igual em: {dict(iguais) or "-"} | vizinho+tipo: {dict(vizinhos) or "-"} | mesmo tipo: {dict(mesmo_tipo.most_common(3)) or "-"}')
        saida.append({'id': x['id'], 'cliente': x['nome_cliente'], 'periodo': x['periodo'],
                      'tipo': str(x['tipos']), 'valor': v, 'empresa': x['empresa'],
                      'valor_igual': dict(iguais), 'vizinho_tipo': dict(vizinhos),
                      'mesmo_tipo': dict(mesmo_tipo.most_common(5))})
    print()
json.dump(saida, open('_ambiguos_evidencia.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('salvo _ambiguos_evidencia.json com', len(saida), 'linhas')

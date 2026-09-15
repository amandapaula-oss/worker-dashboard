# -*- coding: utf-8 -*-
"""Busca o PEP das receitas do Q2 que ainda estao sem, direto no razao do SAP
(C_Razao_PL, coluna WBSElementExternal) — a fonte de origem, nao inferencia.

Casa por (cliente, competencia) e, quando ambiguo, tenta (cliente, competencia, valor).
Trava: o prefixo do PEP tem que bater com a empresa da linha.
Uso: python _pep_do_sap.py [--apply]
"""
import os, re, sys, unicodedata
from collections import Counter, defaultdict
import openpyxl

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')
MARCA = ' | PEP do razao SAP (WBSElementExternal)'
RAZAO = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos\C - Razão P&L (SAP)'
         r'\C_Razao_PL_2026-01_a_2026-09_extraido_2026-09-04.xlsx')
EMPRESA_PREFIXO = {'BR02 FCamara': 'BR02', 'BR09 NextGen': 'BR09', 'BR07 Hyper': 'BR07',
                   'BR05 SGA': 'BR05', 'BR08 Dojo': 'BR08', 'BR03 Omnik': 'BR03',
                   'BR04 Nação Digital': 'BR04'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def raiz(p):
    return str(p).split('.')[0]


def pep_ok(v):
    v = str(v or '').strip().upper()
    return v if re.match(r'^BR\d{2}[A-Z]{2,4}\d+', v) else None


# ---------- razao do SAP ----------
wb = openpyxl.load_workbook(RAZAO, read_only=True)
ws = wb[wb.sheetnames[0]]
por_cli_per, por_cli, por_val = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
n = 0
for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
    if row is None:
        continue
    ano, per, cli, wbs, val = row[4], row[5], row[21], row[27], row[11]
    pep = pep_ok(wbs)
    if not pep:
        continue
    try:
        if int(str(ano).strip()) != 2026:      # FiscalYear pode vir como texto
            continue
        mm = int(str(per).strip())
    except (TypeError, ValueError):
        continue
    p = f'2026-{mm:02d}'
    k = npn(cli) if cli else ''
    if k:
        por_cli[k][pep] += 1
        por_cli_per[(k, p)][pep] += 1
    if val is not None:
        try:
            por_val[(p, round(abs(float(val)), 2))][pep] += 1
        except (TypeError, ValueError):
            pass
    n += 1
wb.close()
print(f'razao SAP: {n} lancamentos de 2026 com WBS | {len(por_cli)} clientes | {len(por_cli_per)} chaves cliente-mes')

# ---------- linhas sem PEP ----------
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,empresa,pep,nome_cliente,nome_pessoa,receita,fonte,fonte_dados,tipos',
                          'periodo': f'in.({",".join(PERS)})', 'order': 'id', 'limit': '1000', 'offset': str(off)},
                  headers=H, timeout=120)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(str(b)[:200])
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
sem = [x for x in rows if (x['receita'] or 0) != 0 and x['fonte'] != 'Budget' and not x['pep']]
print(f'receitas do Q2 sem PEP: {len(sem)} | R$ {sum(x["receita"] for x in sem):,.0f}')


def escolhe(c):
    if not c:
        return None
    if len({raiz(p) for p in c}) == 1:
        com_fase = [p for p in c if '.' in p]
        return (Counter({p: c[p] for p in com_fase}) if com_fase else c).most_common(1)[0][0]
    return None


# nomes de cliente diferem entre a nova_base e o SAP ("Sada Transportes" x
# "SADA TRANSPORTES E ARMAZENAGENS LTDA") — casa por prefixo/contencao quando unico
CLIENTES_SAP = list(por_cli.keys())


def casa_nome(k):
    if k in por_cli:
        return k
    cand = [c for c in CLIENTES_SAP if c.startswith(k[:14]) or k.startswith(c[:14])]
    if len(cand) == 1:
        return cand[0]
    cand = [c for c in CLIENTES_SAP if k in c or c in k]
    return cand[0] if len(cand) == 1 else None


plano, stats = [], Counter()
for x in sem:
    k0 = npn(x['nome_cliente'])
    k = casa_nome(k0) or k0
    if k != k0:
        stats['(nome casado por aproximacao)'] += 1
    pep = escolhe(por_cli_per.get((k, x['periodo'])))
    origem = 'cliente+mes'
    if not pep:
        pep = escolhe(por_val.get((x['periodo'], round(abs(float(x['receita'])), 2))))
        origem = 'valor+mes'
    if not pep:
        pep = escolhe(por_cli.get(k))
        origem = 'cliente (qualquer mes)'
    if not pep:
        stats['nao achou no razao'] += 1
        continue
    pref = EMPRESA_PREFIXO.get(str(x.get('empresa')))
    if pref and not raiz(pep).startswith(pref):
        stats['BLOQUEADO (PEP de outra empresa)'] += 1
        continue
    plano.append((x, pep, origem))
    stats[f'achou por {origem}'] += 1

print('\n=== plano ===')
for k in sorted(stats):
    print(f'   {k:34} {stats[k]}')
if plano:
    print(f'   valor: R$ {sum(x["receita"] for x, _, _ in plano):,.0f}')
    for x, p, o in sorted(plano, key=lambda t: -t[0]['receita'])[:25]:
        print(f'      {x["periodo"]} {str(x["nome_cliente"])[:26]:26} {str(x["tipos"])[:11]:11} {x["receita"]:>10,.0f} -> {p:20} ({o})')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep, _ in plano:
    fd = (x.get('fonte_dados') or '')
    if MARCA not in fd:
        fd = (fd + MARCA)[:500]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': raiz(pep), 'fonte_dados': fd},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

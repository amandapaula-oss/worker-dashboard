# -*- coding: utf-8 -*-
"""Q1/26 (jan-mar), empresas BR02, BR07 e BR09: a receita passa a ser EXATAMENTE a da
peca "Receita Contábil 1Q26".

Regra da Amanda (16/09): "o que tem aqui Receita Contábil 1Q26 e' o correto falando de
receita... mesmo se estiver errado ou incoerente, esse e' o numero que ficou na
contabilidade entao e' o que vamos usar".

Quatro movimentos, por (projeto x mes):
  1. TROCA DE CODIGO  - o mesmo cliente, no mesmo mes, pelo mesmo valor, com outro codigo
                        de projeto dos dois lados -> renomeia o PEP das NOSSAS linhas
                        (preserva pessoa, horas, BU e o vinculo com o custo)
  2. REESCALA         - os dois lados tem o projeto, com valores diferentes -> as nossas
                        linhas sao ajustadas na proporcao ate bater
  3. ENTRA            - so a peca tem -> entra UMA linha, com cliente, projeto e centro de
                        lucro da peca; BU e apuracao herdadas da nossa base
  4. SAI              - so nos temos (ou a linha nao tem PEP) -> a linha sai; se ela
                        carrega horas ou custo, a receita e' zerada e a linha fica

Uso: python _alinha_q1_contabil.py [--apply]
"""
import datetime
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

import pandas as pd

APPLY = '--apply' in sys.argv
SO_ENTRADAS = '--so-entradas' in sys.argv   # refaz so o passo 3 (o resto ja gravou)
UPLOAD_ID = 'a92a8363-5778-5d1f-8a0a-b57c1f8f9f82'   # uuid5 fixo deste lote
APPLY = APPLY or SO_ENTRADAS
DIR = os.path.dirname(os.path.abspath(__file__))
SNAP = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
        r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
        r'\scratchpad\auditoria')
MESES = ['2026-01', '2026-02', '2026-03']
EMPRESAS = {'BR02': 'BR02 FCamara', 'BR07': 'BR07 Hyper', 'BR09': 'BR09 NextGen'}
STOP = {'SA', 'S', 'A', 'LTDA', 'EIRELI', 'ME', 'EPP', 'GRUPO', 'BANCO', 'COMERCIO', 'DO',
        'INDUSTRIA', 'DE', 'DA', 'E', 'DOS', 'DAS', 'SERVICOS', 'SERVICO', 'BRASIL', 'LTD',
        'CONSULTORIA', 'TECNOLOGIA', 'COM', 'SOCIEDADE', 'EMPREENDIMENTOS', 'PARTICIPACOES',
        'DISTRIBUIDORA', 'ATIVIDADES', 'INSTITUICAO', 'FORMACAO', 'PAGAMENTO', 'PAGAMENTOS'}
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx
import main

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}


def semac(v):
    return unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()


def toks(v):
    return {t for t in re.sub(r'[^A-Z0-9 ]', ' ', semac(v)).split() if t not in STOP and len(t) > 2}


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE', 'NAT') else p.replace('BRO', 'BR0').split('.')[0]


# ---------------- alvo: a peca contabil ----------------
ct = pd.read_csv(os.path.join(SNAP, 'fonte_contabilidade_1q26.csv'))
ct['emp'] = ct['cod_empresa'].astype(str).str.strip()
ct = ct[ct['emp'].isin(EMPRESAS)]
ct['r'] = ct['elemento_pep'].map(raiz)
alvo, info = defaultdict(float), {}
for _, r in ct.iterrows():
    for m in MESES:
        v = float(pd.to_numeric(r[m], errors='coerce') or 0)
        if abs(v) > 0.005:
            alvo[(r['r'], m)] += v
    info.setdefault(r['r'], {
        'emp': r['emp'], 'cliente': str(r['nome_cliente']).strip(),
        'cc': str(r['centro_lucro']).strip().replace('(', '').replace(')', '').strip(),
        'pep_cheio': str(r['elemento_pep']).strip(), 'projeto': str(r['nome_prj']).strip()})
print(f'peça contábil (BR02/07/09, Q1): {len({k[0] for k in alvo})} projetos | '
      f'R$ {sum(alvo.values()):,.2f}')

# ---------------- nossas linhas ----------------
df = main._get_nova_base().copy()
for c in ('receita', 'horas', 'custo_rateado'):
    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
d = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(MESES)
       & (~df['fonte'].astype(str).isin(['Budget', 'de para']))].copy()
d['emp'] = d['empresa'].astype(str).str.extract(r'(BR\d\d)')[0].fillna('?')
nossa = d[d['emp'].isin(EMPRESAS)].copy()
nossa['r'] = nossa['pep'].map(raiz)
print(f'nossa base (BR02/07/09, Q1):    {len(nossa)} linhas | R$ {nossa["receita"].sum():,.2f}')

# BU por cliente e apuracao por centro de lucro, tiradas da propria base
todo = df.copy()
todo['peso'] = todo['receita'].abs() + 1.0
bu_nome, bu_tok = {}, defaultdict(lambda: defaultdict(float))
for cli, g in todo[todo['vertical'].astype(str).str.startswith('BU ')].groupby(
        todo['nome_cliente'].astype(str)):
    bu = g.groupby('vertical')['peso'].sum().idxmax()
    bu_nome[semac(cli)] = bu
    for t in toks(cli):
        bu_tok[t][bu] += g['peso'].sum()
# cadastro de clientes (fonte oficial da BU, com as grafias do SAP em nome_base)
cad = {}
try:
    vmap, _ = main._clientes_lookup()
    cad = {semac(k): f'BU {v.strip()}' for k, v in vmap.items() if str(v).strip()}
except Exception as e:
    print(f'   !! cadastro de clientes indisponível ({e})')
print(f'cadastro de clientes: {len(cad)} grafias com BU')
w = todo[(todo['receita'] != 0)
         & todo['no_hierarquia'].astype(str).str.match(r'DC\d+', na=False)].copy()
w['dc'] = w['no_hierarquia'].astype(str).str.extract(r'^(DC\d+)')[0]
ap_dc = w.groupby('dc')['apuracao'].agg(lambda s: s.astype(str).value_counts().index[0]).to_dict()
alias = {semac(k): v for k, v in main.__dict__.get('_NOME_CLIENTE_ALIAS', {}).items()}
print(f'aliases de nome de cliente: {len(alias)}')


def resolve(cliente, projeto, pep, dc):
    """Nome de cliente, BU e apuracao de uma linha que vem da peca.

    Ordem: 1) revenda de licenca Azure SCE segue o Q2 (Encripta = BU Others/Ecossistema);
    2) cadastro de clientes (oficial); 3) historico do proprio cliente na base;
    4) token do nome; 5) default.
    """
    nome = cliente if cliente and cliente.lower() != 'nan' else ''
    if not nome or semac(nome).startswith('FCAMARA'):
        partes = [x for x in re.split(r'\s*[-_]\s*', projeto)
                  if semac(x).strip() not in ('', 'ALOCACAO', 'INATIVO', 'INATIVO ALOCACAO')]
        nome = (partes[0].strip() if partes else '') or nome or '(sem cliente na peça)'
    chave = alias.get(semac(nome), nome)
    if 'AZURE SCE' in semac(projeto):
        return nome, 'BU Others', 'Ecossistema', 'azure-sce'
    bu = cad.get(semac(chave)) or cad.get(semac(nome))
    origem = 'cadastro'
    if not bu:
        bu, origem = bu_nome.get(semac(chave)), 'base'
    if not bu:
        pontos = defaultdict(float)
        for t in toks(chave):
            for b, v in bu_tok[t].items():
                pontos[b] += v
        if pontos:
            bu, origem = max(pontos.items(), key=lambda z: z[1])[0], 'token'
    if not bu:
        bu, origem = ('BU Hyper' if pep.startswith('BR07') else 'BU Others'), 'default'
    return nome, bu, ap_dc.get(dc, 'Ecossistema'), origem


# ---------------- monta o plano ----------------
troca, escala, sai, entra = [], [], [], []
orf_nosso = {}
for (r, m), g in nossa.groupby(['r', 'periodo']):
    if r and (r, m) not in alvo:
        orf_nosso[(r, m)] = [x for _, x in g.iterrows()]
orf_peca = {(p, m): v for (p, m), v in alvo.items()
            if not len(nossa[(nossa['r'] == p) & (nossa['periodo'] == m)])}

# 1) troca de codigo: mesmo mes, mesma empresa, valor identico
usados = set()
for (rn, m), linhas in sorted(orf_nosso.items(),
                              key=lambda z: -abs(sum(x['receita'] for x in z[1]))):
    vn = sum(x['receita'] for x in linhas)
    emp_n = str(linhas[0]['emp'])
    cand = [(p, v) for (p, mm), v in orf_peca.items()
            if mm == m and (p, mm) not in usados and info[p]['emp'] == emp_n
            and abs(v - vn) <= max(0.05, abs(vn) * 0.001)]
    if cand:
        p = min(cand, key=lambda z: abs(z[1] - vn))[0]
        usados.add((p, m))
        troca.append((rn, p, m, vn, alvo[(p, m)], linhas))
for rn, p, m, vn, va, linhas in troca:
    del orf_nosso[(rn, m)]
for k in usados:
    del orf_peca[k]

# 2) o que sobra
for (rn, m), linhas in orf_nosso.items():
    sai += linhas
sai += [x for _, x in nossa[nossa['r'] == ''].iterrows()]
for (p, m), v in orf_peca.items():
    i = info[p]
    cod = (re.match(r'^(DC\d+)', i['cc']) or [None, ''])[1]
    nome, bu, ap, origem = resolve(i['cliente'], i['projeto'], p, cod)
    entra.append({'periodo': m, 'pep': i['pep_cheio'] or p, 'pep_base': p,
                  'empresa': EMPRESAS[i['emp']], 'nome_cliente': nome,
                  'no_hierarquia': i['cc'] or None, 'vertical': bu,
                  'apuracao_manual': ap, 'receita': round(v, 2),
                  'projeto': i['projeto'], '_origem_bu': origem, '_dc': cod or '?'})
for (r, m), g in nossa.groupby(['r', 'periodo']):
    if not r or (r, m) not in alvo:
        continue
    a, b = alvo[(r, m)], g['receita'].sum()
    if abs(a - b) >= 0.005:      # 0,005 e nao 0,01: senao sobra centavo por projeto
        escala.append((r, m, b, a, [x for _, x in g.iterrows()]))
for rn, p, m, vn, va, linhas in troca:
    if abs(va - vn) > 0.01:
        escala.append((p, m, vn, va, linhas))

v_sai = sum(x['receita'] for x in sai)
v_ent = sum(x['receita'] for x in entra)
v_esc = sum(a - b for _, _, b, a, _ in escala)
zera = [x for x in sai if x['horas'] != 0 or x['custo_rateado'] != 0]
print(f'\n=== plano ===')
print(f'   1. TROCA DE CÓDIGO   {len(troca):>4} projeto×mês | R$ {sum(z[3] for z in troca):>14,.2f} '
      f'({sum(len(z[5]) for z in troca)} linhas ficam, com o PEP da peça)')
print(f'   2. REESCALA          {len(escala):>4} projeto×mês | efeito R$ {v_esc:>+13,.2f}')
print(f'   3. ENTRA             {len(entra):>4} linhas     | R$ {v_ent:>14,.2f}')
print(f'   4. SAI               {len(sai):>4} linhas     | R$ {v_sai:>14,.2f} '
      f'({len(zera)} só zeram a receita e guardam {sum(x["horas"] for x in zera):,.0f}h)')
print(f'\n   efeito total: R$ {v_ent - v_sai + v_esc:+,.2f}')
print(f'   Q1 BR02/07/09: R$ {nossa["receita"].sum():,.2f} -> R$ {sum(alvo.values()):,.2f}')

print(f'\n   --- 1. trocas de código ---')
for rn, p, m, vn, va, linhas in sorted(troca, key=lambda z: -abs(z[3])):
    print(f'      {m} {rn:16} -> {p:16} {vn:>13,.2f} {len(linhas):>3} linha(s)  '
          f'{str(linhas[0]["nome_cliente"])[:28]}')
print(f'\n   --- 3. entradas (15 maiores) ---')
for x in sorted(entra, key=lambda z: -abs(z['receita']))[:15]:
    print(f'      {x["periodo"]} {x["pep_base"]:16} {str(x["nome_cliente"])[:26]:26} '
          f'{x["receita"]:>12,.2f}  {x["vertical"]:14} {x["apuracao_manual"]:13} '
          f'{x["_dc"]:6} bu:{x["_origem_bu"]}')
novos = sorted({x['nome_cliente'] for x in entra if x['_origem_bu'] == 'default'})
if novos:
    print(f'\n   !! {len(novos)} cliente(s) sem BU conhecida (foram pro default): {novos}')
print(f'\n   --- 4. saídas (15 maiores por PEP/cliente) ---')
sa = pd.DataFrame([{'pep': raiz(x['pep']) or '(sem PEP)', 'cliente': str(x['nome_cliente'])[:28],
                    'fonte': str(x['fonte'])[:22], 'v': x['receita'], 'h': x['horas']} for x in sai])
if len(sa):
    print(sa.groupby(['pep', 'cliente', 'fonte']).agg(v=('v', 'sum'), h=('h', 'sum'))
          .sort_values('v', ascending=False).head(15).round(2).to_string())
print(f'\n   --- 2. reescalas (12 maiores) ---')
for r, m, b, a, _ in sorted(escala, key=lambda z: -abs(z[3] - z[2]))[:12]:
    cli = info.get(r, {}).get('cliente', '')
    print(f'      {m} {r:16} {str(cli)[:26]:26} {b:>12,.2f} -> {a:>12,.2f} ({a-b:>+11,.2f})')

# efeito por BU e por mes
dep = defaultdict(float)
for _, x in nossa.iterrows():
    dep[x['vertical']] += x['receita']
for x in sai:
    dep[x['vertical']] -= x['receita']
for r, m, b, a, linhas in escala:
    f = (a / b) if b else 0
    for x in linhas:
        dep[x['vertical']] += x['receita'] * (f - 1)
for x in entra:
    dep[x['vertical']] += x['receita']
antes_bu = nossa.groupby('vertical')['receita'].sum()
print(f'\n   === efeito por BU (antes de o pipeline reclassificar) ===')
print(f'   {"BU":18} {"antes":>15} {"depois":>15} {"dif":>14}')
for bu in sorted(set(antes_bu.index) | set(dep)):
    print(f'   {str(bu):18} {antes_bu.get(bu, 0):>15,.2f} {dep.get(bu, 0):>15,.2f} '
          f'{dep.get(bu, 0) - antes_bu.get(bu, 0):>+14,.2f}')
print(f'\n   === por mês ===')
print(f'   {"mês":9} {"antes":>15} {"depois (=peça)":>17}')
for m in MESES:
    a0 = nossa[nossa['periodo'] == m]['receita'].sum()
    pc = sum(v for (p, mm), v in alvo.items() if mm == m)
    print(f'   {m}  {a0:>15,.2f} {pc:>17,.2f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

# ---------------- grava ----------------
ids = sorted({int(x['id']) for x in sai} | {int(x['id']) for _, _, _, _, l in escala for x in l}
             | {int(x['id']) for _, _, _, _, _, l in troca for x in l})
bk = []
if SO_ENTRADAS:
    print(f'--so-entradas: pulando trocas/reescalas/saidas (ja gravadas). '
          f'{len(entra)} entradas a inserir, R$ {v_ent:,.2f}')
    _grosso = [z for z in escala if abs(z[3] - z[2]) >= 1.0]
    assert not troca and not _grosso and not sai, (
        f'esperava so centavos pendentes, mas ha {len(troca)} trocas, {len(_grosso)} reescalas '
        f'acima de R$ 1 e {len(sai)} saidas — NAO rode --so-entradas por cima de outro estado')
    if escala:
        print(f'   (e {len(escala)} sobras de centavo, R$ {v_esc:+,.2f}, serao acertadas)')
for i in range(0, 0 if SO_ENTRADAS else len(ids), 100):
    ch = ','.join(map(str, ids[i:i + 100]))
    bk += httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({ch})'},
                    headers=H, timeout=180).json()
if not SO_ENTRADAS:
    json.dump(bk, open(os.path.join(DIR, '_backup_q1_contabil_antes.json'), 'w',
                       encoding='utf-8'), ensure_ascii=False)
    print(f'backup de {len(bk)} linhas: _backup_q1_contabil_antes.json')

for rn, p, m, vn, va, linhas in (troca if not SO_ENTRADAS else []):
    i = info[p]
    for x in linhas:
        z = httpx.patch(
            f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
            json={'pep': i['pep_cheio'] or p, 'pep_base': p,
                  'no_hierarquia': i['cc'] or x.get('no_hierarquia'),
                  'fonte_dados': (str(x.get('fonte_dados') or '')[:300] +
                                  f' | PEP {rn}->{p} (Receita Contábil 1Q26) 16/09')[:500]},
            headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
        assert z.status_code in (200, 204), z.text[:200]
print(f'   1. trocas de código: {sum(len(z[5]) for z in troca)} linhas')

nes = 0
for r, m, b, a, linhas in escala:
    # diferenca de centavo (sobra de arredondamento da propria reescala): acerta so a
    # maior linha do grupo, em vez de reescalar todas de novo e criar nova sobra
    if abs(a - b) < 1.0:
        x = max(linhas, key=lambda y: abs(float(y['receita'])))
        z = httpx.patch(
            f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
            json={'receita': round(float(x['receita']) + (a - b), 2)},
            headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
        assert z.status_code in (200, 204), z.text[:200]
        nes += 1
        continue
    f = a / b if b else 0
    for x in linhas:
        z = httpx.patch(
            f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
            json={'receita': round(float(x['receita']) * f, 2),
                  'fonte_dados': (str(x.get('fonte_dados') or '')[:290] +
                                  f' | Q1 = Receita Contábil 1Q26 (era {x["receita"]:.2f}) 16/09')[:500]},
            headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
        assert z.status_code in (200, 204), z.text[:200]
        nes += 1
print(f'   2. reescaladas: {nes} linhas')

ids_zera = {int(x['id']) for x in zera} if not SO_ENTRADAS else set()
ids_del = ([int(x['id']) for x in sai if int(x['id']) not in ids_zera]
           if not SO_ENTRADAS else [])
zera = zera if not SO_ENTRADAS else []
for x in zera:
    z = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
                    json={'receita': 0, 'fonte_dados': (str(x.get('fonte_dados') or '')[:270] +
                          f' | receita zerada: fora da Receita Contábil 1Q26 (era {x["receita"]:.2f}) 16/09')[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert z.status_code in (200, 204), z.text[:200]
for i in range(0, len(ids_del), 100):
    ch = ','.join(map(str, ids_del[i:i + 100]))
    z = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({ch})'}, headers=H, timeout=180)
    assert z.status_code in (200, 204), z.text[:200]
print(f'   4. saídas: {len(ids_del)} apagadas, {len(ids_zera)} zeradas')

cols = set(httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'limit': '1'},
                     headers=H, timeout=60).json()[0]) - {'id', 'cpf', 'apuracao'}
novas = []
for x in entra:
    linha = {c: None for c in cols}
    linha.update({k: v for k, v in x.items() if k in cols and not k.startswith('_')})
    linha.update({'fonte': 'Receita Contábil 1Q26', 'custo_rateado': 0, 'horas': 0,
                  'upload_id': UPLOAD_ID,   # upload_id e uploaded_at sao NOT NULL na tabela
                  'uploaded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'fonte_dados': f'Receita Contábil 1Q26 (peça da contabilidade) | '
                                 f'{x["projeto"][:60]} | inserido 16/09'})
    novas.append(linha)
ids_new = []
for i in range(0, len(novas), 500):
    z = httpx.post(f'{url}/rest/v1/nova_base', json=novas[i:i + 500],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert z.status_code in (200, 201), f'{z.status_code} {z.text[:300]}'
    ids_new += [y['id'] for y in z.json()]
json.dump(ids_new, open(os.path.join(DIR, '_backup_insert_q1_contabil_ids.json'), 'w'))
print(f'   3. entradas: {len(ids_new)} linhas inseridas')
print('\npronto. rode _run_sync_calculada.py em seguida.')

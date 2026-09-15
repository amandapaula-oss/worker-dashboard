# -*- coding: utf-8 -*-
"""Preenche as colunas que a carga do Q2 deixou vazias, usando dados que JA existiam
nas fontes e eu tinha ignorado:

  no_hierarquia     <- 'Profit Center' da aba 1 (Dedicated Teams -> DC002 Dedicated Teams...)
                       alimenta o filtro do dash e a apuracao NG/Eco
  agrupador         <- 'Estrutura' da aba 1 (Vertical/E-commerce/Consulting/Sales Boost)
                       e 'agrupador_fpa' no arquivo de Despesas Gerais
  tipo_contrato     <- 'Contrato' (nao faturaveis) e a folha CLTs/PJs por nome
  billable_category <- 'Billability' (nao faturaveis) e a folha
  area              <- 'Função'/'Centro de Custo' (nao faturaveis)

Casa as linhas do banco com a aba 1 por (periodo, pessoa, valor).
Uso: python _enriquece_colunas_q2.py [--apply]
"""
import os, sys, unicodedata
from collections import Counter, defaultdict
from datetime import datetime
import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')
BU = r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\NewDashboard\Apuração de metas 2 Q\Base Unificada v3.xlsx'
MO = r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais'
PL = '2026 dados/FCamara - P&L Gerencial - jun26 v2.xlsx'

# Profit Center (nome curto) -> no_hierarquia canonico da base
NH = {
    'DEDICATED TEAMS': 'DC002 Dedicated Teams', 'SQUADS': 'DC001 Squads',
    'OPEN-X': 'DC005 Open-X', 'E-COMMERCE': 'DC004 E-commerce',
    'FC CONSULT. NEW REV': 'DC029 FC Consult. New Rev',
    'FC CONSULT. B. SALES': 'DC040 FC Consult. B. Sales',
    'BUSINESS UNIT': 'DC037 Business Unit',
    'HYPERAUTOMATION': 'DC008 Hyperautomation',
}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def s(v):
    v = '' if v is None else str(v).strip()
    return None if v in ('', 'nan', 'NaN', 'None', '0') else v


# ---------- aba 1: no_hierarquia + agrupador, por (periodo, pessoa, valor) ----------
d = pd.read_excel(BU, sheet_name=0)
d.columns = [str(c).strip() for c in d.columns]
d['per'] = pd.to_datetime(d['Competencia'], errors='coerce').dt.strftime('%Y-%m')
d = d[d['per'].isin(PERS)]
mapa = {}
for _, r in d.iterrows():
    nome = npn(s(r.get('Nome Unificado')) or s(r.get('Nome (Receita)')) or '')
    pc = npn(r.get('Profit Center'))
    info = {'no_hierarquia': NH.get(pc), 'agrupador': s(r.get('Estrutura'))}
    if not any(info.values()):
        continue
    for col in ('Receita (Valor Liquido)', 'Custo Alocado'):
        v = pd.to_numeric(r.get(col), errors='coerce')
        if pd.notna(v) and float(v) != 0:
            mapa[(r['per'], nome, round(abs(float(v)), 2))] = info
print(f'aba 1: {len(mapa)} chaves (periodo, pessoa, valor)')

# ---------- nao faturaveis: contrato / billability / funcao ----------
pess = {}
p1 = os.path.join(MO, 'Pessoas nao faturaveis por vertical - Q2Y26.xlsx')
for bu in ('Finance', 'Retail', 'Logistics', 'Health', 'Multisector'):
    df = pd.read_excel(p1, sheet_name=bu)
    df.columns = [str(c).strip() for c in df.columns]
    for _, r in df.iterrows():
        nm = npn(r.get('Nome'))
        if not nm:
            continue
        pess[nm] = {'tipo_contrato': s(r.get('Contrato')),
                    'billable_category': s(r.get('Billability')),
                    'area': s(r.get('Função')) or s(r.get('Centro de Custo'))}
print(f'nao faturaveis: {len(pess)} pessoas')

# ---------- folha: contrato / billability por nome ----------
cl = pd.read_excel(PL, sheet_name='CLTs', header=None)
for r in range(1, len(cl)):
    c = cl.iat[r, 25]
    if isinstance(c, (pd.Timestamp, datetime)) and c.year == 2026:
        nm = npn(cl.iat[r, 1])
        if nm and nm not in pess:
            pess[nm] = {'tipo_contrato': 'CLT', 'billable_category': s(cl.iat[r, 26]),
                        'area': s(cl.iat[r, 27])}
pj = pd.read_excel(PL, sheet_name='PJs', header=None)
for r in range(1, len(pj)):
    c = pj.iat[r, 7]
    if isinstance(c, (pd.Timestamp, datetime)) and c.year == 2026:
        nm = npn(pj.iat[r, 1])
        if nm and nm not in pess:
            pess[nm] = {'tipo_contrato': 'PJ', 'billable_category': s(pj.iat[r, 8]),
                        'area': s(pj.iat[r, 9])}
print(f'folha CLT+PJ: {len(pess)} pessoas no total')

# ---------- despesas gerais: agrupador_fpa ----------
dgmap = {}
dg = pd.read_excel(os.path.join(MO, 'Despesas Gerais Verticais - 2Q26.xlsx'), sheet_name='Planilha1')
dg.columns = [str(c).strip() for c in dg.columns]
dg['m'] = pd.to_numeric(dg['FiscalPeriod'], errors='coerce')
dg['val'] = pd.to_numeric(dg['AmountInCompanyCodeCurrency'], errors='coerce').fillna(0)
for (v, m), g in dg[dg['m'].isin([4, 5, 6])].groupby([dg['vertical'].astype(str).str.strip(), 'm']):
    top = g.groupby('agrupador_fpa')['val'].sum().abs().sort_values(ascending=False)
    if len(top):
        dgmap[('BU ' + v, f'2026-0{int(m)}')] = top.index[0]
print(f'despesas gerais: {len(dgmap)} chaves (vertical, mes)')

# ---------- linhas do banco ----------
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,fonte,periodo,nome_pessoa,nome_cliente,vertical,receita,custo_rateado,'
                                    'no_hierarquia,agrupador,tipo_contrato,billable_category,area',
                          'periodo': f'in.({",".join(PERS)})', 'order': 'id', 'limit': '1000', 'offset': str(off)},
                  headers=H, timeout=90)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(str(b)[:200])
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
alvo = [x for x in rows if x['fonte'] in ('racionais', 'Base Unificada Q2', 'Metas Custos Q2')]
print(f'linhas do Q2 a enriquecer: {len(alvo)}')

plano, stats = defaultdict(dict), Counter()
for x in alvo:
    novo = {}
    nm = npn(x.get('nome_pessoa')) if x.get('nome_pessoa') else ''
    v = round(abs(float(x['receita'] or x['custo_rateado'] or 0)), 2)
    info = mapa.get((x['periodo'], nm, v))
    if info:
        if info.get('no_hierarquia') and not x.get('no_hierarquia'):
            novo['no_hierarquia'] = info['no_hierarquia']; stats['no_hierarquia'] += 1
        if info.get('agrupador') and not x.get('agrupador'):
            novo['agrupador'] = info['agrupador']; stats['agrupador (Estrutura)'] += 1
    pi = pess.get(nm) if nm else None
    if pi:
        for col in ('tipo_contrato', 'billable_category', 'area'):
            if pi.get(col) and not x.get(col):
                novo[col] = pi[col]; stats[col] += 1
    if x['fonte'] == 'Metas Custos Q2' and not x.get('agrupador'):
        ag = dgmap.get((str(x.get('vertical')), x['periodo']))
        if ag:
            novo['agrupador'] = ag; stats['agrupador (despesas FPA)'] += 1
    if novo:
        plano[x['id']] = novo

print('\n=== o que sera preenchido ===')
for k in sorted(stats):
    print(f'   {k:28} {stats[k]} linhas')
print(f'   linhas tocadas: {len(plano)}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

# agrupa por payload identico p/ dar menos requests
por_payload = defaultdict(list)
for i, novo in plano.items():
    por_payload[tuple(sorted(novo.items()))].append(str(i))
feitas = 0
for pay, lote in por_payload.items():
    payload = dict(pay)
    for i in range(0, len(lote), 100):
        chunk = lote[i:i + 100]
        r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                        json=payload, headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
        assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
        feitas += len(chunk)
print(f'\natualizadas: {feitas} linhas')

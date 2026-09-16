# -*- coding: utf-8 -*-
"""Casas Bahia no Q2: receita igual a do P&L (decisao da Amanda, 16/09).

A Base Unificada do Yuri traz a receita do Grupo Casas Bahia E um lancamento
'Ajuste RJ (zerar Q2)' negativo que a anula; o P&L da Paola conta a receita.
Removendo o estorno, o que sobra tem que bater com o P&L ao centavo:
  abr 2.309.261,32 | mai 2.493.946,43 | jun 2.526.917,16  (linha do cliente na aba-fonte)
So grava se bater. Backup das linhas removidas antes de apagar.
Uso: python _casas_bahia_igual_pnl.py [--apply]
"""
import json, os, sys
import pandas as pd

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PNL = {'2026-04': 2309261.32, '2026-05': 2493946.43, '2026-06': 2526917.16}

rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,fonte,fonte_dados,nome_cliente,nome_pessoa,tipos,receita,custo_rateado',
                          'nome_cliente': 'ilike.*CASAS BAHIA*',
                          'periodo': 'in.(2026-04,2026-05,2026-06)',
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
d = pd.DataFrame(rows)
d['receita'] = pd.to_numeric(d['receita'], errors='coerce').fillna(0)
d = d[d['fonte'] != 'Budget']
print(f'Casas Bahia no Q2 (sem Budget): {len(d)} linhas | receita R$ {d["receita"].sum():,.2f}')

# o estorno: receita NEGATIVA na fonte da planilha do Yuri
estorno = d[(d['fonte'] == 'racionais') & (d['receita'] < 0)]
print(f'\nestorno "Ajuste RJ (zerar Q2)": {len(estorno)} linhas | R$ {estorno["receita"].sum():,.2f}')
print('  por mes:', {k: round(v, 2) for k, v in estorno.groupby('periodo')['receita'].sum().items()})

resto = d[~d['id'].isin(estorno['id'])]
print('\n=== receita que FICA x P&L ===')
ok = True
for per in sorted(PNL):
    v = resto.loc[(resto['periodo'] == per) & (resto['receita'] != 0), 'receita'].sum()
    dif = v - PNL[per]
    flag = 'bate' if abs(dif) < 1 else 'NAO BATE'
    if abs(dif) >= 1:
        ok = False
    print(f'   {per}: fica R$ {v:>13,.2f} | P&L R$ {PNL[per]:>13,.2f} | dif {dif:>8,.2f}  {flag}')
tot_fica = resto.loc[resto['receita'] != 0, 'receita'].sum()
print(f'   Q2   : fica R$ {tot_fica:>13,.2f} | P&L R$ {sum(PNL.values()):>13,.2f}')

if not ok:
    raise SystemExit('\n!! nao bate com o P&L — nao gravo')
if not APPLY:
    print('\n--- DRY RUN: nada removido. Rode com --apply. ---')
    raise SystemExit(0)

ids_del = [int(x) for x in estorno['id']]
json.dump(rows, open(os.path.join(DIR, '_backup_casas_bahia_q2_antes.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
apagadas = 0
for i in range(0, len(ids_del), 100):
    chunk = [str(x) for x in ids_del[i:i + 100]]
    r = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                     headers=H, timeout=120)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    apagadas += len(chunk)
print(f'\nestorno removido: {apagadas} linhas (backup: _backup_casas_bahia_q2_antes.json)')

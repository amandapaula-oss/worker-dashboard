# -*- coding: utf-8 -*-
"""Odontoprev: os PEPs BR07 saem da BU Health e vao pra BU Hyper (decisao Amanda/Paola 18/09).
O Licensing Hyper (BR02LIC00005) ja' esta' em BU Hyper."""
import json, os, sys
import pandas as pd
APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
PEPS = ('BR07CLP00022', 'BR07CLP00087', 'BR07CLP00151')
os.environ.setdefault('SECRET_KEY', 'dbg'); os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx, main
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
z = df[df['nome_cliente'].astype(str).str.upper().str.contains('ODONTOPREV', na=False)].copy()
z['r'] = z['pep'].astype(str).str.upper().str.replace('BRO', 'BR0').str.split('.').str[0]
alvo = z[z['r'].isin(PEPS)]
print('Odontoprev nos PEPs BR07, TODOS os periodos:')
print(alvo.groupby([alvo['periodo'].astype(str), 'vertical'])['receita'].agg(['size','sum']).round(2).to_string())
q2 = alvo[alvo['periodo'].astype(str).isin(['2026-04','2026-05','2026-06'])
          & (alvo['vertical'].astype(str) != 'BU Hyper')]
q1 = alvo[alvo['periodo'].astype(str).isin(['2026-01','2026-02','2026-03'])
          & (alvo['vertical'].astype(str) != 'BU Hyper')]
print(f'\nQ2 a mover: {len(q2)} linhas | R$ {q2["receita"].sum():,.2f}')
print(f'Q1 na mesma situacao: {len(q1)} linhas | R$ {q1["receita"].sum():,.2f}  (NAO mexo sem ordem)')
if not APPLY:
    print('\n--- DRY RUN ---'); raise SystemExit(0)
ids = [int(x) for x in q2['id'].dropna()]
bk = []
for i in range(0, len(ids), 100):
    ch = ','.join(map(str, ids[i:i+100]))
    bk += httpx.get(f'{url}/rest/v1/nova_base', params={'select':'*','id':f'in.({ch})'},
                    headers=H, timeout=120).json()
json.dump(bk, open(os.path.join(DIR,'_backup_odonto_hyper.json'),'w',encoding='utf-8'), ensure_ascii=False)
print(f'backup de {len(bk)} linhas: _backup_odonto_hyper.json')
for x in bk:
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'vertical': 'BU Hyper',
                          'fonte_dados': (str(x.get('fonte_dados') or '')[:300] +
                                          ' | BU Health->Hyper: PEP BR07 da Odontoprev (Amanda/Paola 18/09)')[:500]},
                    headers={**H, 'Prefer':'return=minimal'}, timeout=60)
    assert r.status_code in (200,204), r.text[:200]
print(f'movidas {len(bk)} linhas para BU Hyper')

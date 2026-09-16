# -*- coding: utf-8 -*-
"""Remove a duplicidade que as cargas de hoje criaram: os profit centers DC029
(FC Consult. New Rev = aba Play) e DC040 (FC Consult. B. Sales = aba Sales Boost)
JA vinham dentro da fonte 'racionais' no Q2. Quando as abas subiram como fonte
propria, o mesmo dinheiro passou a ser contado duas vezes.

Sai o lado do RACIONAL, porque as 4 cargas novas batem ao centavo com o P&L
(12 conferencias, diferenca zero) e o racional traz o valor agregado de outra forma
(ex.: o Yuri lanca o trimestre inteiro do Adcos em abril).

FICA a UNIMED NACIONAL (R$ 30.208,05, abr): a aba Play esta zerada em abril para ela,
entao nao e duplicidade e sim divergencia entre as fontes — decisao a parte.
Uso: python _remove_dup_dc029_dc040.py [--apply]
"""
import json
import os
import sys

import pandas as pd

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx
import main

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
MANTER = 'UNIMED NACIONAL'          # nao e duplicidade

df = main._get_nova_base()
d = df[(df['periodo'].astype(str) >= '2026-04') & (df['periodo'].astype(str) <= '2026-06')].copy()
d['receita'] = pd.to_numeric(d['receita'], errors='coerce').fillna(0)
nh = d['no_hierarquia'].fillna('').astype(str)
alvo = d[(d['receita'] != 0) & (d['fonte'].astype(str) == 'racionais')
         & nh.str.startswith(('DC029', 'DC040'))
         & (~d['nome_cliente'].astype(str).str.upper().str.contains(MANTER, na=False))]
ids = [int(x) for x in alvo['id'].dropna()]
print(f'linhas a remover: {len(ids)} | R$ {alvo["receita"].sum():,.2f}')
for _, x in alvo.iterrows():
    print(f'   {x["periodo"]} {str(x["nome_cliente"])[:28]:28} {str(x["no_hierarquia"])[:26]:26} '
          f'R$ {x["receita"]:>11,.2f}')
mant = d[(d['receita'] != 0) & (d['fonte'].astype(str) == 'racionais')
         & nh.str.startswith(('DC029', 'DC040'))
         & (d['nome_cliente'].astype(str).str.upper().str.contains(MANTER, na=False))]
print(f'\nmantidas (divergencia, nao duplicidade): {len(mant)} | R$ {mant["receita"].sum():,.2f}')

if not APPLY:
    print('\n--- DRY RUN: nada removido. Rode com --apply. ---')
    raise SystemExit(0)

# backup antes de apagar
linhas = []
for i in range(0, len(ids), 100):
    chunk = [str(x) for x in ids[i:i + 100]]
    r = httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({",".join(chunk)})'},
                  headers=H, timeout=120)
    linhas += r.json()
json.dump(linhas, open(os.path.join(DIR, '_backup_del_dup_dc029_dc040.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'backup: _backup_del_dup_dc029_dc040.json ({len(linhas)} linhas)')

apagadas = 0
for i in range(0, len(ids), 100):
    chunk = [str(x) for x in ids[i:i + 100]]
    r = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                     headers=H, timeout=120)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    apagadas += len(chunk)
print(f'removidas: {apagadas} linhas')

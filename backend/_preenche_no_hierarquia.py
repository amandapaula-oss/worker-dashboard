# -*- coding: utf-8 -*-
"""Preenche no_hierarquia (DCxxx Nome) das linhas do Q2 usando o profit_center que o
cadastro mestre do SAP traz para cada PEP — agora que 99,8% das linhas tem projeto.

O no_hierarquia alimenta o filtro de hierarquia do dash e a apuracao NG/Eco automatica.
O nome que acompanha o codigo vem do que ja existe na propria base (ex.: DC002 -> 'DC002
Dedicated Teams'), para nao inventar rotulo.
Uso: python _preenche_no_hierarquia.py [--apply]
"""
import os, sys, re
from collections import Counter, defaultdict
import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')


def raiz(p):
    return str(p or '').split('.')[0].strip().upper()


# PEP -> profit center, do cadastro mestre
m = pd.read_excel('pep_master_sap.xlsx', sheet_name='PEPs')
m.columns = [str(c).strip() for c in m.columns]
pc_por_pep, pc_por_raiz = {}, {}
for _, r in m.iterrows():
    pc = str(r['profit_center']).strip().upper()
    if not re.match(r'^DC\d+$', pc):
        continue
    p = str(r['pep']).strip().upper()
    pc_por_pep[p] = pc
    pc_por_raiz.setdefault(raiz(p), pc)
print(f'cadastro mestre: {len(pc_por_pep)} PEPs com profit center')

# rotulo canonico de cada DC, a partir do que a propria base ja usa
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,pep,pep_base,no_hierarquia,fonte,receita,custo_rateado',
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
rotulo = {}
for x in rows:
    nh = str(x.get('no_hierarquia') or '').strip()
    mm = re.match(r'^(DC\d+)\b\s*(.*)$', nh)
    if mm and mm.group(2):
        rotulo.setdefault(mm.group(1), nh)
print(f'rotulos ja usados na base: {len(rotulo)} (ex.: {list(rotulo.items())[:3]})')

alvo = [x for x in rows if x['periodo'] in PERS and x['fonte'] != 'Budget'
        and not str(x.get('no_hierarquia') or '').strip()]
print(f'linhas do Q2 sem no_hierarquia: {len(alvo)}')

plano, stats = [], Counter()
for x in alvo:
    p = str(x.get('pep') or '').strip().upper()
    pc = pc_por_pep.get(p) or pc_por_raiz.get(raiz(p)) or (pc_por_raiz.get(raiz(x.get('pep_base'))) if x.get('pep_base') else None)
    if not pc:
        stats['sem PEP no cadastro'] += 1
        continue
    nh = rotulo.get(pc, pc)          # usa o rotulo da base; se nao houver, so o codigo
    plano.append((x['id'], nh))
    stats[nh] += 1

print('\n=== a preencher ===')
for k, v in Counter(nh for _, nh in plano).most_common(12):
    print(f'   {k:30} {v}')
print(f'   sem PEP no cadastro: {stats["sem PEP no cadastro"]}')
print(f'   total: {len(plano)} linhas')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

por_valor = defaultdict(list)
for i, nh in plano:
    por_valor[nh].append(str(i))
feitas = 0
for nh, lote in por_valor.items():
    for i in range(0, len(lote), 100):
        chunk = lote[i:i + 100]
        r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                        json={'no_hierarquia': nh}, headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
        assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
        feitas += len(chunk)
print(f'\natualizadas: {feitas} linhas')

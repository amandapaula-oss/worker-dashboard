# -*- coding: utf-8 -*-
"""Preenche a empresa das linhas do Q2 que ficaram sem: o prefixo do PEP ja diz
a empresa (BR02... = FCamara, BR09... = NextGen, etc).
Para as despesas gerais (que nao tem PEP), usa o CompanyCode do arquivo de origem.
Uso: python _preenche_empresa_por_pep.py [--apply]
"""
import os, sys
from collections import Counter, defaultdict
import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')
EMPRESA = {
    'BR02': 'BR02 FCamara', 'BR03': 'BR03 Omnik', 'BR04': 'BR04 Nação Digital',
    'BR05': 'BR05 SGA', 'BR07': 'BR07 Hyper', 'BR08': 'BR08 Dojo', 'BR09': 'BR09 NextGen',
}

rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,fonte,periodo,empresa,pep,pep_base,vertical,nome_cliente,nome_pessoa',
                          'periodo': f'in.({",".join(PERS)})', 'order': 'id', 'limit': '1000', 'offset': str(off)},
                  headers=H, timeout=90)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(f'erro: {str(b)[:200]}')
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
sem = [x for x in rows if not (x.get('empresa') or '').strip()]
print(f'linhas sem empresa no Q2: {len(sem)}')

# empresa por vertical, a partir do arquivo de Despesas Gerais Verticais (tem CompanyCode)
emp_por_vertical = {}
try:
    dg = pd.read_excel(
        r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais\Despesas Gerais Verticais - 2Q26.xlsx',
        sheet_name='Planilha1')
    dg.columns = [str(c).strip() for c in dg.columns]
    for v, g in dg.groupby(dg['vertical'].astype(str).str.strip()):
        cc = g['CompanyCode'].astype(str).str.strip().mode()
        if len(cc):
            emp_por_vertical['BU ' + v] = EMPRESA.get(cc.iat[0], None)
    print('empresa por vertical (arquivo de despesas):', emp_por_vertical)
except Exception as e:
    print('nao consegui ler o arquivo de despesas:', str(e)[:120])

# empresa por PESSOA, direto da folha do P&L (CLTs col 24 / PJs col 6)
import unicodedata
from datetime import datetime


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


emp_por_pessoa = {}
PL = '2026 dados/FCamara - P&L Gerencial - jun26 v2.xlsx'
cl = pd.read_excel(PL, sheet_name='CLTs', header=None)
for r in range(1, len(cl)):
    c = cl.iat[r, 25]
    if isinstance(c, (pd.Timestamp, datetime)) and c.year == 2026:
        e = EMPRESA.get(str(cl.iat[r, 24]).strip())
        if e:
            emp_por_pessoa.setdefault(npn(cl.iat[r, 1]), e)
pj = pd.read_excel(PL, sheet_name='PJs', header=None)
for r in range(1, len(pj)):
    c = pj.iat[r, 7]
    if isinstance(c, (pd.Timestamp, datetime)) and c.year == 2026:
        e = EMPRESA.get(str(pj.iat[r, 6]).strip())
        if e:
            emp_por_pessoa.setdefault(npn(pj.iat[r, 1]), e)
print(f'empresa por pessoa (folha CLT+PJ): {len(emp_por_pessoa)} nomes')

plano, stats = defaultdict(list), Counter()
for x in sem:
    p = (x.get('pep') or x.get('pep_base') or '').strip().upper()
    emp = EMPRESA.get(p[:4]) if p else None
    if emp:
        stats[f'por PEP {p[:4]}'] += 1
    elif x.get('nome_pessoa') and emp_por_pessoa.get(npn(x['nome_pessoa'])):
        emp = emp_por_pessoa[npn(x['nome_pessoa'])]
        stats['por pessoa (folha)'] += 1
    else:
        emp = emp_por_vertical.get(str(x.get('vertical')))
        if emp:
            stats['por vertical (CompanyCode)'] += 1
    if not emp:
        stats['sem como deduzir'] += 1
        continue
    plano[emp].append(str(x['id']))

print('\n=== plano ===')
for k in sorted(stats):
    print(f'   {k:28} {stats[k]}')
print(f'   total a atualizar          {sum(len(v) for v in plano.values())}')
for emp, l in sorted(plano.items()):
    print(f'      -> {emp:22} {len(l)} linhas')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for emp, lote in plano.items():
    for i in range(0, len(lote), 100):
        chunk = lote[i:i + 100]
        r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                        json={'empresa': emp}, headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
        assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
        feitas += len(chunk)
print(f'\natualizadas: {feitas} linhas')

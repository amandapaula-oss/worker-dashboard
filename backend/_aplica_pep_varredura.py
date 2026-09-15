# -*- coding: utf-8 -*-
"""Aplica os PEPs confirmados pela varredura das extracoes (razao do SAP + ciclo de caixa),
onde valor + mes + cliente casam. Cada atribuicao carrega a evidencia no fonte_dados.

NAO mexe na empresa das linhas: o BR02 veio da planilha do Yuri, e a divergencia com a
empresa do PEP (BR04/BR05/BR07) e um achado pra conferir com ele, nao pra eu corrigir.
Uso: python _aplica_pep_varredura.py [--apply]
"""
import os, sys, unicodedata
from collections import Counter

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')

# (trecho do cliente, valor aproximado, PEP, evidencia)
REGRAS = [
    ('TRANSUNION', 141936, 'BR02CLP000122.1.1', 'razao SAP: R$ 141.936,45 em abr/26'),
    ('TRANSUNION', 58146, 'BR02CLP000150.1.1', 'razao SAP: R$ 58.146,46/mes'),
    ('OURINVEST', 57632, 'BR04CLP00053.1.1', 'razao SAP: R$ 57.632,42/mes nos 3 meses (+Q1 igual)'),
    ('OURINVEST', 64206, 'BR07CLP00024.1.2', 'razao SAP: R$ 64.206,66/mes nos 3 meses'),
    ('GVC', 41700, 'BR05CLP000206.1.1', 'razao SAP: R$ 41.699,43/mes, unico PEP do cliente (+Q1 igual)'),
    ('STIX', 18739, 'BR05CLP000402.1.1', 'razao SAP: R$ 18.739,02/mes, unico projeto do cliente (+Q1 igual)'),
    ('KLABIN', 7706, 'BR02CLP000923.1.1', 'razao SAP: R$ 7.706,31 em jun/26 (projeto aberto em 01/06)'),
    ('MERCADO LIVRE', 35485, 'BR07CLP00220.1.1', 'razao SAP: R$ 35.485,07 em jun/26 (ambiguo com BR07CLP00221; razao tem WBS do lancamento)'),
]


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,empresa,pep,nome_cliente,receita,fonte,fonte_dados,tipos',
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
print(f'receitas do Q2 sem PEP: {len(sem)} | R$ {sum(x["receita"] for x in sem):,.0f}\n')

plano, usados = [], set()
for cli, valor, pep, ev in REGRAS:
    for x in sem:
        if x['id'] in usados:
            continue
        if cli in npn(x['nome_cliente']) and abs(float(x['receita']) - valor) <= max(2.0, valor * 0.001):
            plano.append((x, pep, ev)); usados.add(x['id'])

print('=== a gravar ===')
for x, p, ev in sorted(plano, key=lambda t: -t[0]['receita']):
    alerta = ''
    emp = str(x.get('empresa') or '')[:4]
    if emp and not p.startswith(emp):
        alerta = f'  << empresa da linha {emp} x PEP {p[:4]}'
    print(f'   {x["periodo"]} {str(x["nome_cliente"])[:24]:24} {x["receita"]:>10,.0f} -> {p:20}{alerta}')
print(f'   total: {len(plano)} linhas, R$ {sum(x["receita"] for x, _, _ in plano):,.0f}')
resto = [x for x in sem if x['id'] not in usados]
print(f'\n   seguem sem PEP: {len(resto)} linhas, R$ {sum(x["receita"] for x in resto):,.0f}')
for k, v in Counter(str(x['nome_cliente'])[:26] for x in resto).most_common():
    val = sum(y['receita'] for y in resto if str(y['nome_cliente'])[:26] == k)
    print(f'      {k:28} {v} ln  R$ {val:>10,.0f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep, ev in plano:
    fd = (x.get('fonte_dados') or '')
    marca = f' | PEP confirmado na varredura das extracoes ({ev})'
    if 'varredura das extracoes' not in fd:
        fd = (fd + marca)[:500]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': pep.split('.')[0], 'fonte_dados': fd},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

# -*- coding: utf-8 -*-
"""PUC/Fundacao SP (aba Licensing Msf) -> BR02CLP00200.1.2.

Nao ha PEP para esse cliente antes de abril na nossa base (a aba Licensing Msf nunca
tinha sido carregada). Mas o cadastro do SAP tem o projeto: 'PUC SP - AZURE SCE',
cliente FUNDACAO SAO PAULO, BR02, ativo — e a aba Licensing Msf e justamente
licenciamento Microsoft/Azure, entao o projeto casa com a natureza da receita.
Uso: python _pep_puc.py [--apply]
"""
import os, sys
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

APPLY = '--apply' in sys.argv
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PEP = 'BR02CLP00200.1.2'

r = httpx.get(f'{url}/rest/v1/nova_base',
              params={'select': 'id,periodo,nome_cliente,receita,fonte,fonte_dados',
                      'fonte': 'eq.Licensing Msf Q2', 'pep': 'is.null', 'limit': '50'},
              headers=H, timeout=90)
alvo = [x for x in r.json() if 'PUC' in str(x['nome_cliente']).upper()
        or 'FUNDA' in str(x['nome_cliente']).upper()]
print(f'linhas PUC/Fundacao sem projeto: {len(alvo)} | R$ {sum(x["receita"] for x in alvo):,.2f}')
for x in alvo:
    print(f'   {x["periodo"]} {str(x["nome_cliente"])[:26]:26} R$ {x["receita"]:>9,.2f} -> {PEP}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

n = 0
for x in alvo:
    fd = (x.get('fonte_dados') or '')
    if 'PUC SP - AZURE SCE' not in fd:
        fd += (' | PEP do cadastro do SAP: BR02CLP00200 "PUC SP - AZURE SCE" (cliente FUNDACAO '
               'SAO PAULO). Nao havia PEP para esse cliente antes de abril na base')
    rr = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                     json={'pep': PEP, 'pep_base': 'BR02CLP00200', 'fonte_dados': fd[:500]},
                     headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert rr.status_code in (200, 204), f'{rr.status_code} {rr.text[:200]}'
    n += 1
print(f'\natualizadas: {n} linhas')

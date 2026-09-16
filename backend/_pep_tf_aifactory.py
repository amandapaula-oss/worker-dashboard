# -*- coding: utf-8 -*-
"""T&F - AI Factory (aba Play) -> BR02CLP000815, por decisao da Amanda.
No cadastro do SAP o projeto se chama 'AI Factory T&F-Distrito' e esta no cliente
DISTRITO TECNOLOGIA, por isso o casamento automatico por cliente nao aceitou.
Uso: python _pep_tf_aifactory.py [--apply]
"""
import os, sys
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

APPLY = '--apply' in sys.argv
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PEP = 'BR02CLP000815.1.1'

r = httpx.get(f'{url}/rest/v1/nova_base',
              params={'select': 'id,periodo,nome_cliente,tipos,receita,fonte,fonte_dados',
                      'fonte': 'eq.Play Q2', 'pep': 'is.null', 'limit': '100'},
              headers=H, timeout=90)
alvo = [x for x in r.json() if 'AI FACTORY' in str(x['tipos'] or '').upper()]
print(f'linhas T&F - AI Factory sem projeto: {len(alvo)} | R$ {sum(x["receita"] for x in alvo):,.2f}')
for x in alvo:
    print(f'   {x["periodo"]} {str(x["tipos"])[:30]:30} R$ {x["receita"]:>10,.2f} -> {PEP}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

n = 0
for x in alvo:
    fd = (x.get('fonte_dados') or '')
    if 'PEP definido pela Amanda' not in fd:
        fd += (' | PEP definido pela Amanda: BR02CLP000815 (no cadastro do SAP o projeto '
               'se chama "AI Factory T&F-Distrito", cliente DISTRITO)')
    rr = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                     json={'pep': PEP, 'pep_base': 'BR02CLP000815', 'fonte_dados': fd[:500]},
                     headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert rr.status_code in (200, 204), f'{rr.status_code} {rr.text[:200]}'
    n += 1
print(f'\natualizadas: {n} linhas')

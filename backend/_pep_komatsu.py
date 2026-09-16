# -*- coding: utf-8 -*-
"""Komatsu: lanca o projeto que existe, aceitando a inconsistencia de empresa
(decisao da Amanda).

A receita esta na empresa BR02 (abr/26, R$ 56.863,19), mas o cadastro do SAP tem o
contrato 214224_KOMATSU_POWER_PLATFORM em duas empresas:
  BR02CLP00857  (BR02) — vigencia 01 a 15/06/2026 e status 42 (encerrado)
  BR07CLP00205  (BR07) — vigencia 01/04 a 31/10/2026, ativo
So o BR07 cobre abril, entao e ele. A divergencia (linha BR02 x projeto BR07) fica
gravada no fonte_dados, nao escondida.
Uso: python _pep_komatsu.py [--apply]
"""
import os, sys
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

APPLY = '--apply' in sys.argv
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PEP = 'BR07CLP00205.1.1'

r = httpx.get(f'{url}/rest/v1/nova_base',
              params={'select': 'id,periodo,empresa,nome_cliente,tipos,receita,fonte,fonte_dados,vertical',
                      'nome_cliente': 'ilike.*KOMATSU*', 'pep': 'is.null', 'receita': 'neq.0',
                      'limit': '50'}, headers=H, timeout=90)
alvo = [x for x in r.json() if x['fonte'] != 'Budget']
print(f'linhas da Komatsu sem projeto: {len(alvo)} | R$ {sum(x["receita"] for x in alvo):,.2f}')
for x in alvo:
    print(f'   {x["periodo"]} {x["empresa"]} / {x["vertical"]} R$ {x["receita"]:>10,.2f} -> {PEP} '
          f'(projeto e BR07, a linha e {str(x["empresa"])[:4]})')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

n = 0
for x in alvo:
    fd = (x.get('fonte_dados') or '')
    if 'INCONSISTENCIA' not in fd:
        fd += (' | PEP BR07CLP00205 por decisao da Amanda. INCONSISTENCIA CONHECIDA: a receita '
               'esta em BR02 e o projeto e BR07; o mesmo contrato 214224_KOMATSU_POWER_PLATFORM '
               'esta cadastrado nas duas empresas, e so o BR07 tem vigencia em abr/26')
    rr = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                     json={'pep': PEP, 'pep_base': 'BR07CLP00205', 'fonte_dados': fd[:500]},
                     headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert rr.status_code in (200, 204), f'{rr.status_code} {rr.text[:200]}'
    n += 1
print(f'\natualizadas: {n} linhas')

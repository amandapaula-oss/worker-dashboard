# -*- coding: utf-8 -*-
"""Corrige 2 linhas do Q2 que herdaram PEP de OUTRO cliente (por pessoa) e por isso
cairam na BU errada no dash e no bate com a apuracao de metas do Yuri (16/09):
  id 100797  Sortenabet mai/26  BR02CLP00045.1.1 (Banco Inter) -> BR02CLP000183 (Alocacao SORTENABET)
  id 101852  Poliedro   jun/26  BR02CLP000151.1.1 (Banco C6)   -> BR02CLP00056  (ALOCACAO POLIEDRO)
Uso: python _fix_pep_sortenabet_poliedro.py [--apply]"""
import os, sys, httpx
APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'Prefer': 'return=representation'}
FIX = {100797: ('BR02CLP000183', 'Sortenabet'), 101852: ('BR02CLP00056', 'Poliedro')}
for i, (pep, cli) in FIX.items():
    r = httpx.get(f'{url}/rest/v1/nova_base', params={'select': 'id,periodo,nome_cliente,nome_pessoa,pep,pep_base,receita,fonte_dados', 'id': f'eq.{i}'}, headers=H, timeout=60).json()[0]
    assert cli.upper() in str(r['nome_cliente']).upper(), r
    print(f"{i} {r['periodo']} {r['nome_cliente']} | {r['nome_pessoa']} | {r['pep']} -> {pep} | R$ {r['receita']:,.2f}")
    if APPLY:
        fd = (r.get('fonte_dados') or '')[:400] + ' | PEP corrigido 16/09: era de outro cliente (herdado por pessoa)'
        x = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{i}'}, json={'pep': pep, 'pep_base': pep, 'fonte_dados': fd[:500]}, headers=H, timeout=60)
        assert x.status_code in (200, 204), x.text[:200]
        print('   gravado')
print('--- DRY RUN ---' if not APPLY else 'ok')

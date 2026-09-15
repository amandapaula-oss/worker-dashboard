# -*- coding: utf-8 -*-
"""Consistencia Hyper x Others entre os meses.

Problema: a receita da fonte 'Hyper' no Q1 nao tem no_hierarquia, entao fica sem
apuracao, e a regra `_sem_apuracao_para_others` joga a linha pra BU Others. No Q2 a
carga 'Hyper Q2' ja nasce com apuracao_manual='Ecossistema' e fica na BU Hyper.
Resultado: BU Others com R$ 3,1 mi/mes no Q1 e R$ 54 mil/mes no Q2 — o mesmo negocio
aparecendo em BUs diferentes conforme o trimestre.

Correcao: a receita da carteira Hyper do Q1 recebe apuracao_manual='Ecossistema', o
mesmo tratamento do Q2 (e coerente com a regra de 15/09: custo do Hyper e Ecossistema).

NAO mexe nas linhas com apuracao_manual='' (override deliberado: DC029 FC Consult New
Rev, DC040 FC Consult B Sales, Symphony/DISTRITO) — essas sao decisao da Amanda.
Uso: python _apuracao_hyper_q1_consistente.py [--apply]
"""
import os, sys
from collections import Counter

import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-01', '2026-02', '2026-03')

rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,fonte,apuracao_manual,no_hierarquia,receita,'
                                    'nome_cliente,vertical,empresa,pep,fonte_dados',
                          'periodo': f'in.({",".join(PERS)})', 'receita': 'neq.0',
                          'order': 'id', 'limit': '1000', 'offset': str(off)}, headers=H, timeout=90)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(str(b)[:200])
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000

alvo = [x for x in rows
        if x.get('apuracao_manual') is None                       # sem override deliberado
        and not str(x.get('no_hierarquia') or '').strip()         # sem hierarquia -> sem apuracao
        and (str(x.get('fonte')) == 'Hyper'
             or str(x.get('empresa') or '').startswith('BR07')
             or str(x.get('vertical') or '').strip() == 'BU Hyper')]
print(f'receita do Q1 sem apuracao, da carteira Hyper: {len(alvo)} linhas | '
      f'R$ {sum(x["receita"] for x in alvo):,.0f}')
print('  por cliente:', {k[:24]: round(v) for k, v in
                         sorted(((c, sum(x['receita'] for x in alvo if str(x['nome_cliente']) == c))
                                 for c in {str(x['nome_cliente']) for x in alvo}),
                                key=lambda t: -t[1])[:8]})
print('  por mes:', {p: round(sum(x['receita'] for x in alvo if x['periodo'] == p)) for p in PERS})

# o que fica de fora (pra reportar)
override = [x for x in rows if x.get('apuracao_manual') == '']
print(f'\nNAO mexo: {len(override)} linhas com override manual "Sem Apuração" '
      f'(R$ {sum(x["receita"] for x in override):,.0f}) — decisao da Amanda:')
for k, n in Counter(str(x['no_hierarquia'] or '(sem hierarquia)')[:30] for x in override).most_common(6):
    v = sum(x['receita'] for x in override if str(x['no_hierarquia'] or '(sem hierarquia)')[:30] == k)
    print(f'   {k:32} {n:>4} linhas  R$ {v:>10,.0f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
lote = [str(x['id']) for x in alvo]
for i in range(0, len(lote), 100):
    chunk = lote[i:i + 100]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                    json={'apuracao_manual': 'Ecossistema'},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += len(chunk)
print(f'\natualizadas: {feitas} linhas (apuracao_manual = Ecossistema)')

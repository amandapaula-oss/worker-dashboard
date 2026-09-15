# -*- coding: utf-8 -*-
"""Popula o PEP das receitas do Q2 que ficaram sem, herdando o projeto que a MESMA
pessoa tem no MESMO cliente em outro mes (dado real da propria base, nao inferencia
por cliente dominante).

Regra: so aplica quando os PEPs historicos da dupla (pessoa, cliente) sao do mesmo
projeto (mesma raiz). Raizes diferentes = ambiguo, nao mexe.
Marca no fonte_dados que o PEP foi herdado, pra ficar rastreavel.
Uso: python _herda_pep_outro_mes.py [--apply]
"""
import os, sys, unicodedata
from collections import Counter, defaultdict

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')
MARCA = ' | PEP herdado (mesma pessoa+cliente em outro mes)'


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def raiz(p):
    return str(p).split('.')[0]


rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,pep,pep_base,nome_pessoa,nome_cliente,receita,'
                                    'custo_rateado,fonte,fonte_dados,tipos',
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
print(f'nova_base: {len(rows)} linhas')

# historico (pessoa, cliente) -> PEPs, de QUALQUER periodo
hist = defaultdict(Counter)
for x in rows:
    if x['pep'] and x['nome_pessoa'] and x['nome_cliente']:
        hist[(npn(x['nome_pessoa']), npn(x['nome_cliente']))][x['pep']] += 1

alvo = [x for x in rows
        if x['periodo'] in PERS and (x['receita'] or 0) != 0
        and x['fonte'] != 'Budget' and not x['pep'] and x['nome_pessoa'] and x['nome_cliente']]
print(f'receitas do Q2 sem PEP com pessoa e cliente: {len(alvo)}')

plano, stats = [], Counter()
pendentes = []
for x in alvo:
    c = hist.get((npn(x['nome_pessoa']), npn(x['nome_cliente'])))
    if not c:
        stats['sem historico no cliente'] += 1
        pendentes.append((x, 'sem historico'))
        continue
    if len({raiz(p) for p in c}) > 1:
        stats['ambiguo (projetos diferentes)'] += 1
        pendentes.append((x, f'ambiguo: {sorted({raiz(p) for p in c})}'))
        continue
    pep = c.most_common(1)[0][0]                      # o mais usado dessa dupla
    com_fase = [p for p in c if '.' in p]
    if com_fase and '.' not in pep:
        pep = Counter({p: c[p] for p in com_fase}).most_common(1)[0][0]
    plano.append((x, pep))
    stats['herdado'] += 1

print('\n=== plano ===')
for k in sorted(stats):
    print(f'   {k:32} {stats[k]}')
if plano:
    print(f'   valor coberto: R$ {sum(x["receita"] for x, _ in plano):,.0f}')
for x, p in sorted(plano, key=lambda t: -t[0]['receita']):
    print(f'      {x["periodo"]} {str(x["nome_cliente"])[:24]:24} {str(x["nome_pessoa"])[:24]:24} -> {p}')
for x, m in pendentes:
    print(f'      PENDENTE {x["periodo"]} {str(x["nome_cliente"])[:22]:22} {str(x["nome_pessoa"])[:22]:22} {m}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep in plano:
    fd = (x.get('fonte_dados') or '')
    if MARCA not in fd:
        fd = (fd + MARCA)[:500]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': raiz(pep), 'fonte_dados': fd},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

# -*- coding: utf-8 -*-
"""Ultimo passo do PEP: linhas de receita do Q2 ainda sem projeto, cujo CLIENTE tem
um unico projeto em toda a base (incluindo Q1). Nao e escolha entre alternativas —
e a unica opcao existente para aquele cliente.

Travas: (1) o cliente precisa ter UMA unica raiz de PEP no historico inteiro;
        (2) o prefixo do PEP tem que bater com a empresa da linha (BR02 -> BR02 FCamara).
Marca no fonte_dados que o PEP foi herdado do cliente.
Uso: python _herda_pep_por_cliente.py [--apply]
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
MARCA = ' | PEP herdado (unico projeto do cliente na base)'
EMPRESA_PREFIXO = {'BR02 FCamara': 'BR02', 'BR09 NextGen': 'BR09', 'BR07 Hyper': 'BR07',
                   'BR05 SGA': 'BR05', 'BR08 Dojo': 'BR08', 'BR03 Omnik': 'BR03',
                   'BR04 Nação Digital': 'BR04'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def raiz(p):
    return str(p).split('.')[0]


rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,empresa,pep,nome_pessoa,nome_cliente,receita,'
                                    'fonte,fonte_dados,tipos',
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

hist = defaultdict(Counter)
for x in rows:
    if x['pep'] and x['nome_cliente']:
        hist[npn(x['nome_cliente'])][x['pep']] += 1

sem = [x for x in rows if x['periodo'] in PERS and (x['receita'] or 0) != 0
       and x['fonte'] != 'Budget' and not x['pep']]
print(f'receitas do Q2 sem PEP: {len(sem)} | R$ {sum(x["receita"] for x in sem):,.0f}')

plano, stats = [], Counter()
for x in sem:
    c = hist.get(npn(x['nome_cliente']))
    if not c:
        stats['cliente nunca teve PEP'] += 1
        continue
    if len({raiz(p) for p in c}) > 1:
        stats['cliente com varios projetos (nao mexo)'] += 1
        continue
    pep = c.most_common(1)[0][0]
    com_fase = [p for p in c if '.' in p]
    if com_fase and '.' not in pep:
        pep = Counter({p: c[p] for p in com_fase}).most_common(1)[0][0]
    pref = EMPRESA_PREFIXO.get(str(x.get('empresa')))
    if pref and not raiz(pep).startswith(pref):
        stats[f'BLOQUEADO: PEP {raiz(pep)[:4]} x empresa {x.get("empresa")}'] += 1
        print(f'   !! {str(x["nome_cliente"])[:24]:24} empresa={x.get("empresa")} mas PEP={pep} — nao aplicado')
        continue
    plano.append((x, pep))
    stats['vai preencher'] += 1

print('\n=== plano ===')
for k in sorted(stats):
    print(f'   {k:44} {stats[k]}')
if plano:
    print(f'   valor: R$ {sum(x["receita"] for x, _ in plano):,.0f}')
    for x, p in sorted(plano, key=lambda t: -t[0]['receita']):
        print(f'      {x["periodo"]} {str(x["nome_cliente"])[:26]:26} {str(x["tipos"])[:12]:12} {x["receita"]:>10,.0f} -> {p}')

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

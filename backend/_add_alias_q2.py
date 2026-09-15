# -*- coding: utf-8 -*-
"""Acrescenta ao NOME_CLIENTE_ALIAS do main.py as grafias que a Base Unificada do Yuri
usa no Q2 (Cliente Unificado), apontando para o MESMO canonico que o historico ja usa.

Sem isso o dash mostra 'BANCO BTG' com receita ate marco e 'BTG Pactual' so a partir de
abril, como se fossem clientes diferentes.
Uso: python _add_alias_q2.py [--apply]
"""
import os, re, sys, unicodedata
from collections import defaultdict

import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main

DIR = os.path.dirname(os.path.abspath(__file__))
ALIAS = main._NOME_CLIENTE_ALIAS if hasattr(main, '_NOME_CLIENTE_ALIAS') else {}
if not ALIAS:
    main._get_nova_base()
    ALIAS = main.__dict__.get('_NOME_CLIENTE_ALIAS', {})
print(f'aliases ja existentes no main.py: {len(ALIAS)}')


def canonico(nome):
    """segue a cadeia do dicionario ate o nome final"""
    v = ALIAS.get(str(nome).strip().upper(), nome)
    for _ in range(4):
        nv = ALIAS.get(str(v).strip().upper(), v)
        if nv == v:
            break
        v = nv
    return v


df = main._get_nova_base()
d = df[(df['fonte'].astype(str) != 'Budget') & (df['periodo'].astype(str).str.startswith('2026'))].copy()
d['receita'] = pd.to_numeric(d['receita'], errors='coerce').fillna(0)
d = d[d['receita'] != 0]
d['cli'] = d['nome_cliente'].fillna('').astype(str).str.strip()
d['rz'] = d['pep_base'].fillna(d['pep']).fillna('').astype(str).str.strip().str.upper()
q1 = d[d['periodo'].astype(str) <= '2026-03']
q2 = d[d['periodo'].astype(str) >= '2026-04']
r1, r2 = q1.groupby('cli')['receita'].sum(), q2.groupby('cli')['receita'].sum()
sumiu = r1[~r1.index.isin(r2.index)].sort_values(ascending=False)
surgiu = r2[~r2.index.isin(r1.index)].sort_values(ascending=False)
peps1, peps2 = defaultdict(set), defaultdict(set)
for _, x in q1.iterrows():
    if x['rz']:
        peps1[x['cli']].add(x['rz'])
for _, x in q2.iterrows():
    if x['rz']:
        peps2[x['cli']].add(x['rz'])


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO)\b', ' ', v)
    return ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())


novos, usados = [], set()
for c1 in sumiu.index:
    p1 = peps1.get(c1, set())
    cands = sorted(((len(p1 & peps2.get(c2, set())), c2) for c2 in surgiu.index
                    if c2 not in usados and (p1 & peps2.get(c2, set()))), reverse=True)
    motivo = 'PEP em comum'
    if not cands:
        n1 = npn(c1)
        nc = [c2 for c2 in surgiu.index if c2 not in usados and
              (npn(c2).startswith(n1[:9]) or n1.startswith(npn(c2)[:9]))]
        if len(nc) != 1:
            continue
        cands, motivo = [(0, nc[0])], 'nucleo do nome'
    c2 = cands[0][1]
    usados.add(c2)
    alvo = canonico(c1)
    if str(c2).strip().upper() in ALIAS and canonico(c2) == alvo:
        continue                      # ja resolvido
    novos.append((c2, alvo, c1, motivo, r2.get(c2, 0)))

print(f'\n=== {len(novos)} entradas a acrescentar ===')
for c2, alvo, c1, motivo, val in sorted(novos, key=lambda t: -t[4]):
    print(f'   "{c2[:40]:40}" -> "{alvo[:26]:26}"  (era {c1[:22]:22}) [{motivo}] R$ {val:,.0f}')

if not APPLY:
    print('\n--- DRY RUN: main.py nao alterado. Rode com --apply. ---')
    raise SystemExit(0)

src = open(os.path.join(DIR, 'main.py'), encoding='utf-8').read()
marca = '        "YELUM SEGUROS SA": "HDI",\n'
if marca not in src:
    raise SystemExit('nao achei o ponto de insercao no dicionario')
bloco = '        # --- grafias da Base Unificada Q2 (Cliente Unificado do Yuri) ---\n'
for c2, alvo, c1, motivo, _ in sorted(novos, key=lambda t: t[0].upper()):
    esc = c2.replace('"', '\\"').upper()
    bloco += f'        "{esc}": "{alvo}",\n'
src = src.replace(marca, marca + bloco, 1)
open(os.path.join(DIR, 'main.py'), 'w', encoding='utf-8').write(src)
print(f'\nmain.py: {len(novos)} aliases acrescentados ao NOME_CLIENTE_ALIAS')

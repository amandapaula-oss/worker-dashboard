# -*- coding: utf-8 -*-
"""Acha os clientes que mudaram de nome entre o Q1 e o Q2 (a carga do Q2 veio da Base
Unificada do Yuri, com 'Cliente Unificado' escrito diferente) e propoe o alias.

O casamento e por PEP COMPARTILHADO: se o nome A do Q1 e o nome B do Q2 faturam no mesmo
projeto, sao o mesmo cliente. Nome parecido entra so como reforco, nunca sozinho.
Uso: python _depara_clientes_q1q2.py [--apply]   (--apply grava em parametros.xlsx)
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
PARAM = os.path.join(DIR, 'parametros.xlsx')


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO)\b', ' ', v)
    return ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())


df = main._get_nova_base()
d = df[(df['fonte'].astype(str) != 'Budget') & (df['periodo'].astype(str).str.startswith('2026'))].copy()
d['receita'] = pd.to_numeric(d['receita'], errors='coerce').fillna(0)
d = d[d['receita'] != 0]
d['cli'] = d['nome_cliente'].fillna('').astype(str).str.strip()
d['rz'] = d['pep_base'].fillna(d['pep']).fillna('').astype(str).str.strip().str.upper()

q1 = d[d['periodo'].astype(str) <= '2026-03']
q2 = d[d['periodo'].astype(str) >= '2026-04']
r1 = q1.groupby('cli')['receita'].sum()
r2 = q2.groupby('cli')['receita'].sum()
sumiu = r1[~r1.index.isin(r2.index)].sort_values(ascending=False)
surgiu = r2[~r2.index.isin(r1.index)].sort_values(ascending=False)
print(f'clientes so no Q1: {len(sumiu)} (R$ {sumiu.sum():,.0f}) | so no Q2: {len(surgiu)} (R$ {surgiu.sum():,.0f})')

peps1, peps2 = defaultdict(set), defaultdict(set)
for _, x in q1.iterrows():
    if x['rz']:
        peps1[x['cli']].add(x['rz'])
for _, x in q2.iterrows():
    if x['rz']:
        peps2[x['cli']].add(x['rz'])

pares, sem_par = [], []
usados2 = set()
for c1 in sumiu.index:
    p1 = peps1.get(c1, set())
    cands = []
    for c2 in surgiu.index:
        if c2 in usados2:
            continue
        comum = p1 & peps2.get(c2, set())
        if comum:
            cands.append((len(comum), c2, sorted(comum)[:3]))
    if not cands:
        # sem PEP em comum: tenta nome (so aceita se for unico e o nucleo casar)
        n1 = npn(c1)
        nc = [c2 for c2 in surgiu.index if c2 not in usados2 and
              (npn(c2).startswith(n1[:9]) or n1.startswith(npn(c2)[:9]))]
        if len(nc) == 1:
            pares.append((c1, nc[0], 'nome (nucleo igual)', []))
            usados2.add(nc[0])
        else:
            sem_par.append(c1)
        continue
    cands.sort(reverse=True)
    n, c2, comum = cands[0]
    pares.append((c1, c2, f'{n} PEP(s) em comum', comum))
    usados2.add(c2)

print(f'\n=== {len(pares)} pares identificados ===')
tot = 0.0
for c1, c2, motivo, comum in sorted(pares, key=lambda t: -r1.get(t[0], 0)):
    v1, v2 = r1.get(c1, 0), r2.get(c2, 0)
    tot += v2
    ex = f' ex.: {comum[0]}' if comum else ''
    print(f'   {c1[:30]:30} (Q1 {v1:>11,.0f})  <->  {c2[:32]:32} (Q2 {v2:>11,.0f})  [{motivo}{ex}]')
print(f'   receita do Q2 que volta a casar com o historico: R$ {tot:,.0f}')
if sem_par:
    print(f'\n   {len(sem_par)} sem par (provavelmente cliente que encerrou mesmo):')
    for c in sem_par[:10]:
        print(f'      {c[:36]:36} R$ {r1.get(c, 0):>11,.0f}')
so2 = [c for c in surgiu.index if c not in usados2]
if so2:
    print(f'\n   {len(so2)} novos no Q2 sem par (cliente novo):')
    for c in so2[:10]:
        print(f'      {c[:36]:36} R$ {r2.get(c, 0):>11,.0f}')

if not APPLY:
    print('\n--- DRY RUN: parametros.xlsx nao foi alterado. Rode com --apply. ---')
    raise SystemExit(0)

# ---- grava os aliases em parametros.xlsx (aba clientes, coluna nome_base) ----
import shutil
from openpyxl import load_workbook
shutil.copy(PARAM, PARAM.replace('.xlsx', '_BACKUP_antes_alias_q1q2.xlsx'))
cli = pd.read_excel(PARAM, sheet_name='clientes', dtype=str)
cli.columns = [str(c).strip() for c in cli.columns]
idx = {str(r.get('nome_cliente') or '').strip().upper(): i for i, r in cli.iterrows()}
novos, atualizados = 0, 0
for c1, c2, _, _ in pares:
    # canonico = o nome do Q2 (o que a base oficial de metas usa daqui pra frente)
    i = idx.get(c2.upper())
    if i is None:
        cli.loc[len(cli)] = {c: None for c in cli.columns}
        cli.loc[len(cli) - 1, 'nome_cliente'] = c2
        cli.loc[len(cli) - 1, 'nome_base'] = f'{c2}|{c1}'
        novos += 1
    else:
        atual = str(cli.at[i, 'nome_base'] or '').strip()
        partes = [p.strip() for p in atual.split('|') if p.strip()]
        for p in (c2, c1):
            if p.upper() not in [x.upper() for x in partes]:
                partes.append(p)
        cli.at[i, 'nome_base'] = '|'.join(partes)
        atualizados += 1
with pd.ExcelWriter(PARAM, engine='openpyxl', mode='a', if_sheet_exists='replace') as w:
    cli.to_excel(w, sheet_name='clientes', index=False)
load_workbook(PARAM)   # testa abertura
print(f'\nparametros.xlsx atualizado: {novos} clientes novos, {atualizados} com alias acrescentado')
print(f'backup: {os.path.basename(PARAM).replace(".xlsx", "_BACKUP_antes_alias_q1q2.xlsx")}')

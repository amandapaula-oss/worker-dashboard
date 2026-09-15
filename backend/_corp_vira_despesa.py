# -*- coding: utf-8 -*-
"""Area corporativa e DESPESA, nunca custo (regra da Amanda, 15/09).

Estrutura corporativa lancada em projeto INTERNO (PEP BRxxINP / BRxxBO / BRxxBU) estava
com classificacao='custo' e entrava na MARGEM BRUTA. Passa a 'despesa': sai da margem
bruta e continua na BU para o calculo de margem de contribuicao.

De quebra resolve a BU vazia: despesa fica na BU (o pipeline so move receita sem apuracao
para Others), e estrutura corporativa sem dono de negocio vai para BU Others.

NAO mexe: 37 linhas com PEP de CLIENTE e area de backoffice (ex.: pessoa de entrega com
centro de custo BO) — ambiguo, decisao da Amanda.
Uso: python _corp_vira_despesa.py [--apply]
"""
import os, re, sys, unicodedata
from collections import Counter, defaultdict

import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx
import main

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
BUS_REAIS = {'BU Finance', 'BU Retail', 'BU Health', 'BU Multisector', 'BU Logistics', 'BU Hyper'}
POR_NOME = [('TECH RETAIL', 'BU Retail'), ('VTEX', 'BU Retail'), ('E-COMMERCE', 'BU Retail'),
            ('ECOMMERCE', 'BU Retail'), ('IMAGINE', 'BU Multisector'),
            ('LICENSING', 'BU Hyper'), ('HYPER', 'BU Hyper'), ('BIRMINGHAM', 'FC UK')]


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return '' if v in ('NAN', 'NONE', '0') else v


def raiz(p):
    s = str(p or '').split('.')[0].strip().upper()
    return '' if s in ('', 'NAN', 'NONE', '0') else s


df = main._get_nova_base()
d = df[df['periodo'].astype(str).str.startswith('2026')].copy()
for c in ('receita', 'custo_rateado'):
    d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
v = d['vertical'].fillna('').astype(str).str.strip()
ok = d[v.isin(BUS_REAIS)]
bu_por_pep = {}
for rz, g in ok.groupby(ok['pep_base'].fillna(ok['pep']).map(raiz)):
    if rz:
        bu_por_pep[rz] = g.groupby(g['vertical'].astype(str))[['receita', 'custo_rateado']].sum().abs().sum(axis=1).idxmax()

pep = d['pep'].fillna('').astype(str).str.upper()
cl = d['classificacao'].fillna('').astype(str).str.strip().str.lower()
interno = pep.str.match(r'^BR\d{1,2}(INP|BO|BU)')

# 1) estrutura em projeto interno, hoje como custo -> despesa
alvo_desp = d[interno & cl.eq('custo') & (d['custo_rateado'] != 0)]
print(f'1) estrutura corporativa como CUSTO: {len(alvo_desp)} linhas | R$ {alvo_desp["custo_rateado"].sum():,.0f}')
print('   por periodo:', {k: round(g['custo_rateado'].sum()) for k, g in alvo_desp.groupby(alvo_desp['periodo'].astype(str))})

# 2) linhas sem BU (quase todas sao as mesmas) -> BU por pertinencia
sem_bu = d[v.eq('')]
plano_bu, stats_bu = [], Counter()
for _, x in sem_bu.iterrows():
    if pd.isna(x.get('id')):
        continue
    rz = raiz(x.get('pep_base') or x.get('pep'))
    bu = bu_por_pep.get(rz)
    motivo = 'projeto ja classificado'
    if not bu:
        nome = npn(x.get('nome_cliente')) + ' ' + npn(x.get('pep')) + ' ' + npn(x.get('area'))
        for chave, b in POR_NOME:
            if chave in nome:
                bu, motivo = b, f'pertinencia ({chave.title()})'
                break
    if not bu:
        if re.match(r'^BR\d{1,2}CLP', str(x.get('pep') or '').upper()):
            continue                       # projeto de cliente que nao sei: nao chuto
        bu, motivo = 'BU Others', 'estrutura corporativa'
    plano_bu.append((int(x['id']), bu))
    stats_bu[f'{bu} [{motivo}]'] += 1
print(f'\n2) linhas sem BU: {len(sem_bu)} -> classifico {len(plano_bu)}')
for k, n in stats_bu.most_common(8):
    print(f'   {k[:52]:52} {n:>4}')

ids_desp = [int(x['id']) for _, x in alvo_desp.iterrows() if not pd.isna(x.get('id'))]
print(f'\nresumo: {len(ids_desp)} linhas viram despesa (saem da margem bruta), '
      f'{len(plano_bu)} ganham BU')
print(f'   efeito na margem bruta: +R$ {abs(alvo_desp["custo_rateado"].sum()):,.0f} '
      f'(custo que sai do calculo)')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for i in range(0, len(ids_desp), 100):
    chunk = [str(x) for x in ids_desp[i:i + 100]]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                    json={'classificacao': 'despesa'},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += len(chunk)
print(f'classificacao=despesa: {feitas} linhas')

por_bu = defaultdict(list)
for i, bu in plano_bu:
    por_bu[bu].append(str(i))
f2 = 0
for bu, lote in por_bu.items():
    for i in range(0, len(lote), 100):
        chunk = lote[i:i + 100]
        r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                        json={'vertical': bu}, headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
        assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
        f2 += len(chunk)
print(f'vertical preenchida: {f2} linhas')

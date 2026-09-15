# -*- coding: utf-8 -*-
"""Gera o de-para para reconstruir na aba PJs do P&L as colunas que foram deletadas
(Cliente, BU, Projeto, Profit Center) — sao elas que os SUMIFS de 'Custos PJ' da aba
'MC por BU' procuravam, e por isso viraram PJs!#REF!.

Chave: CPF (BRCPF) + competencia; fallback por nome + competencia.
Saida: _depara_pj.csv com uma linha por (cpf, competencia).
"""
import os, re, unicodedata
from collections import Counter, defaultdict

import pandas as pd

os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main

DIR = os.path.dirname(os.path.abspath(__file__))


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    return ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())


def cpfd(v):
    d = re.sub(r'\D', '', str(v or ''))
    return d[-11:].zfill(11) if len(d) >= 9 else ''


df = main._get_nova_base()
d = df[df['periodo'].astype(str).str.startswith('2026')].copy()
for c in ('receita', 'custo_rateado'):
    d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
# so o que e custo de PJ
pj = d[(d['tipo_contrato'].fillna('').astype(str).str.upper().str.contains('PJ|HORA'))
       & (d['custo_rateado'] != 0)]
print(f'linhas de PJ na nossa base: {len(pj)} | custo R$ {pj["custo_rateado"].sum():,.0f}')

linhas = {}
for (cpf, nome, per), g in pj.groupby([pj['cpf'].fillna('').astype(str).map(cpfd),
                                       pj['nome_pessoa'].fillna('').astype(str).map(npn),
                                       pj['periodo'].astype(str)]):
    peso = g.groupby(g['vertical'].astype(str))['custo_rateado'].sum().abs()
    bu = peso.idxmax() if len(peso) else ''
    gg = g[g['vertical'].astype(str) == bu]
    cli = (gg['nome_cliente'].astype(str).mode().iat[0]
           if gg['nome_cliente'].notna().any() else '')
    proj = (gg['pep'].dropna().astype(str).mode().iat[0]
            if gg['pep'].notna().any() else '')
    pc = (gg['no_hierarquia'].dropna().astype(str).mode().iat[0]
          if gg['no_hierarquia'].notna().any() else '')
    linhas[(cpf, nome, per)] = {'cpf': cpf, 'nome': nome, 'competencia': per,
                                'cliente': cli, 'bu': bu, 'projeto': proj,
                                'profit_center': pc,
                                'custo': round(float(g['custo_rateado'].sum()), 2)}
out = pd.DataFrame(linhas.values())
out.to_csv(os.path.join(DIR, '_depara_pj.csv'), index=False, encoding='utf-8-sig', sep=';')
print(f'de-para gerado: {len(out)} linhas (cpf x competencia) -> _depara_pj.csv')
print('  BUs:', dict(Counter(out['bu']).most_common(8)))
print('  com cliente:', int(out['cliente'].ne('').sum()), '| com projeto:', int(out['projeto'].ne('').sum()),
      '| com profit center:', int(out['profit_center'].ne('').sum()))
print('  com CPF:', int(out['cpf'].ne('').sum()), 'de', len(out))

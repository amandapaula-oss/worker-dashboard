# -*- coding: utf-8 -*-
"""Bate a receita de Hyper (BR07) da nossa base contra a FONTE dela — a aba
"Hyper - Serviços" do `Receita 2Q26_V2.xlsx` da contabilidade (Controle Augusto),
que traz CLIENTE | Projeto (PEP) | ID SF | jan..jun/26.

Regra da Amanda (16/09): cada receita bate com a fonte que e' dona dela — BR02 com a
base do Yuri, Hyper com a base de Hyper.
Uso: python _bate_hyper_fonte.py
"""
import os
import re

import pandas as pd

DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main

FONTE = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\03. Apresentações\2026\5. Comitê de Finanças - Fechamentos FP&A'
         r'\00. Fechamento FP&A\6. Contabilidade\Receita 2Q26_V2.xlsx')
MESES = [f'2026-{m:02d}' for m in range(1, 7)]


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE') else p.replace('BRO', 'BR0').split('.')[0]


# ---------- fonte ----------
raw = pd.read_excel(FONTE, sheet_name='Hyper - Serviços', header=None)
hdr = 1
cols = {str(raw.iloc[hdr, j]).strip(): j for j in range(raw.shape[1])}
cj = cols.get('CLIENTE'); pj = cols.get('Projeto (PEP)')
mj = {}
for j in range(raw.shape[1]):
    v = raw.iloc[hdr, j]
    if hasattr(v, 'strftime'):          # datetime OU pd.Timestamp
        mj[v.strftime('%Y-%m')] = j
if not mj or cj is None or pj is None:
    raise SystemExit(f'cabecalho nao reconhecido: cliente={cj} pep={pj} meses={list(mj)}')
fonte = []
for i in range(hdr + 1, len(raw)):
    p = raiz(raw.iloc[i, pj])
    if not p.startswith('BR'):
        continue
    for m, j in mj.items():
        v = pd.to_numeric(raw.iloc[i, j], errors='coerce')
        fonte.append({'pep': p, 'cliente': str(raw.iloc[i, cj]).strip(), 'periodo': m,
                      'valor': 0.0 if pd.isna(v) else float(v)})
f = pd.DataFrame(fonte)
print(f'fonte "Hyper - Serviços": {f["pep"].nunique()} projetos, {len(f)} celulas | '
      f'total jan-jun R$ {f["valor"].sum():,.2f}')
print('   por mes:', {m: round(v) for m, v in f.groupby('periodo')['valor'].sum().items()})

# ---------- nossa base ----------
df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
d = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(MESES)].copy()
d['raiz'] = d['pep'].map(raiz)
hy = d[d['fonte'].astype(str).str.startswith('Hyper')]      # 'Hyper' (Q1) e 'Hyper Q2'
print(f'\nnossa base, fonte Hyper: {len(hy)} linhas | R$ {hy["receita"].sum():,.2f}')
print('   por mes:', {m: round(v) for m, v in hy.groupby('periodo')['receita'].sum().items()})

# ---------- comparacao por PEP x mes ----------
a = f.groupby(['pep', 'periodo'])['valor'].sum()
b = hy.groupby(['raiz', 'periodo'])['receita'].sum()
b.index.names = ['pep', 'periodo']
idx = a.index.union(b.index)
cmp = pd.DataFrame({'fonte': a.reindex(idx, fill_value=0), 'nossa': b.reindex(idx, fill_value=0)})
cmp['dif'] = cmp['nossa'] - cmp['fonte']
div = cmp[cmp['dif'].abs() > 1]
print(f'\n=== PEP x mes divergentes: {len(div)} de {len(cmp)} | soma das difs R$ {div["dif"].sum():,.2f} ===')
por_pep = div.groupby(level=0)['dif'].agg(['sum', 'count']).sort_values('sum', key=abs, ascending=False)
cli_f = f.drop_duplicates('pep').set_index('pep')['cliente'].to_dict()
cli_n = hy.drop_duplicates('raiz').set_index('raiz')['nome_cliente'].to_dict()
print(f'  {"PEP":16} {"cliente":30} {"dif total":>14} {"meses":>6}')
for p, r in por_pep.head(25).iterrows():
    print(f'  {p:16} {str(cli_f.get(p) or cli_n.get(p) or "")[:30]:30} {r["sum"]:>+14,.2f} {int(r["count"]):>6}')

print('\n=== so na FONTE (projeto que nao temos) ===')
so_f = cmp[(cmp['nossa'] == 0) & (cmp['fonte'].abs() > 1)]
g = so_f.groupby(level=0)['fonte'].sum().sort_values(ascending=False)
print(f'  {len(g)} projetos | R$ {g.sum():,.2f}')
for p, v in g.head(12).items():
    print(f'   {p:16} {str(cli_f.get(p, ""))[:34]:34} {v:>12,.2f}')

print('\n=== so na NOSSA base (fonte Hyper, sem o projeto na fonte) ===')
so_n = cmp[(cmp['fonte'] == 0) & (cmp['nossa'].abs() > 1)]
g = so_n.groupby(level=0)['nossa'].sum().sort_values(ascending=False)
print(f'  {len(g)} projetos | R$ {g.sum():,.2f}')
for p, v in g.head(12).items():
    print(f'   {p:16} {str(cli_n.get(p, ""))[:34]:34} {v:>12,.2f}')

# ---------- projetos de Hyper que aparecem em OUTRA fonte nossa (duplicidade) ----------
outros = d[d['raiz'].isin(set(f['pep'])) & ~d['fonte'].astype(str).str.startswith('Hyper')]
print(f'\n=== projeto da base de Hyper lancado por OUTRA fonte nossa: '
      f'{len(outros)} linhas | R$ {outros["receita"].sum():,.2f} ===')
if len(outros):
    print(outros.groupby(['raiz', 'fonte', 'nome_cliente', 'periodo'])['receita'].sum()
          .sort_values(ascending=False).round(2).to_string())

# ---------- comparacao por CLIENTE (tira o ruido de PEP trocado) ----------
import unicodedata
ALIAS = {'BANCO BV': 'VOTORANTIM', 'BANCO VOTORANTIM': 'VOTORANTIM',
         'BANCO DE TOKYO MITSUBISHI UFJ BRASIL': 'MUFG', 'BANCO MUFG BRASIL': 'MUFG',
         'DEXCO': 'DURATEX', 'VIA VAREJO': 'CASAS BAHIA', 'GRUPO CASAS BAHIA': 'CASAS BAHIA',
         'GRUPO ULTRA': 'ULTRA', 'ULTRAPAR': 'ULTRA', 'IRANI PAPEL E EMBALAGEM': 'IRANI',
         'TFSPORTS': 'TRACK FIELD', 'ALLPARK': 'ESTAPAR'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO|FL\s*\d+|SP|MG)\b', ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return ALIAS.get(v, v)


f['k'] = f['cliente'].map(npn)
hy = hy.assign(k=hy['nome_cliente'].map(npn))
A = f.groupby(['k', 'periodo'])['valor'].sum()
B = hy.groupby(['k', 'periodo'])['receita'].sum()
idx = A.index.union(B.index)
c2 = pd.DataFrame({'fonte': A.reindex(idx, fill_value=0), 'nossa': B.reindex(idx, fill_value=0)})
c2['dif'] = c2['nossa'] - c2['fonte']
d2 = c2[c2['dif'].abs() > 1]
print(f'\n\n=== por CLIENTE x mes: {len(d2)} divergencias | soma R$ {d2["dif"].sum():,.2f} ===')
g2 = d2.groupby(level=0)[['fonte', 'nossa', 'dif']].sum().sort_values('dif', key=abs, ascending=False)
print(f'  {"cliente":34} {"fonte":>14} {"nossa":>14} {"dif":>14}')
for k, r in g2.head(22).iterrows():
    print(f'  {k[:34]:34} {r["fonte"]:>14,.2f} {r["nossa"]:>14,.2f} {r["dif"]:>+14,.2f}')
print(f'\n  clientes que batem ao centavo: {len(c2) - len(d2)} de {len(c2)} (cliente x mes)')

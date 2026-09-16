# -*- coding: utf-8 -*-
"""Q1/26 — auditoria dos PEPs contra a peca da contabilidade (Receita Contábil 1Q26).

Para cada linha de receita do Q1 com projeto, pergunta:
  1. esse PEP existe na contabilidade?
  2. e' do MESMO cliente?
  3. o valor cabe no que a contabilidade lancou naquele projeto/mes?
Separa o que foi classificado A MAO por nos (fonte_dados com "PEP:") do que veio na fonte.

Uso: python _audita_pep_q1_contabil.py
"""
import os
import re
import unicodedata
from collections import defaultdict

import pandas as pd

DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main

CONTABIL = os.path.join(os.environ['TEMP'], 'receita_contabil_1q26_copy.xlsx')
CT_COLS = ['cod_empresa', 'projeto', 'tipo_prj', 'elemento_pep', 'nome_prj',
           'cod_cliente', 'nome_cliente', 'centro_lucro', 'responsavel']
MESES = ['2026-01', '2026-02', '2026-03']


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO|CNPJ|FL\s*\d+|SP|MG)\b',
               ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return '' if v in ('NAN', 'NONE') else v


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE') else p.replace('BRO', 'BR0').split('.')[0]


# ---------- contabilidade ----------
raw = pd.read_excel(CONTABIL, sheet_name='Planilha1', header=None)
hdr = c0 = None
for i in range(min(8, len(raw))):
    linha = raw.iloc[i].astype(str).str.strip()
    hit = linha[linha == 'Cod Empresa']
    if len(hit):
        hdr, c0 = i, hit.index[0]
        break
df_ct = raw.iloc[hdr + 1:].rename(columns={c0 + k: n for k, n in enumerate(CT_COLS)})
from datetime import datetime
mes_cols = {}
for i in (max(0, hdr - 1), hdr):
    for j, v in raw.iloc[i].items():
        if isinstance(v, datetime):
            mes_cols.setdefault(f'{v.strftime("%Y-%m")}', j)
for m, j in mes_cols.items():
    df_ct[m] = pd.to_numeric(df_ct[j], errors='coerce').fillna(0.0)
for c in CT_COLS:
    df_ct[c] = (df_ct[c].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                .replace({'nan': '', 'None': ''}))
df_ct = df_ct[df_ct['projeto'] != '']
df_ct['raiz'] = df_ct['elemento_pep'].map(raiz)
df_ct['k'] = df_ct['nome_cliente'].map(npn)

ct_cliente = {}
ct_valor = defaultdict(float)
for _, r in df_ct.iterrows():
    ct_cliente.setdefault(r['raiz'], r['k'])
    for m in MESES:
        ct_valor[(r['raiz'], m)] += -float(r[m])
ct_peps = set(df_ct['raiz']) - {''}
print(f'contabilidade 1Q26: {len(ct_peps)} projetos | R$ {sum(ct_valor.values()):,.2f}')

# de-para de cliente pelos PEPs que os dois lados ja compartilham
df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
df['raiz'] = df['pep'].map(raiz)
df['k'] = df['nome_cliente'].map(npn)
liga = defaultdict(lambda: defaultdict(float))
for _, x in df[(df['raiz'] != '') & (df['k'] != '')].iterrows():
    c = ct_cliente.get(x['raiz'])
    if c:
        liga[x['k']][c] += abs(x['receita']) + 1
depara = {k: max(v, key=v.get) for k, v in liga.items()}

q1 = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(MESES)
        & (~df['fonte'].astype(str).isin(['Budget', 'de para']))].copy()
q1['manual'] = q1['fonte_dados'].astype(str).str.contains(r'\| PEP', regex=True)
q1['ct_k'] = q1['k'].map(lambda k: depara.get(k, k))


def veredito(x):
    p = x['raiz']
    if not p:
        return 'sem projeto'
    if p not in ct_peps:
        return 'projeto NAO existe na contabilidade'
    dono = ct_cliente.get(p, '')
    if dono and x['ct_k'] and dono != x['ct_k']:
        return 'projeto e de OUTRO cliente'
    v = ct_valor.get((p, x['periodo']), 0)
    if abs(v) < 0.01:
        return 'projeto sem receita nesse mes na contabilidade'
    if x['receita'] > v * 1.02 + 1:
        return 'valor MAIOR que o da contabilidade no projeto/mes'
    return 'ok'


q1['veredito'] = q1.apply(veredito, axis=1)
print(f'\nQ1: {len(q1)} linhas de receita | R$ {q1["receita"].sum():,.2f}')
print(f'   classificadas por nos (marca "| PEP"): {int(q1["manual"].sum())} linhas | '
      f'R$ {q1[q1["manual"]]["receita"].sum():,.2f}')

for grupo, rot in ((True, 'PEP QUE NOS COLOCAMOS'), (False, 'PEP QUE VEIO NA FONTE')):
    d = q1[q1['manual'] == grupo]
    if d.empty:
        continue
    print(f'\n=== {rot}: {len(d)} linhas | R$ {d["receita"].sum():,.2f} ===')
    t = d.groupby('veredito')['receita'].agg(['sum', 'count']).sort_values('sum', ascending=False)
    for v, r in t.iterrows():
        print(f'   {v:48} {int(r["count"]):>4} linhas  R$ {r["sum"]:>13,.2f}')

print('\n=== o que nao fechou, cliente a cliente (top 25) ===')
ruim = q1[~q1['veredito'].isin(['ok'])]
g = (ruim.groupby(['veredito', 'nome_cliente', 'raiz', 'manual'])['receita']
     .agg(['sum', 'count']).sort_values('sum', ascending=False))
print(f'  {"veredito":42} {"cliente":26} {"projeto":15} {"nosso":>6} {"R$":>13}')
for (v, cli, p, man), r in g.head(25).iterrows():
    print(f'  {v[:42]:42} {str(cli)[:26]:26} {(p or "-"):15} {"sim" if man else "nao":>6} '
          f'{r["sum"]:>13,.2f}')

print('\n=== projetos da contabilidade sem receita nossa (top 15) ===')
nossos = set(q1['raiz']) - {''}
falta = [(p, sum(ct_valor[(p, m)] for m in MESES)) for p in ct_peps if p not in nossos]
falta = [x for x in falta if abs(x[1]) > 1]
nome = df_ct.drop_duplicates('raiz').set_index('raiz')[['nome_prj', 'nome_cliente']].to_dict('index')
print(f'  {len(falta)} projetos | R$ {sum(v for _, v in falta):,.2f}')
for p, v in sorted(falta, key=lambda t: -t[1])[:15]:
    i = nome.get(p, {})
    print(f'   {p:16} {str(i.get("nome_prj", ""))[:32]:32} {str(i.get("nome_cliente", ""))[:26]:26} '
          f'{v:>12,.2f}')

print('\n=== os 184 projetos sem receita nossa, por empresa ===')
emp = df_ct.drop_duplicates('raiz').set_index('raiz')['cod_empresa'].to_dict()
por_emp = defaultdict(lambda: [0, 0.0])
for p, v in falta:
    e = emp.get(p, '?')
    por_emp[e][0] += 1
    por_emp[e][1] += v
NOME = {'BR02': 'BR02 FCamara', 'BR03': 'BR03', 'BR04': 'BR04 Nação', 'BR05': 'BR05 SGA',
        'BR07': 'BR07 Hyper', 'BR08': 'BR08 Dojo', 'BR09': 'BR09 NextGen'}
for e, (n, v) in sorted(por_emp.items(), key=lambda t: -t[1][1]):
    print(f'   {NOME.get(e, e):16} {n:>4} projetos  R$ {v:>13,.2f}')
carregamos = sum(v for e, (n, v) in por_emp.items() if e in ('BR02', 'BR07', 'BR09'))
print(f'   -> das empresas que carregamos (BR02/BR07/BR09): R$ {carregamos:,.2f}')

print('\n=== FUTEBOLCARD: nossa base x contabilidade ===')
f1 = q1[q1['nome_cliente'].astype(str).str.upper().str.contains('FUTEBOL')]
print(f1.groupby(['periodo', 'fonte', 'raiz'])['receita'].sum().round(2).to_string())
fc = df_ct[df_ct['k'].str.contains('FUTEBOL', na=False)]
print('\n contabilidade:')
print(fc[['cod_empresa', 'elemento_pep', 'nome_prj'] + MESES]
      .assign(**{m: -fc[m] for m in MESES}).to_string(index=False))

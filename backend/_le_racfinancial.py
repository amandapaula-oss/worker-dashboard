# -*- coding: utf-8 -*-
"""Le os RacFinancial_<mes>.xlsx da pasta de Hyper (Financial Controls - Racional\
Receita\BR07 - Hyper\2026\<mes>) — a planilha que a Amanda apontou como fonte do BR07 —
e compara com (1) a aba "Hyper - Serviços" do Receita 2Q26_V2 (Controle Augusto) e
(2) a nossa base.

3 abas por arquivo: TimeAndExpenses (por pessoa), Fee-WIP e UsageBased.
Uso: python _le_racfinancial.py
"""
import os
import re
import unicodedata

import pandas as pd

DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main

PASTA = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\Financial Controls - Racional'
         r'\Receita\BR07 - Hyper\2026')
MES = {'2026-01': ('01 Janeiro', 'Janeiro'), '2026-02': ('02 Fevereiro', 'Fevereiro'),
       '2026-03': ('03 Março', 'Março'), '2026-04': ('04 Abril', 'Abril'),
       '2026-05': ('05 Maio', 'Maio'), '2026-06': ('06 Junho', 'Junho')}
AUGUSTO = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
           r'\30. FP&A NOVO\03. Apresentações\2026\5. Comitê de Finanças - Fechamentos FP&A'
           r'\00. Fechamento FP&A\6. Contabilidade\Receita 2Q26_V2.xlsx')


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE') else p.replace('BRO', 'BR0').split('.')[0]


def cabecalho(raw, chave='PEP'):
    for i in range(min(6, len(raw))):
        linha = [str(v).strip() for v in raw.iloc[i].tolist()]
        if chave in linha:
            return i, {c: j for j, c in enumerate(linha) if c and c != 'nan'}
    return None, {}


def col(cols, *nomes):
    for n in nomes:
        for c, j in cols.items():
            if c.strip().upper() == n:
                return j
    return None


linhas = []
for per, (pasta, nome) in MES.items():
    f = os.path.join(PASTA, pasta, f'RacFinancial_{nome}.xlsx')
    if not os.path.exists(f):
        print(f'!! nao achei {f}')
        continue
    xl = pd.ExcelFile(f)
    for aba in xl.sheet_names:
        if aba not in ('TimeAndExpenses', 'Fee-WIP', 'UsageBased'):
            continue   # 'Projetos SAP' e 'Planilha*' nao sao receita
        raw = pd.read_excel(xl, sheet_name=aba, header=None)
        i, cols = cabecalho(raw)
        if i is None:
            continue
        jp = col(cols, 'PEP')
        jc = col(cols, 'NOME CLIENTE')
        jv = col(cols, 'RECEITA LIQUIDA', 'VALOR TOTAL')   # liquida e' a que vai pro P&L
        jpess = col(cols, 'PROFISSIONAL')
        if jp is None or jv is None:
            print(f'   {per} {aba}: sem coluna de valor/PEP ({list(cols)[:8]})')
            continue
        for k in range(i + 1, len(raw)):
            p = raiz(raw.iloc[k, jp])
            if not p.startswith('BR'):
                continue
            v = pd.to_numeric(raw.iloc[k, jv], errors='coerce')
            if pd.isna(v) or abs(float(v)) < 0.005:
                continue
            linhas.append({'periodo': per, 'aba': aba, 'pep': p,
                           'pep_cheio': str(raw.iloc[k, jp]).strip(),
                           'cliente': str(raw.iloc[k, jc]).strip() if jc is not None else '',
                           'pessoa': str(raw.iloc[k, jpess]).strip() if jpess is not None else '',
                           'valor': round(float(v), 2)})
r = pd.DataFrame(linhas)
print(f'RacFinancial: {len(r)} linhas | {r["pep"].nunique()} projetos | R$ {r["valor"].sum():,.2f}')
print(r.groupby(['periodo', 'aba'])['valor'].sum().unstack(fill_value=0).round(0).to_string())

# ---------- Controle Augusto (aba do arquivo da contabilidade) ----------
raw = pd.read_excel(AUGUSTO, sheet_name='Hyper - Serviços', header=None)
hdr = 1
cols = {str(raw.iloc[hdr, j]).strip(): j for j in range(raw.shape[1])}
cj, pj = cols['CLIENTE'], cols['Projeto (PEP)']
mj = {v.strftime('%Y-%m'): j for j, v in
      ((j, raw.iloc[hdr, j]) for j in range(raw.shape[1])) if hasattr(v, 'strftime')}
aug = []
for i in range(hdr + 1, len(raw)):
    p = raiz(raw.iloc[i, pj])
    if not p.startswith('BR'):
        continue
    for m, j in mj.items():
        v = pd.to_numeric(raw.iloc[i, j], errors='coerce')
        if pd.notna(v) and abs(float(v)) > 0.005:
            aug.append({'periodo': m, 'pep': p, 'cliente': str(raw.iloc[i, cj]).strip(),
                        'valor': round(float(v), 2)})
a = pd.DataFrame(aug)
print(f'\nControle Augusto (aba): {a["pep"].nunique()} projetos | R$ {a["valor"].sum():,.2f}')

# ---------- nossa base ----------
df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
hy = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(MES)
        & df['fonte'].astype(str).str.startswith('Hyper')].copy()
hy['pep_r'] = hy['pep'].map(raiz)
print(f'nossa base (fonte Hyper): {len(hy)} linhas | R$ {hy["receita"].sum():,.2f}')

print('\n=== total por mes ===')
print(f'  {"mes":9} {"RacFinancial":>15} {"Ctrl Augusto":>15} {"nossa base":>15} '
      f'{"Rac-Aug":>12} {"nossa-Rac":>12}')
for per in MES:
    x = r[r['periodo'] == per]['valor'].sum()
    y = a[a['periodo'] == per]['valor'].sum()
    z = hy[hy['periodo'] == per]['receita'].sum()
    print(f'  {per}  {x:>15,.2f} {y:>15,.2f} {z:>15,.2f} {x - y:>+12,.2f} {z - x:>+12,.2f}')
print(f'  {"TOTAL":9} {r["valor"].sum():>15,.2f} {a["valor"].sum():>15,.2f} '
      f'{hy["receita"].sum():>15,.2f} {r["valor"].sum() - a["valor"].sum():>+12,.2f} '
      f'{hy["receita"].sum() - r["valor"].sum():>+12,.2f}')

print('\n=== por PEP x mes: RacFinancial x nossa base ===')
A = r.groupby(['pep', 'periodo'])['valor'].sum()
B = hy.groupby(['pep_r', 'periodo'])['receita'].sum()
B.index.names = ['pep', 'periodo']
idx = A.index.union(B.index)
c = pd.DataFrame({'rac': A.reindex(idx, fill_value=0), 'nossa': B.reindex(idx, fill_value=0)})
c['dif'] = c['nossa'] - c['rac']
div = c[c['dif'].abs() > 1]
cli = r.drop_duplicates('pep').set_index('pep')['cliente'].to_dict()
print(f'  {len(div)} de {len(c)} divergem | soma R$ {div["dif"].sum():,.2f}')
g = div.groupby(level=0)[['rac', 'nossa', 'dif']].sum().sort_values('dif', key=abs, ascending=False)
for p, x in g.head(20).iterrows():
    print(f'   {p:16} {str(cli.get(p, ""))[:28]:28} rac {x["rac"]:>12,.2f} | '
          f'nossa {x["nossa"]:>12,.2f} | dif {x["dif"]:>+12,.2f}')
r.to_pickle(os.path.join(DIR, '_racfinancial_hyper.pkl'))
print('\nsalvo: _racfinancial_hyper.pkl')

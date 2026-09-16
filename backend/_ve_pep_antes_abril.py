# -*- coding: utf-8 -*-
"""Para as 7 linhas do Q2 que seguem sem projeto, procura se o MESMO cliente ja teve
PEP antes de abril (Q1/2026 e 2025) na propria base — e tambem o que o cadastro do SAP
tem para ele. Nao grava nada: so mostra o que existe.
"""
import os, re, unicodedata
from collections import Counter, defaultdict
import pandas as pd

os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO)\b', ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return '' if v in ('NAN', 'NONE') else v


df = main._get_nova_base()
d = df.copy()
d['receita'] = pd.to_numeric(d['receita'], errors='coerce').fillna(0)
d['custo_rateado'] = pd.to_numeric(d['custo_rateado'], errors='coerce').fillna(0)
per = d['periodo'].astype(str)

# as que sobraram
q2 = d[(per >= '2026-04') & (per <= '2026-06') & (d['receita'] != 0)
       & (d['fonte'].astype(str) != 'Budget') & d['pep'].isna()]
print(f'linhas sem projeto no Q2: {len(q2)} | R$ {q2["receita"].sum():,.2f}\n')

# historico ANTES de abril/26 (inclui 2025)
antes = d[(per < '2026-04') & d['pep'].notna()]
hist = defaultdict(Counter)
for _, x in antes.iterrows():
    hist[npn(x['nome_cliente'])][str(x['pep'])] += 1

m = pd.read_excel('pep_master_sap.xlsx', sheet_name='PEPs')
m.columns = [str(c).strip() for c in m.columns]
cad = defaultdict(list)
for _, p in m.iterrows():
    if pd.notna(p['cliente_nome']):
        cad[npn(p['cliente_nome'])].append((str(p['pep']), str(p['descricao'])[:36],
                                            str(p['empresa']), str(p['status'])))

for cli_raw, g in q2.groupby(q2['nome_cliente'].astype(str)):
    cli = npn(cli_raw)
    print(f'=== {cli_raw} — R$ {g["receita"].sum():,.2f} em {len(g)} linha(s) ===')
    h = hist.get(cli)
    if h:
        print('   PEP usado por esse cliente ANTES de abril:')
        for pep, n in h.most_common(6):
            meses = sorted({str(x['periodo']) for _, x in antes.iterrows()
                            if npn(x['nome_cliente']) == cli and str(x['pep']) == pep})
            print(f'      {pep:22} {n:>3}x   meses: {", ".join(meses[:6])}')
    else:
        print('   (nenhum PEP antes de abril na nossa base)')
    c = cad.get(cli)
    if not c:
        # tenta por prefixo
        alt = [k for k in cad if k.startswith(cli[:9]) or cli.startswith(k[:9])]
        c = cad[alt[0]] if len(alt) == 1 else None
    if c:
        print('   no cadastro de projetos do SAP:')
        for pep, desc, emp, st in c[:6]:
            if '.' in pep:
                print(f'      {pep:22} {desc:36} [{emp} st={st}]')
    print()

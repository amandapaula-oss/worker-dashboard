# -*- coding: utf-8 -*-
"""Gera a nova foto da aba 'nova_base_calculada' de cada Apuracao, a partir da base viva,
carregando as 3 colunas manuais (AE Q1, AE Q2, GrupoClienteMap) pelo cliente."""
import os
import pandas as pd
SC = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
      r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
      r'\scratchpad\metas')
OUT = os.path.join(SC, 'foto_nova')
os.makedirs(OUT, exist_ok=True)
MAP = {'Apuração Meta 2026 Health OFICIAL.xlsx': 'BU Health',
       'Apuração Meta Finance (AE) OFICIAL.xlsx': 'BU Finance',
       'Apuração Meta Grupo Mult Oficial.xlsx': 'BU Logistics',
       'Apuração Meta Multisector OFICIAL V3.xlsx': 'BU Multisector',
       'Apuração Meta Retail  (AE) OFICIAL.xlsx': 'BU Retail'}
os.environ.setdefault('SECRET_KEY', 'dbg'); os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx
import main
H = {'apikey': key, 'Authorization': f'Bearer {key}'}
main._get_nova_base()          # carrega o mapa de alias
AL = {str(k).upper(): str(v) for k, v in main.__dict__.get('_NOME_CLIENTE_ALIAS', {}).items()}
def canon(c):
    u = str(c).strip().upper()
    return str(AL.get(u, c)).strip().upper()
print(f'aliases carregados: {len(AL)}')
rows, off = [], 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base_calculada',
                  params={'select': '*', 'order': 'id', 'offset': str(off), 'limit': '1000'},
                  headers=H, timeout=180).json()
    rows += r
    if len(r) < 1000: break
    off += 1000
viva = pd.DataFrame(rows)
print(f'nova_base_calculada viva: {len(viva)} linhas | colunas {len(viva.columns)}')

for arq, bu in MAP.items():
    velho = pd.read_excel(os.path.join(SC, arq), sheet_name='nova_base_calculada')
    velho.columns = [str(c).strip() for c in velho.columns]
    cols = list(velho.columns)
    velho['k'] = velho['nome_cliente'].map(canon)
    man = {}
    for c in ('AE Q1', 'AE Q2', 'GrupoClienteMap'):
        if c not in velho.columns: continue
        g = velho[velho[c].notna() & (velho[c].astype(str).str.strip() != '')]
        man[c] = g.groupby('k')[c].agg(lambda s: s.value_counts().index[0]).to_dict()
    nova = viva[viva['vertical'].astype(str) == bu].copy()
    nova['k'] = nova['nome_cliente'].map(canon)
    for c, d in man.items():
        nova[c] = nova['k'].map(d)
    if 'COMPETENCIA' in cols:
        nova['COMPETENCIA'] = pd.to_datetime(nova['periodo'].astype(str) + '-01', errors='coerce')
    for c in cols:
        if c not in nova.columns:
            nova[c] = None
    nova = nova[cols]
    q2 = nova['periodo'].astype(str).isin(['2026-04', '2026-05', '2026-06'])
    semae = nova[q2 & nova['AE Q2'].isna()
                 & (pd.to_numeric(nova['receita'], errors='coerce').fillna(0) != 0)]
    rec_semae = pd.to_numeric(semae['receita'], errors='coerce').fillna(0).sum()
    p = os.path.join(OUT, f'{bu.replace(" ", "_")}.csv')
    nova.to_csv(p, index=False, encoding='utf-8')
    print(f'{bu:16} {len(velho):>5} -> {len(nova):>5} linhas | sem AE Q2 e com receita: '
          f'{len(semae):>4} linhas / R$ {rec_semae:>12,.2f}  -> {os.path.basename(p)}')
    if len(semae):
        top = (semae.assign(v=pd.to_numeric(semae['receita'], errors='coerce').fillna(0))
               .groupby('nome_cliente')['v'].sum().sort_values(ascending=False).head(5))
        print('                 maiores sem AE no Q2: ' +
              ', '.join(f'{c} {v:,.0f}' for c, v in top.items())[:110])

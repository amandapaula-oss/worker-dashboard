# -*- coding: utf-8 -*-
"""Monta a grade completa da aba nova_base_calculada de cada Apuracao, com AE Q1/AE Q2/
GrupoClienteMap ja' resolvidos em VALOR (a verdade esta' na foto antiga, nao no de-para)."""
import os
import pandas as pd
SC = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
      r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
      r'\scratchpad\metas')
OUT = os.path.join(SC, 'grade'); os.makedirs(OUT, exist_ok=True)
MAP = {'Apuração Meta 2026 Health OFICIAL.xlsx': 'BU Health',
       'Apuração Meta Finance (AE) OFICIAL.xlsx': 'BU Finance',
       'Apuração Meta Grupo Mult Oficial.xlsx': 'BU Logistics',
       'Apuração Meta Multisector OFICIAL V3.xlsx': 'BU Multisector',
       'Apuração Meta Retail  (AE) OFICIAL.xlsx': 'BU Retail'}
Q1 = ['2026-01','2026-02','2026-03']; Q2 = ['2026-04','2026-05','2026-06']
os.environ.setdefault('SECRET_KEY','dbg'); os.environ.setdefault('ALLOWED_ORIGINS','*')
from _supabase_creds import load_creds
load_creds()
import main
main._get_nova_base()
AL = {str(k).upper(): str(v) for k, v in main.__dict__.get('_NOME_CLIENTE_ALIAS', {}).items()}
canon = lambda c: str(AL.get(str(c).strip().upper(), c)).strip().upper()
CB = 'CASAS BAHIA|VIA VAREJO'
resumo = {}
for arq, bu in MAP.items():
    velho = pd.read_excel(os.path.join(SC, arq), sheet_name='nova_base_calculada')
    velho.columns = [str(c).strip() for c in velho.columns]
    cols = list(velho.columns)
    velho['k'] = velho['nome_cliente'].map(canon)
    velho['receita'] = pd.to_numeric(velho['receita'], errors='coerce').fillna(0)
    # 1) verdade da foto: AE por cliente e por trimestre, com peso de receita
    mapas = {}
    for c, per in (('AE Q1', Q1), ('AE Q2', Q2), ('GrupoClienteMap', None)):
        if c not in velho.columns: continue
        base = velho if per is None else velho[velho['periodo'].astype(str).str[:7].isin(per)]
        g = base[base[c].notna() & (base[c].astype(str).str.strip().isin(['','nan','None','0']) == False)]
        if len(g):
            mapas[c] = g.groupby('k').apply(
                lambda d: d.groupby(c)['receita'].sum().abs().idxmax()
                if d['receita'].abs().sum() > 0 else d[c].iloc[0], include_groups=False).to_dict()
        else:
            mapas[c] = {}
    # 2) de-para como reserva
    raw = pd.read_excel(os.path.join(SC, arq), sheet_name='PARA DE', header=None)
    dp = raw.iloc[:, [2, 3, 4, 5]].copy(); dp.columns = ['grupo','cliente','ae1','ae2']
    dp = dp[dp['cliente'].notna()]
    res = {'AE Q1': {}, 'AE Q2': {}, 'GrupoClienteMap': {}}
    for _, r in dp.iterrows():
        k = canon(r['cliente'])
        for c, v in (('AE Q1', r['ae1']), ('AE Q2', r['ae2']), ('GrupoClienteMap', r['grupo'])):
            s = str(v).strip()
            if s and s not in ('nan','None','0'): res[c].setdefault(k, s)
    # 3) grade nova
    n = pd.read_csv(os.path.join(SC, 'foto_nova', bu.replace(' ', '_') + '.csv'))
    n['k'] = n['nome_cliente'].map(canon)
    n['COMPETENCIA'] = pd.to_datetime(n['periodo'].astype(str) + '-01', errors='coerce')
    for c in ('AE Q1','AE Q2','GrupoClienteMap'):
        n[c] = n['k'].map(lambda k: mapas.get(c, {}).get(k) or res[c].get(k, ''))
    n.loc[n['k'].str.contains(CB, na=False), 'AE Q2'] = ''          # trava Casas Bahia
    for c in cols:
        if c not in n.columns: n[c] = None
    n = n[cols]
    n.to_excel(os.path.join(OUT, bu.replace(' ', '_') + '.xlsx'), index=False, sheet_name='dados')
    n['receita'] = pd.to_numeric(n['receita'], errors='coerce').fillna(0)
    q2 = n[n['periodo'].astype(str).isin(Q2) & (n['receita'] != 0) & (n['AE Q2'].astype(str).str.strip() != '')]
    for ae, v in q2.groupby(n['AE Q2'])['receita'].sum().items():
        resumo[ae] = resumo.get(ae, 0) + v
    print(f'{bu:16} {len(n):>5} linhas -> {bu.replace(" ","_")}.xlsx')
print('\nCONFERENCIA: meta Q2 por AE a partir da grade gerada')
for ae, v in sorted(resumo.items(), key=lambda z: -z[1]):
    print(f'   {str(ae)[:34]:34} {v:>15,.2f}')

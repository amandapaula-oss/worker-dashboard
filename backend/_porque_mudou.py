# -*- coding: utf-8 -*-
"""Por que cada AE mudou: abre cliente a cliente, com a fonte, e classifica a causa."""
import os
import pandas as pd
SC = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
      r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
      r'\scratchpad\metas')
MAP = {'Apuração Meta 2026 Health OFICIAL.xlsx': 'BU Health',
       'Apuração Meta Finance (AE) OFICIAL.xlsx': 'BU Finance',
       'Apuração Meta Grupo Mult Oficial.xlsx': 'BU Logistics',
       'Apuração Meta Multisector OFICIAL V3.xlsx': 'BU Multisector',
       'Apuração Meta Retail  (AE) OFICIAL.xlsx': 'BU Retail'}
Q2 = ['2026-04', '2026-05', '2026-06']
NOVAS = ['Hyper Q2', 'Play Q2', 'Sales Boost Q2', 'Licensing Hyper Q2', 'Licensing Msf Q2']
DUP_ABR = {'OURIBANK', 'TRIBANCO', 'TRAVELEX', 'RUMO', 'RUMO S.A.', 'KOMATSU'}
os.environ.setdefault('SECRET_KEY', 'dbg'); os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main
main._get_nova_base()
AL = {str(k).upper(): str(v) for k, v in main.__dict__.get('_NOME_CLIENTE_ALIAS', {}).items()}
canon = lambda c: str(AL.get(str(c).strip().upper(), c)).strip().upper()
linhas = []
for arq, bu in MAP.items():
    t = pd.read_excel(os.path.join(SC, arq), sheet_name='nova_base_calculada')
    t.columns = [str(c).strip() for c in t.columns]
    t['receita'] = pd.to_numeric(t.get('receita'), errors='coerce').fillna(0)
    t['AE'] = t.get('AE Q2', pd.Series('', index=t.index)).fillna('').astype(str).str.strip()
    t['k'] = t['nome_cliente'].map(canon)
    q = t[t['periodo'].astype(str).str[:7].isin(Q2) & (t['receita'] != 0)]
    com = q[(q['AE'] != '') & (q['AE'] != '0')]
    foto_ae = {k: g.groupby('AE')['receita'].sum().abs().idxmax() for k, g in com.groupby('k')}
    raw = pd.read_excel(os.path.join(SC, arq), sheet_name='PARA DE', header=None)
    d = raw.iloc[:, [3, 5]].copy(); d.columns = ['cliente', 'ae']
    d = d[d['cliente'].notna()]; d['ae'] = d['ae'].astype(str).str.strip()
    d = d[~d['ae'].isin(['', 'nan', 'None', '0'])]
    reserva = {}
    for _, r in d.iterrows(): reserva.setdefault(canon(r['cliente']), r['ae'])
    a = com.groupby(['AE', 'k'])['receita'].sum()
    n = pd.read_csv(os.path.join(SC, 'foto_nova', bu.replace(' ', '_') + '.csv'))
    n['receita'] = pd.to_numeric(n['receita'], errors='coerce').fillna(0)
    n = n[n['periodo'].astype(str).isin(Q2) & (n['receita'] != 0)].copy()
    n['k'] = n['nome_cliente'].map(canon)
    cb = n['k'].str.contains('CASAS BAHIA|VIA VAREJO', na=False)
    n['trava'] = cb | n['fonte'].astype(str).isin(NOVAS)
    n['AE'] = n['k'].map(lambda k: foto_ae.get(k) or reserva.get(k, ''))
    b = n[(n['AE'] != '') & (~n['trava'])].groupby(['AE', 'k'])['receita'].sum()
    trav = n[(n['AE'] != '') & (n['trava'])].groupby(['AE', 'k'])['receita'].sum()
    for key in sorted(set(a.index) | set(b.index)):
        va, vb = float(a.get(key, 0)), float(b.get(key, 0))
        if abs(vb - va) < 100: continue
        ae, cli = key
        vt = float(trav.get(key, 0))
        if vt > 100 and abs(vb - va + vt) < max(500, abs(va) * 0.02):
            causa = f'base nova nao entra (R$ {vt:,.0f})'
        elif cli in DUP_ABR:
            causa = 'duplicidade de abril removida'
        elif vb == 0:
            causa = 'saiu no ajuste da contabilidade'
        else:
            causa = 'ajuste da contabilidade / reescala'
        linhas.append({'AE': ae, 'cliente': cli, 'antes': va, 'depois': vb,
                       'dif': round(vb - va, 2), 'causa': causa})
x = pd.DataFrame(linhas)
for ae, g in x.groupby('AE'):
    if abs(g['dif'].sum()) < 100: continue
    print(f'\n=== {ae}  ({g["dif"].sum():+,.2f}) ===')
    for _, r in g.reindex(g['dif'].abs().sort_values(ascending=False).index).iterrows():
        print(f'   {str(r["cliente"])[:28]:28} {r["antes"]:>13,.2f} -> {r["depois"]:>13,.2f} '
              f'{r["dif"]:>+12,.2f}   {r["causa"]}')

# -*- coding: utf-8 -*-
"""Escopo do Yuri + valor da contabilidade: so os clientes que a foto dele contava,
revalorizados pela base de hoje (que e' igual ao arquivo que foi pro contabil)."""
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
os.environ.setdefault('SECRET_KEY', 'dbg'); os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main
main._get_nova_base()
AL = {str(k).upper(): str(v) for k, v in main.__dict__.get('_NOME_CLIENTE_ALIAS', {}).items()}
canon = lambda c: str(AL.get(str(c).strip().upper(), c)).strip().upper()
yuri, novo, det = {}, {}, []
for arq, bu in MAP.items():
    t = pd.read_excel(os.path.join(SC, arq), sheet_name='nova_base_calculada')
    t.columns = [str(c).strip() for c in t.columns]
    t['receita'] = pd.to_numeric(t.get('receita'), errors='coerce').fillna(0)
    t['AE'] = t.get('AE Q2', pd.Series('', index=t.index)).fillna('').astype(str).str.strip()
    t['k'] = t['nome_cliente'].map(canon)
    com = t[t['periodo'].astype(str).str[:7].isin(Q2) & (t['receita'] != 0)
            & (t['AE'] != '') & (t['AE'] != '0')]
    com = com[~com['k'].str.contains('CASAS BAHIA|VIA VAREJO', na=False)]
    escopo = com.groupby(['AE', 'k'])['receita'].sum()          # o que o Yuri contava
    n = pd.read_csv(os.path.join(SC, 'foto_nova', bu.replace(' ', '_') + '.csv'))
    n['receita'] = pd.to_numeric(n['receita'], errors='coerce').fillna(0)
    n = n[n['periodo'].astype(str).isin(Q2) & (n['receita'] != 0)].copy()
    n['k'] = n['nome_cliente'].map(canon)
    n = n[~n['k'].str.contains('CASAS BAHIA|VIA VAREJO', na=False)]   # decisao: CB fora da meta
    hoje = n.groupby('k')['receita'].sum()
    for (ae, k), v in escopo.items():
        yuri[ae] = yuri.get(ae, 0) + v
        vn = float(hoje.get(k, 0))
        novo[ae] = novo.get(ae, 0) + vn
        if abs(vn - v) > 100:
            det.append({'AE': ae, 'cliente': k, 'yuri': v, 'contabil': vn, 'dif': round(vn - v, 2)})
x = pd.DataFrame({'yuri': pd.Series(yuri), 'novo': pd.Series(novo)}).fillna(0)
x['dif'] = (x['novo'] - x['yuri']).round(2)
x['%'] = (x['dif'] / x['yuri'].replace(0, pd.NA) * 100).round(1)
m = x[x['dif'].abs() > 100].sort_values('dif')
print(f'ESCOPO DO YURI + VALOR DA CONTABILIDADE')
print(f'{len(m)} AEs mudam | desvio absoluto R$ {m["dif"].abs().sum():,.2f} | '
      f'sobem {(m["dif"]>0).sum()} | descem {(m["dif"]<0).sum()}\n')
print(f'{"AE":34} {"e-mail":>14} {"novo":>14} {"dif":>13} {"%":>7}')
for k, r in m.iterrows():
    print(f'{str(k)[:34]:34} {r["yuri"]:>14,.2f} {r["novo"]:>14,.2f} {r["dif"]:>+13,.2f} {r["%"]:>6.1f}%')
print(f'\npor cliente:')
dd = pd.DataFrame(det)
for _, r in dd.reindex(dd['dif'].abs().sort_values(ascending=False).index).head(14).iterrows():
    print(f'   {str(r["AE"])[:24]:24} {str(r["cliente"])[:26]:26} {r["yuri"]:>13,.2f} -> '
          f'{r["contabil"]:>13,.2f} {r["dif"]:>+12,.2f}')

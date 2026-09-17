# -*- coding: utf-8 -*-
"""Bate o arquivo final da Paola (receita_contabilidade_2Q26_vf) com a nossa base no Q2."""
import os
import pandas as pd
SC = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
      r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
      r'\scratchpad\paola')
os.environ.setdefault('SECRET_KEY', 'dbg'); os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main
Q2 = ['2026-04', '2026-05', '2026-06']
F = os.path.join(SC, 'receita_contabilidade_2Q26_vf.xlsx')
raw = pd.read_excel(F, sheet_name='Consolidado por PEP', header=None)
h = next(i for i in range(12) if any(str(x).strip() == 'PEP' for x in raw.iloc[i]))
p = pd.read_excel(F, sheet_name='Consolidado por PEP', header=h)
p.columns = [str(c).strip() for c in p.columns]
c = {x.lower(): x for x in p.columns}
mc = next(x for x in p.columns if x.strip().lower() in ('mês', 'mes'))
vc = next(x for x in p.columns if x.strip().lower().startswith('valor'))
pc = next(x for x in p.columns if x.strip().lower() == 'pep')
p['m'] = pd.to_datetime(p[mc], errors='coerce').dt.strftime('%Y-%m')
p['v'] = pd.to_numeric(p[vc], errors='coerce').fillna(0)
p = p[p['m'].isin(Q2)]
p['emp'] = p[c['empresa']].astype(str).str.extract(r'(BR\d\d)')[0].fillna('?')
p['r'] = p[pc].astype(str).str.upper().str.replace('BRO', 'BR0').str.split('.').str[0]
print(f'ARQUIVO FINAL (2Q26_vf): {len(p)} linhas | R$ {p["v"].sum():,.2f}')

df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
n = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(Q2)
       & (~df['fonte'].astype(str).isin(['Budget', 'de para']))].copy()
n['emp'] = n['empresa'].astype(str).str.extract(r'(BR\d\d)')[0].fillna('?')
n['r'] = n['pep'].astype(str).str.upper().str.replace('BRO', 'BR0').str.split('.').str[0]
n['m'] = n['periodo'].astype(str)
print(f'NOSSA BASE Q2:           {len(n)} linhas | R$ {n["receita"].sum():,.2f}')
print(f'DIFERENCA: R$ {n["receita"].sum() - p["v"].sum():+,.2f}\n')
print(f'{"mes":9} {"empresa":8} {"arquivo Paola":>16} {"nossa base":>16} {"dif":>14}')
for m in Q2:
    for e in sorted(set(p['emp']) | set(n['emp'])):
        a = p[(p['m'] == m) & (p['emp'] == e)]['v'].sum()
        b = n[(n['m'] == m) & (n['emp'] == e)]['receita'].sum()
        if abs(a) + abs(b) < 1: continue
        fl = '  <<<' if abs(a - b) > 1 else ''
        print(f'{m:9} {e:8} {a:>16,.2f} {b:>16,.2f} {b-a:>+14,.2f}{fl}')
ga = p.groupby(['m', 'r'])['v'].sum()
gb = n.groupby(['m', 'r'])['receita'].sum()
idx = sorted(set(ga.index) | set(gb.index))
lin = [{'mes': m, 'pep': r, 'paola': float(ga.get((m, r), 0)),
        'nossa': float(gb.get((m, r), 0))} for m, r in idx]
x = pd.DataFrame(lin)
x['dif'] = (x['nossa'] - x['paola']).round(2)
d = x[x['dif'].abs() > 0.5]
print(f'\n=== projeto x mes divergentes: {len(d)} de {len(x)} | soma {d["dif"].sum():+,.2f} ===')
cli = n.drop_duplicates('r').set_index('r')['nome_cliente'].to_dict()
cli.update(p.drop_duplicates('r').set_index('r')[c['cliente']].to_dict())
for _, r in d.reindex(d['dif'].abs().sort_values(ascending=False).index).head(25).iterrows():
    print(f'   {r["mes"]} {str(r["pep"])[:18]:18} {str(cli.get(r["pep"], ""))[:28]:28} '
          f'Paola {r["paola"]:>13,.2f} nossa {r["nossa"]:>13,.2f} dif {r["dif"]:>+12,.2f}')
d.to_csv(os.path.join(SC, 'dif_vf_q2.csv'), index=False, encoding='utf-8')

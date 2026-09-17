# -*- coding: utf-8 -*-
"""Extrai as MARRETAS da Paola: diff da aba 'Consolidado por PEP' do arquivo (3) dela
contra o que o nosso sistema produz HOJE, com a mesma agregacao do export."""
import os
import numpy as np
import pandas as pd
SC = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
      r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
      r'\scratchpad\paola')
os.environ.setdefault('SECRET_KEY', 'dbg'); os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main
import receita_contabilidade as rc

df = main._get_nova_base().copy()
d = df.copy()
d['receita'] = pd.to_numeric(d['receita'], errors='coerce').fillna(0)
d['periodo'] = d.get('periodo', '').astype(str).str.strip()
fonte = d.get('fonte', pd.Series('', index=d.index)).fillna('').astype(str).str.strip()
d = d[(d['receita'] != 0) & (~fonte.isin(['Budget', 'de para']))]
pc = rc._profit_center_por_pep()
pep = d.get('pep', '').fillna('').astype(str).str.strip()
cc = d.get('no_hierarquia', '').fillna('').astype(str).str.strip()
nosso = pd.DataFrame({
    'mes': d['periodo'],
    'empresa': d.get('empresa', '').fillna('').astype(str).str.strip(),
    'cc': cc,
    'bu': d.get('vertical', '').fillna('').astype(str).str.strip(),
    'pep': pep,
    'cliente': d.get('nome_cliente', '').fillna('').astype(str).str.strip(),
    'ap': d.get('apuracao', '').fillna('').astype(str).str.strip(),
    'valor': d['receita'],
})
gn = nosso.groupby(['mes', 'empresa', 'pep', 'cliente'], dropna=False, as_index=False).agg(
    valor=('valor', 'sum'), bu=('bu', 'first'), cc=('cc', 'first'), ap=('ap', 'first'))

p = pd.read_excel(os.path.join(SC, 'receita_contabilidade_todos_os_meses (3).xlsx'),
                  sheet_name='Consolidado por PEP', header=None)
h = next(i for i in range(12) if 'PEP' in [str(x).strip() for x in p.iloc[i]])
p = pd.read_excel(os.path.join(SC, 'receita_contabilidade_todos_os_meses (3).xlsx'),
                  sheet_name='Consolidado por PEP', header=h)
p.columns = [str(c).strip() for c in p.columns]
col = {c.lower(): c for c in p.columns}
mc = next(c for c in p.columns if c.strip().lower() in ('mês', 'mes'))
gp = pd.DataFrame({
    'mes': pd.to_datetime(p[mc], errors='coerce').dt.strftime('%Y-%m'),
    'empresa': p[col['empresa']].fillna('').astype(str).str.strip(),
    'pep': p[col['pep']].fillna('').astype(str).str.strip(),
    'cliente': p[col['cliente']].fillna('').astype(str).str.strip(),
    'valor': pd.to_numeric(p[col['valor']], errors='coerce').fillna(0),
})
gp = gp[gp['mes'].notna()]
gp = gp.groupby(['mes', 'empresa', 'pep', 'cliente'], dropna=False, as_index=False)['valor'].sum()

m = gn.merge(gp, on=['mes', 'empresa', 'pep', 'cliente'], how='outer',
             suffixes=('_nosso', '_paola'), indicator=True)
m['valor_nosso'] = m['valor_nosso'].fillna(0)
m['valor_paola'] = m['valor_paola'].fillna(0)
m['dif'] = (m['valor_paola'] - m['valor_nosso']).round(2)
print(f'nosso {gn["valor"].sum():,.2f}  x  Paola {gp["valor"].sum():,.2f}  '
      f'= {gp["valor"].sum()-gn["valor"].sum():+,.2f}')
print('\npor mes:')
for mm in sorted(set(m['mes'].dropna())):
    z = m[m['mes'] == mm]
    print(f'   {mm}  nosso {z["valor_nosso"].sum():>15,.2f}  Paola {z["valor_paola"].sum():>15,.2f}'
          f'  dif {z["dif"].sum():>+13,.2f}')
dif = m[m['dif'].abs() > 0.01].copy()
print(f'\n=== {len(dif)} chaves com diferenca ===')
so_p = dif[dif['valor_nosso'] == 0]
so_n = dif[dif['valor_paola'] == 0]
amb = dif[(dif['valor_nosso'] != 0) & (dif['valor_paola'] != 0)]
print(f'   SO NA PAOLA (ela criou):  {len(so_p):>4} | R$ {so_p["valor_paola"].sum():>13,.2f}')
print(f'   SO NOSSO (ela apagou):    {len(so_n):>4} | R$ {so_n["valor_nosso"].sum():>13,.2f}')
print(f'   VALOR DIFERENTE:          {len(amb):>4} | R$ {amb["dif"].sum():>+13,.2f}')
for rot, z, c in (('ELA CRIOU', so_p, 'valor_paola'), ('ELA APAGOU', so_n, 'valor_nosso'),
                  ('ELA MUDOU O VALOR', amb, 'dif')):
    if not len(z): continue
    print(f'\n--- {rot} ---')
    for _, r in z.reindex(z[c].abs().sort_values(ascending=False).index).head(30).iterrows():
        print(f'   {r["mes"]} {str(r["empresa"])[:13]:13} {str(r["pep"])[:18]:18} '
              f'{str(r["cliente"])[:28]:28} nosso {r["valor_nosso"]:>12,.2f} '
              f'Paola {r["valor_paola"]:>12,.2f} dif {r["dif"]:>+12,.2f}')
dif.to_csv(os.path.join(SC, 'marretas_paola.csv'), index=False, encoding='utf-8')
print(f'\nsalvo: {os.path.join(SC, "marretas_paola.csv")}')

# -*- coding: utf-8 -*-
"""Por que a BU Health do Q1 nao voltou ao que era antes do alinhamento."""
import os, sys
import pandas as pd
DIR = os.path.dirname(os.path.abspath(__file__))
Q1 = ['2026-01', '2026-02', '2026-03']
os.environ.setdefault('SECRET_KEY', 'dbg-readonly'); os.environ.setdefault('ALLOWED_ORIGINS', '*')
sys.path.insert(0, DIR)
from _supabase_creds import load_creds; load_creds()
import main
main._cache['nova_base'] = None
nb = main._get_nova_base()
nb['receita'] = pd.to_numeric(nb['receita'], errors='coerce').fillna(0)
q1 = nb[nb['periodo'].astype(str).isin(Q1)].copy()

print('=== 1. Q1 do pipeline por empresa ===')
emp = q1.groupby('empresa')['receita'].sum().sort_values(ascending=False)
for k, v in emp.items():
    print(f'   {str(k)[:34]:34} {v:>16,.2f}')
TRES = [k for k in emp.index if str(k)[:4] in ('BR02', 'BR07', 'BR09')
        or str(k).strip() in ('BR02', 'BR07', 'BR09')]
print(f'   ---\n   BR02+BR07+BR09: {emp[TRES].sum():,.2f}   (antes do alinhamento: 77,344,202.05'
      f' | dif {emp[TRES].sum() - 77344202.05:+,.2f})')

print('\n=== 2. Odontoprev: BU por periodo (a regra "1 cliente = 1 BU" ignora periodo) ===')
od = nb[nb['nome_cliente'].astype(str).str.upper().str.contains('ODONTOPREV', na=False)]
if len(od):
    print(od.groupby([od['periodo'].astype(str), 'vertical'])['receita']
          .agg(['size', 'sum']).round(2).to_string())
else:
    print('   (nenhuma linha de Odontoprev)')

print('\n=== 3. Health Q1 por cliente (top 25) ===')
he = q1[q1['vertical'] == 'BU Health']
print(f'   total BU Health Q1: {he["receita"].sum():,.2f}')
print(he.groupby(he['nome_cliente'].astype(str).str[:34])['receita'].sum()
      .sort_values(ascending=False).head(25).round(2).to_string())

print('\n=== 4. clientes cuja BU difere entre Q1 e Q2 (nao deveria haver, pela regra) ===')
pq = nb[nb['periodo'].astype(str).str[:7].isin(Q1 + ['2026-04', '2026-05', '2026-06'])].copy()
pq['tri'] = pq['periodo'].astype(str).map(lambda p: 'Q1' if p in Q1 else 'Q2')
cross = pq.groupby(['nome_cliente', 'tri'])['vertical'].agg(lambda s: '|'.join(sorted(set(s.dropna()))))
cross = cross.unstack('tri')
dif = cross[(cross.get('Q1').notna()) & (cross.get('Q2').notna()) & (cross['Q1'] != cross['Q2'])]
print(dif.to_string() if len(dif) else '   (nenhum)')

# -*- coding: utf-8 -*-
"""Compara a 'MC por BU' REPARADA com o nosso dashboard, BU a BU e mes a mes."""
import os

import pandas as pd
import win32com.client as win32

os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main

ARQ = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
       r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
       r'\scratchpad\pnl_corrigido.xlsx')
COLS = {'E': '2026-01', 'F': '2026-02', 'G': '2026-03'}
BLOCOS = [(33, 'BU Retail'), (48, 'BU Health'), (63, 'BU Finance'),
          (78, 'BU Multisector'), (94, 'BU Logistics')]

# ---------- planilha ----------
excel = win32.DispatchEx('Excel.Application')
excel.Visible = False
excel.DisplayAlerts = False
plan = {}
try:
    wb = excel.Workbooks.Open(ARQ, 0, True)
    mc = wb.Worksheets('MC por BU')
    for base, bu in BLOCOS:
        for c, per in COLS.items():
            rec = mc.Range(f'{c}{base + 1}').Value
            cus = mc.Range(f'{c}{base + 2}').Value
            plan[(bu, per)] = (float(rec or 0), float(cus or 0))
    tot = {}
    for c, per in COLS.items():
        tot[per] = (float(mc.Range(f'{c}6').Value or 0), float(mc.Range(f'{c}7').Value or 0))
    wb.Close(False)
finally:
    excel.Quit()

# ---------- dashboard ----------
df = main._get_nova_base()
d = df[df['periodo'].astype(str).isin(list(COLS.values())) & (df['fonte'].astype(str) != 'Budget')].copy()
for c in ('receita', 'custo_rateado'):
    d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
ma = d['macro_area'].fillna('').astype(str).str.strip().ne('')
soc = d['fonte'].fillna('').astype(str).str.strip().isin(['Custo Socios', 'Custo Sócios'])
cl = d['classificacao'].fillna('').astype(str).str.strip().str.lower()
desp = (cl == 'despesa') | ((cl != 'custo') & (ma | soc))
d['custo_bruto'] = d['custo_rateado'].where(~desp, 0)

print(f'{"BU":16}{"mes":9}{"receita plan":>15}{"receita dash":>15}{"dif":>13}   '
      f'{"%GM plan":>9}{"%GM dash":>9}')
print('-' * 92)
for bu in [b for _, b in BLOCOS]:
    for per in COLS.values():
        rp, cp = plan[(bu, per)]
        g = d[(d['vertical'].astype(str) == bu) & (d['periodo'].astype(str) == per)]
        rd = float(g['receita'].sum())
        cd = float(g['custo_bruto'].sum())
        gp = (rp + cp) / rp * 100 if rp else 0
        gd = (rd + cd) / rd * 100 if rd else 0
        print(f'{bu[:16]:16}{per[-2:]:9}{rp:>15,.0f}{rd:>15,.0f}{rd - rp:>13,.0f}   {gp:>8.1f}%{gd:>8.1f}%')
print('-' * 92)
for per in COLS.values():
    rp, cp = tot[per]
    g = d[d['periodo'].astype(str) == per]
    rd, cd = float(g['receita'].sum()), float(g['custo_bruto'].sum())
    print(f'{"TOTAL":16}{per[-2:]:9}{rp:>15,.0f}{rd:>15,.0f}{rd - rp:>13,.0f}   '
          f'{(rp + cp) / rp * 100:>8.1f}%{(rd + cd) / rd * 100:>8.1f}%')

# -*- coding: utf-8 -*-
"""Carga da BU Hyper no Q2 (ficou de fora porque a Base Unificada do Yuri so cobre
as verticais BR02/BR09).

Receita: aba 'Hyper' do P&L Gerencial jun26 v2 (cliente x PEP x mes, liquida).
Custo  : folha do BR07 (CLTs Custo Gerencial SAP + PJs valor liquido).
Fonte marcada: 'Hyper Q2' — rastreavel e sem se misturar com a carga do Yuri.
Uso: python _sobe_hyper_q2.py [--apply]
"""
import os, sys, json
from datetime import datetime
import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PL = '2026 dados/FCamara - P&L Gerencial - jun26 v2.xlsx'
FONTE = 'Hyper Q2'
FD = 'FCamara - P&L Gerencial - jun26 v2.xlsx | aba Hyper (receita) + CLTs/PJs BR07 (custo)'
KEYS = ['fonte', 'fonte_dados', 'periodo', 'empresa', 'pep', 'pep_base', 'nome_pessoa', 'nome_cliente',
        'vertical', 'apuracao_manual', 'tipos', 'receita', 'custo_rateado', 'classificacao',
        'tipo_contrato', 'billable_category', 'no_hierarquia']


def s(v):
    v = '' if v is None else str(v).strip()
    return None if v in ('', 'nan', 'NaN', 'None') else v


rows = []

# ---------- receita ----------
h = pd.read_excel(PL, sheet_name='Hyper', header=3)
h.columns = [str(c).strip() for c in h.columns]
vistos, mescols = [], []
for i, c in enumerate(h.columns):
    if c.startswith('2026-'):
        k = c[:7]
        if k not in vistos:
            vistos.append(k); mescols.append((k, i))
h = h[h['CLIENTE'].notna()].copy()
h['cli'] = h['CLIENTE'].astype(str).str.strip()
h = h[~h['cli'].str.upper().str.endswith('TOTAL') & ~h['cli'].str.upper().str.startswith('TOTAL')]
tot_rec = {}
for _, r in h.iterrows():
    pep = s(r.get('Projeto (PEP)'))
    for k, i in mescols:
        if k not in ('2026-04', '2026-05', '2026-06'):
            continue
        v = pd.to_numeric(r.iloc[i], errors='coerce')
        if pd.isna(v) or float(v) == 0:
            continue
        x = {kk: None for kk in KEYS}
        x.update({'fonte': FONTE, 'fonte_dados': FD, 'periodo': k, 'empresa': 'BR07 Hyper',
                  'pep': pep, 'pep_base': pep.split('.')[0] if pep else None,
                  'nome_cliente': r['cli'], 'vertical': 'BU Hyper',
                  'apuracao_manual': 'Ecossistema',        # padrao da carteira Hyper na base
                  'tipos': s(r.get('ID SF')), 'receita': round(float(v), 2)})
        rows.append(x)
        tot_rec[k] = tot_rec.get(k, 0) + float(v)
print('receita Hyper Q2:', {k: round(v) for k, v in sorted(tot_rec.items())}, '| total', f"{sum(tot_rec.values()):,.0f}")

# ---------- custo: folha do BR07 ----------
tot_cus = {}
cl = pd.read_excel(PL, sheet_name='CLTs', header=None)
for r in range(1, len(cl)):
    c = cl.iat[r, 25]
    if not (isinstance(c, (pd.Timestamp, datetime)) and c.year == 2026 and 4 <= c.month <= 6):
        continue
    if str(cl.iat[r, 24]).strip().upper() != 'BR07':
        continue
    v = pd.to_numeric(cl.iat[r, 21], errors='coerce')
    if pd.isna(v) or float(v) == 0:
        continue
    per = c.strftime('%Y-%m')
    x = {kk: None for kk in KEYS}
    x.update({'fonte': FONTE, 'fonte_dados': FD, 'periodo': per, 'empresa': 'BR07 Hyper',
              'nome_pessoa': s(cl.iat[r, 1]), 'nome_cliente': s(cl.iat[r, 29]) or 'Time Hyper',
              'vertical': 'BU Hyper', 'classificacao': 'custo', 'tipo_contrato': 'CLT',
              'billable_category': s(cl.iat[r, 26]), 'pep': s(cl.iat[r, 31]),
              'pep_base': (s(cl.iat[r, 31]) or '').split('.')[0] or None,
              'custo_rateado': -round(abs(float(v)), 2)})
    rows.append(x)
    tot_cus[per] = tot_cus.get(per, 0) + float(v)
pj = pd.read_excel(PL, sheet_name='PJs', header=None)
for r in range(1, len(pj)):
    c = pj.iat[r, 7]
    if not (isinstance(c, (pd.Timestamp, datetime)) and c.year == 2026 and 4 <= c.month <= 6):
        continue
    if str(pj.iat[r, 6]).strip().upper() != 'BR07':
        continue
    v = pd.to_numeric(pj.iat[r, 5], errors='coerce')
    if pd.isna(v) or float(v) == 0:
        continue
    per = c.strftime('%Y-%m')
    x = {kk: None for kk in KEYS}
    x.update({'fonte': FONTE, 'fonte_dados': FD, 'periodo': per, 'empresa': 'BR07 Hyper',
              'nome_pessoa': s(pj.iat[r, 1]), 'nome_cliente': 'Time Hyper',
              'vertical': 'BU Hyper', 'classificacao': 'custo', 'tipo_contrato': 'PJ',
              'billable_category': s(pj.iat[r, 8]),
              'custo_rateado': -round(abs(float(v)), 2)})
    rows.append(x)
    tot_cus[per] = tot_cus.get(per, 0) + float(v)
print('custo Hyper Q2  :', {k: round(v) for k, v in sorted(tot_cus.items())}, '| total', f"{sum(tot_cus.values()):,.0f}")
print(f'\nlinhas a inserir: {len(rows)} | margem implicita: {sum(tot_rec.values()) - sum(tot_cus.values()):,.0f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

r = httpx.delete(f'{url}/rest/v1/nova_base', params={'fonte': f'eq.{FONTE}'},
                 headers={**H, 'Prefer': 'count=exact'}, timeout=300)
print('carga anterior removida:', r.headers.get('content-range'))
ids = []
for i in range(0, len(rows), 500):
    r = httpx.post(f'{url}/rest/v1/nova_base', json=rows[i:i + 500],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert r.status_code in (200, 201), f'{r.status_code} {r.text[:300]}'
    ids += [x['id'] for x in r.json()]
json.dump(ids, open('_backup_insert_hyper_q2_ids.json', 'w'))
print('inseridas:', len(ids))

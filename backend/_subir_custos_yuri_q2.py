# -*- coding: utf-8 -*-
"""Sobe os custos que faltam pro dash bater com a apuração do Yuri:
1) Pessoas não faturáveis por vertical (abas Finance/Retail/Logistics/Health/Multisector)
2) Despesas Gerais Verticais (agregado vertical×mês)
Ambos como fonte='Metas Custos Q2', classificacao='custo' (entram na margem como Custo Outro)."""
import os, json
import pandas as pd

os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
BASE = r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais'
MESCOL = {'abr/26': '2026-04', 'mai/26': '2026-05', 'jun/26': '2026-06'}
KEYS = ['fonte', 'fonte_dados', 'periodo', 'empresa', 'nome_pessoa', 'nome_cliente',
        'vertical', 'apuracao_manual', 'tipos', 'receita', 'custo_rateado', 'classificacao', 'pep', 'pep_base']

rows = []
# ---- 1) nao faturaveis: uma linha pessoa x mes ----
p1 = os.path.join(BASE, 'Pessoas nao faturaveis por vertical - Q2Y26.xlsx')
tot_nf = {}
for bu in ('Finance', 'Retail', 'Logistics', 'Health', 'Multisector'):
    d = pd.read_excel(p1, sheet_name=bu)
    d.columns = [str(c).strip() for c in d.columns]
    for _, r in d.iterrows():
        nome = str(r.get('Nome', '')).strip()
        if not nome or nome.lower() in ('nan', 'total'):
            continue
        emp = str(r.get('Empresa', '')).strip()
        for col, per in MESCOL.items():
            v = pd.to_numeric(r.get(col), errors='coerce')
            if pd.isna(v) or v == 0:
                continue
            x = {k: None for k in KEYS}
            x.update({'fonte': 'Metas Custos Q2',
                      'fonte_dados': 'Pessoas nao faturaveis por vertical - Q2Y26.xlsx',
                      'periodo': per, 'empresa': {'BR02': 'BR02 FCamara', 'BR09': 'BR09 NextGen', 'BR07': 'BR07 Hyper'}.get(emp, emp or None),
                      'nome_pessoa': nome, 'nome_cliente': 'Estrutura não faturável',
                      'vertical': 'BU ' + bu, 'classificacao': 'custo',
                      'custo_rateado': round(-abs(float(v)), 2)})
            rows.append(x)
            tot_nf[bu] = tot_nf.get(bu, 0) + float(v)
print('nao faturaveis por BU (Q2):', {k: round(v) for k, v in tot_nf.items()})

# ---- 2) despesas gerais: agregado vertical x mes ----
p2 = os.path.join(BASE, 'Despesas Gerais Verticais - 2Q26.xlsx')
d2 = pd.read_excel(p2, sheet_name='Planilha1')
d2.columns = [str(c).strip() for c in d2.columns]
d2['v'] = d2['vertical'].astype(str).str.strip()
d2['m'] = pd.to_numeric(d2['FiscalPeriod'], errors='coerce')
d2['val'] = pd.to_numeric(d2['AmountInCompanyCodeCurrency'], errors='coerce').fillna(0)
# o arquivo traz CompanyCode — agrupar por ele tambem, pra nao subir sem empresa
d2['cc'] = d2['CompanyCode'].astype(str).str.strip()
g = d2[d2['m'].isin([4, 5, 6])].groupby(['v', 'm', 'cc'])['val'].sum()
tot_dg = {}
for (v, m, cc), val in g.items():
    if val == 0 or v.lower() in ('nan', ''):
        continue
    x = {k: None for k in KEYS}
    x.update({'fonte': 'Metas Custos Q2',
              'fonte_dados': 'Despesas Gerais Verticais - 2Q26.xlsx',
              'periodo': f'2026-0{int(m)}',
              'empresa': {'BR02': 'BR02 FCamara', 'BR09': 'BR09 NextGen', 'BR07': 'BR07 Hyper'}.get(cc, cc or None),
              'nome_pessoa': None, 'nome_cliente': 'Despesas gerais da BU',
              'vertical': 'BU ' + v, 'classificacao': 'custo',
              'custo_rateado': round(-abs(float(val)), 2)})
    rows.append(x)
    tot_dg[v] = tot_dg.get(v, 0) + float(val)
print('despesas gerais por BU (Q2):', {k: round(v) for k, v in tot_dg.items()})
print('linhas a inserir:', len(rows), '| custo total:', f"{sum(x['custo_rateado'] for x in rows):,.0f}")

# limpa carga anterior (idempotente)
r = httpx.delete(f'{url}/rest/v1/nova_base', params={'fonte': 'eq.Metas Custos Q2'},
                 headers={**H, 'Prefer': 'count=exact'}, timeout=300)
print('delete carga anterior:', r.status_code, r.headers.get('content-range'))

ids = []
for i in range(0, len(rows), 500):
    r = httpx.post(f'{url}/rest/v1/nova_base', json=rows[i:i + 500],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert r.status_code in (200, 201), f'{r.status_code} {r.text[:300]}'
    ids += [x['id'] for x in r.json()]
print('inseridas:', len(ids))
json.dump(ids, open('_backup_insert_metas_custos_q2_ids.json', 'w'))

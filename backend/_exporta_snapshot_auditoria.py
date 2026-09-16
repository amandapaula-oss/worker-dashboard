# -*- coding: utf-8 -*-
"""Exporta um snapshot da base e das fontes para a auditoria de receita (16/09).
Tudo em CSV no scratchpad, para os agentes lerem sem bater no Supabase.
"""
import os
import re

import pandas as pd

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
       r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
       r'\scratchpad\auditoria')
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
load_creds()
import main

# ---------- 1. base processada (o que o dash mostra) ----------
df = main._get_nova_base().copy()
for c in ('receita', 'custo_rateado', 'horas', 'margem', 'valor_liquido', 'despesa', 'custo'):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
cols = [c for c in ['id', 'periodo', 'empresa', 'fonte', 'fonte_familia', 'fonte_dados',
                    'nome_pessoa', 'nome_cliente', 'pep', 'pep_base', 'vertical', 'apuracao',
                    'apuracao_manual', 'no_hierarquia', 'macro_area', 'area', 'classificacao',
                    'billable_category', 'tipos', 'tipo_contrato', 'agrupador', 'receita',
                    'custo_rateado', 'horas'] if c in df.columns]
base = df[cols]
base.to_csv(os.path.join(OUT, 'base_processada.csv'), index=False, encoding='utf-8')
print(f'base_processada.csv: {len(base)} linhas, {len(cols)} colunas')

rec = base[(base['receita'] != 0) & (~base['fonte'].astype(str).isin(['Budget', 'de para']))]
rec.to_csv(os.path.join(OUT, 'receita.csv'), index=False, encoding='utf-8')
print(f'receita.csv: {len(rec)} linhas | R$ {rec["receita"].sum():,.2f}')
r26 = rec[rec['periodo'].astype(str).str.startswith('2026')]
print(f'   2026: {len(r26)} linhas | R$ {r26["receita"].sum():,.2f}')

# ---------- 2. Controle Augusto (dono do Hyper) ----------
AUG = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
       r'\30. FP&A NOVO\03. Apresentações\2026\5. Comitê de Finanças - Fechamentos FP&A'
       r'\00. Fechamento FP&A\6. Contabilidade\Receita 2Q26_V2.xlsx')
raw = pd.read_excel(AUG, sheet_name='Hyper - Serviços', header=None)
hdr = 1
cols_a = {str(raw.iloc[hdr, j]).strip(): j for j in range(raw.shape[1])}
mj = {v.strftime('%Y-%m'): j for j, v in
      ((j, raw.iloc[hdr, j]) for j in range(raw.shape[1])) if hasattr(v, 'strftime')}
linhas = []
for i in range(hdr + 1, len(raw)):
    p = str(raw.iloc[i, cols_a['Projeto (PEP)']] or '').strip()
    if not p.upper().startswith('BR'):
        continue
    for m, j in mj.items():
        v = pd.to_numeric(raw.iloc[i, j], errors='coerce')
        linhas.append({'periodo': m, 'cliente': str(raw.iloc[i, cols_a['CLIENTE']]).strip(),
                       'pep': p, 'id_sf': str(raw.iloc[i, cols_a.get('ID SF', 0)]).strip(),
                       'valor': 0.0 if pd.isna(v) else round(float(v), 2)})
pd.DataFrame(linhas).to_csv(os.path.join(OUT, 'fonte_hyper_augusto.csv'), index=False,
                            encoding='utf-8')
print(f'fonte_hyper_augusto.csv: {len(linhas)} celulas')

# ---------- 3. racional do Yuri (dono do BR02), Q2 ----------
y = pd.read_excel(AUG, sheet_name='Racional Ajustado FP&A - Metas', header=0)
y.columns = [str(c).strip() for c in y.columns]
y['periodo'] = pd.to_datetime(y['Competência'], errors='coerce').dt.strftime('%Y-%m')
y['valor'] = pd.to_numeric(y['Valor Liquido :)'], errors='coerce').fillna(0)
keep = [c for c in ['periodo', 'EMPRESA', 'TIPO', 'NOME CLIENTE', 'PEP', 'PROFISSIONAL',
                    'valor', 'HRS APROVADAS', 'Vertical', 'Profit Center'] if c in y.columns]
y[keep].to_csv(os.path.join(OUT, 'fonte_racional_yuri_q2.csv'), index=False, encoding='utf-8')
print(f'fonte_racional_yuri_q2.csv: {len(y)} linhas | R$ {y["valor"].sum():,.2f}')

# ---------- 4. contabilidade 1Q26 ----------
CT = os.path.join(os.environ['TEMP'], 'receita_contabil_1q26_copy.xlsx')
CT_COLS = ['cod_empresa', 'projeto', 'tipo_prj', 'elemento_pep', 'nome_prj',
           'cod_cliente', 'nome_cliente', 'centro_lucro', 'responsavel']
raw = pd.read_excel(CT, sheet_name='Planilha1', header=None)
hdr = c0 = None
for i in range(min(8, len(raw))):
    linha = raw.iloc[i].astype(str).str.strip()
    hit = linha[linha == 'Cod Empresa']
    if len(hit):
        hdr, c0 = i, hit.index[0]
        break
ct = raw.iloc[hdr + 1:].rename(columns={c0 + k: n for k, n in enumerate(CT_COLS)})
from datetime import datetime
mes_cols = {}
for i in (max(0, hdr - 1), hdr):
    for j, v in raw.iloc[i].items():
        if isinstance(v, datetime):
            mes_cols.setdefault(v.strftime('%Y-%m'), j)
for m, j in mes_cols.items():
    ct[m] = -pd.to_numeric(ct[j], errors='coerce').fillna(0.0)   # sinal invertido: credito
for c in CT_COLS:
    ct[c] = (ct[c].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
             .replace({'nan': '', 'None': ''}))
ct = ct[ct['projeto'] != '']
ct[CT_COLS + sorted(mes_cols)].to_csv(os.path.join(OUT, 'fonte_contabilidade_1q26.csv'),
                                      index=False, encoding='utf-8')
print(f'fonte_contabilidade_1q26.csv: {len(ct)} projetos')

# ---------- 5. cadastro mestre de PEPs do SAP ----------
m = pd.read_excel(os.path.join(DIR, 'pep_master_sap.xlsx'), sheet_name='PEPs')
m.columns = [str(c).strip() for c in m.columns]
m.to_csv(os.path.join(OUT, 'pep_master_sap.csv'), index=False, encoding='utf-8')
print(f'pep_master_sap.csv: {len(m)} linhas')

# ---------- 6. resumos prontos ----------
r26 = rec[rec['periodo'].astype(str).str.startswith('2026')]
(r26.groupby(['periodo', 'fonte'])['receita'].agg(['sum', 'count'])
 .to_csv(os.path.join(OUT, 'resumo_fonte_mes.csv'), encoding='utf-8'))
(r26.groupby(['periodo', 'vertical'])['receita'].sum()
 .to_csv(os.path.join(OUT, 'resumo_bu_mes.csv'), encoding='utf-8'))
(r26.groupby(['nome_cliente', 'periodo'])['receita'].sum().unstack(fill_value=0)
 .to_csv(os.path.join(OUT, 'resumo_cliente_mes.csv'), encoding='utf-8'))
print('resumos salvos em', OUT)

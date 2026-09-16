# -*- coding: utf-8 -*-
"""Corrige o PEP das linhas de receita de Hyper (fontes 'Hyper' e 'Hyper Q2') usando a
FONTE dona do stream: aba "Hyper - Serviços" do `Receita 2Q26_V2.xlsx` (Controle Augusto),
que traz CLIENTE | Projeto (PEP) | jan..jun/26.

Regra da Amanda (16/09): "os projetos de hyper estao corretos naquela base de hyper".
Casamento por cliente + mes + valor (o par mais forte); depois cliente + mes quando o
cliente so tem um projeto no mes; depois cliente com projeto unico no semestre.
NAO mexe em valor, BU, cliente nem em linha de custo — so em pep/pep_base.

Uso: python _pep_hyper_da_fonte.py [--apply]
"""
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

import pandas as pd

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx
import main

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
FONTE = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\03. Apresentações\2026\5. Comitê de Finanças - Fechamentos FP&A'
         r'\00. Fechamento FP&A\6. Contabilidade\Receita 2Q26_V2.xlsx')
MESES = [f'2026-{m:02d}' for m in range(1, 7)]
ALIAS = {'BANCO BV': 'VOTORANTIM', 'BANCO VOTORANTIM': 'VOTORANTIM', 'BV': 'VOTORANTIM',
         'DE TOKYO MITSUBISHI UFJ BRASIL': 'MUFG', 'MUFG BRASIL': 'MUFG',
         'DEXCO': 'DURATEX', 'VIA VAREJO': 'CASAS BAHIA', 'CASAS BAHIA': 'CASAS BAHIA',
         'ULTRAPAR': 'ULTRA', 'IRANI PAPEL E EMBALAGEM': 'IRANI', 'ALLPARK': 'ESTAPAR',
         'CIRION TECHNOLOGIES DO BRASIL': 'CIRION', 'DEL TORO LOAN SERVICING INC': 'DEL TORO US AZ',
         'MULTIPLAN EMPREENDIMENTOS IMOBILIARIOS': 'MULTIPLAN', 'RED HAT BRASIL': 'RED HAT',
         'LIGGA TELECOMUNICACOES': 'LIGGA', 'TOKIO MARINE SEGURADORA': 'TOKIO MARINE',
         'MERCADO LIVRE MERCADO PAGO': 'MERCADO LIVRE', 'OURINVEST': 'OURIBANK',
         'MULTIPLAN EMPREENDIMENTOS IMOBILIA': 'MULTIPLAN'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO|FL\s*\d+|SP|MG)\b', ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return ALIAS.get(v, v)


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE') else p.replace('BRO', 'BR0').split('.')[0]


# ---------- fonte ----------
raw = pd.read_excel(FONTE, sheet_name='Hyper - Serviços', header=None)
hdr = 1
cols = {str(raw.iloc[hdr, j]).strip(): j for j in range(raw.shape[1])}
cj, pj = cols['CLIENTE'], cols['Projeto (PEP)']
mj = {v.strftime('%Y-%m'): j for j, v in
      ((j, raw.iloc[hdr, j]) for j in range(raw.shape[1])) if hasattr(v, 'strftime')}
linhas = []
for i in range(hdr + 1, len(raw)):
    p = raiz(raw.iloc[i, pj])
    if not p.startswith('BR'):
        continue
    for m, j in mj.items():
        v = pd.to_numeric(raw.iloc[i, j], errors='coerce')
        linhas.append({'pep': p, 'cli': npn(raw.iloc[i, cj]), 'periodo': m,
                       'valor': 0.0 if pd.isna(v) else round(float(v), 2)})
f = pd.DataFrame(linhas)
print(f'fonte: {f["pep"].nunique()} projetos | {f["cli"].nunique()} clientes | '
      f'R$ {f["valor"].sum():,.2f}')

por_val = defaultdict(set)      # (cliente, mes, valor) -> peps
por_cli_mes = defaultdict(set)  # (cliente, mes) -> peps com valor no mes
por_cli = defaultdict(set)      # cliente -> peps com valor no semestre
for r in linhas:
    if abs(r['valor']) > 0.005:
        por_val[(r['cli'], r['periodo'], abs(r['valor']))].add(r['pep'])
        por_cli_mes[(r['cli'], r['periodo'])].add(r['pep'])
        por_cli[r['cli']].add(r['pep'])

# ---------- nossas linhas ----------
df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
hy = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(MESES)
        & df['fonte'].astype(str).str.startswith('Hyper')].copy()
hy['cli'] = hy['nome_cliente'].map(npn)
hy['raiz'] = hy['pep'].map(raiz)
print(f'nossas linhas de receita Hyper: {len(hy)} | R$ {hy["receita"].sum():,.2f}')

plano, sem, stats = [], [], defaultdict(lambda: [0, 0.0])
for _, x in hy.iterrows():
    k, per, v = x['cli'], x['periodo'], round(abs(x['receita']), 2)
    pep = motivo = None
    for cand, m in ((por_val.get((k, per, v)), 'cliente + mes + valor exato'),
                    (por_cli_mes.get((k, per)), 'cliente + mes (projeto unico no mes)'),
                    (por_cli.get(k), 'cliente com projeto unico no semestre')):
        if cand and len(cand) == 1 and not pep:
            pep, motivo = next(iter(cand)), m
    if not pep:
        sem.append(x)
        continue
    if pep == x['raiz']:
        stats['ja estava certo'][0] += 1
        stats['ja estava certo'][1] += x['receita']
        continue
    plano.append((x, pep, motivo))
    stats[motivo][0] += 1
    stats[motivo][1] += x['receita']

print('\n=== resultado ===')
for m, (q, v) in sorted(stats.items(), key=lambda t: -t[1][1]):
    print(f'   {m:42} {q:>4} linhas  R$ {v:>13,.2f}')
print(f'   {"sem casamento na fonte":42} {len(sem):>4} linhas  '
      f'R$ {sum(x["receita"] for x in sem):>13,.2f}')

print('\n  PEP que muda (top 25 por valor):')
for x, p, m in sorted(plano, key=lambda t: -t[0]['receita'])[:25]:
    print(f'   {x["periodo"]} {str(x["nome_cliente"])[:24]:24} {x["receita"]:>11,.0f} '
          f'{str(x["raiz"] or "(sem PEP)"):16} -> {p:16} [{m}]')
if sem:
    d = pd.DataFrame([(str(x['nome_cliente']), x['periodo'], x['receita'], x['raiz']) for x in sem],
                     columns=['cliente', 'periodo', 'receita', 'pep_hoje'])
    print(f'\n  sem casamento ({len(sem)}):')
    print(d.groupby(['cliente', 'pep_hoje'])['receita'].agg(['sum', 'count'])
          .sort_values('sum', ascending=False).head(15).round(0).to_string())

json.dump([{'id': int(x['id']), 'de': x['raiz'], 'para': p, 'motivo': m,
            'cliente': str(x['nome_cliente']), 'periodo': x['periodo'],
            'receita': float(x['receita'])} for x, p, m in plano],
          open(os.path.join(DIR, '_plano_pep_hyper_fonte.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

ids = sorted({int(x['id']) for x, _, _ in plano})
bk = []
for i in range(0, len(ids), 100):
    ch = ','.join(str(v) for v in ids[i:i + 100])
    bk += httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({ch})'},
                    headers=H, timeout=120).json()
json.dump(bk, open(os.path.join(DIR, '_backup_pep_hyper_fonte.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'backup: _backup_pep_hyper_fonte.json ({len(bk)} linhas)')

feitas = 0
for x, p, m in plano:
    fd = str(x.get('fonte_dados') or '')
    fd = re.sub(r' \| PEP[^|]*', '', fd)[:380] + ' | PEP: base de Hyper (Controle Augusto)'
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
                    json={'pep': p, 'pep_base': p, 'fonte_dados': fd[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

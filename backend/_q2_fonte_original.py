# -*- coding: utf-8 -*-
"""Q2/26 — regra da Paola (16/09): linha em BR02 com PEP de BR07 nao veio da fonte
original; vale so a informacao da fonte dona (a base de Hyper, "Controle Augusto",
aba "Hyper - Serviços" do Receita 2Q26_V2.xlsx).

Para cada linha nossa cuja empresa difere da empresa do PEP, o script separa:
  (a) DUPLICATA  — a fonte dona TEM esse projeto nesse mes: a linha sai
  (b) PEP ERRADO — a fonte dona NAO tem: a receita e' da empresa da linha, so o PEP
      esta trocado; troca pelo projeto equivalente (o SAP tem o mesmo projeto nas duas
      empresas, ex.: Komatsu BR07CLP00205 = BR02CLP00857) ou apaga o PEP
  (c) OUTRAS EMPRESAS (BR04 Nacao, BR05 SGA, BR09 NextGen) — so relatorio: nao
      carregamos essas fontes, apagar a linha perderia receita de verdade

Uso: python _q2_fonte_original.py [--apply]
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
Q2 = ['2026-04', '2026-05', '2026-06']
Q1 = ['2026-01', '2026-02', '2026-03']
PERIODOS = Q1 if '--q1' in sys.argv else Q2


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE') else p.replace('BRO', 'BR0').split('.')[0]


# ---------- fonte dona do BR07 ----------
raw = pd.read_excel(FONTE, sheet_name='Hyper - Serviços', header=None)
hdr = 1
cols = {str(raw.iloc[hdr, j]).strip(): j for j in range(raw.shape[1])}
cj, pj = cols['CLIENTE'], cols['Projeto (PEP)']
mj = {v.strftime('%Y-%m'): j for j, v in
      ((j, raw.iloc[hdr, j]) for j in range(raw.shape[1])) if hasattr(v, 'strftime')}
ALIAS = {'BANCO BV': 'VOTORANTIM', 'BV': 'VOTORANTIM', 'DE TOKYO MITSUBISHI UFJ BRASIL': 'MUFG',
         'MUFG BRASIL': 'MUFG', 'DEXCO': 'DURATEX', 'VIA VAREJO': 'CASAS BAHIA',
         'ULTRAPAR': 'ULTRA', 'ALLPARK': 'ESTAPAR', 'OURINVEST': 'OURIBANK',
         'CIRION TECHNOLOGIES DO BRASIL': 'CIRION', 'RED HAT BRASIL': 'RED HAT'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO|FL\s*\d+|SP|MG)\b', ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return ALIAS.get(v, v)


hyper = {}          # (pep, mes) -> valor
hyper_cli = {}      # pep -> cliente (normalizado) na fonte
for i in range(hdr + 1, len(raw)):
    p = raiz(raw.iloc[i, pj])
    if not p.startswith('BR'):
        continue
    hyper_cli.setdefault(p, npn(raw.iloc[i, cj]))
    for m, j in mj.items():
        v = pd.to_numeric(raw.iloc[i, j], errors='coerce')
        if pd.notna(v) and abs(float(v)) > 0.005:
            hyper[(p, m)] = hyper.get((p, m), 0) + float(v)
print(f'fonte de Hyper: {len({k[0] for k in hyper})} projetos com valor')

# ---------- projeto equivalente na outra empresa (mesmo nome no cadastro do SAP) ----------
mestre = pd.read_excel(os.path.join(DIR, 'pep_master_sap.xlsx'), sheet_name='PEPs')
mestre.columns = [str(c).strip() for c in mestre.columns]
mestre['r'] = mestre['pep'].map(raiz)
desc = {}
for _, r in mestre.drop_duplicates('r').iterrows():
    d = str(r['descricao'] or '').strip().upper()
    if d and not d.startswith('LC'):
        desc.setdefault(d, []).append(r['r'])
equiv = {}          # pep -> pep da outra empresa com a MESMA descricao
for d, ps in desc.items():
    if len(ps) == 2:
        equiv[ps[0]], equiv[ps[1]] = ps[1], ps[0]

# ---------- nossas linhas ----------
df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
d = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(PERIODOS)
       & (~df['fonte'].astype(str).isin(['Budget', 'de para']))].copy()
d['raiz'] = d['pep'].map(raiz)
d['emp'] = d['empresa'].astype(str).str.extract(r'(BR\d\d)')[0].fillna('?')
d['emp_pep'] = d['raiz'].str.slice(0, 4)
x = d[(d['emp_pep'] != '') & (d['emp_pep'] != d['emp'])]

dup, troca, apaga, outras = [], [], [], []
for _, r in x.iterrows():
    if r['emp_pep'] == 'BR07' and r['emp'] != 'BR07':
        # so e' duplicata se a fonte tem esse projeto NO MES e para o MESMO cliente:
        # no Q1 as alocacoes do Ouribank estao com o PEP da RED HAT (typo do racional),
        # e sem essa trava a linha seria apagada como se fosse duplicidade do Hyper
        mesmo_cli = hyper_cli.get(r['raiz'], '') == npn(r['nome_cliente'])
        if (r['raiz'], r['periodo']) in hyper and mesmo_cli:
            dup.append(r)
        else:
            eq = equiv.get(r['raiz'])
            (troca if eq and eq.startswith(r['emp']) else apaga).append((r, eq))
    else:
        outras.append(r)

print(f'\n=== (a) DUPLICATA da fonte de Hyper — a linha sai: {len(dup)} | '
      f'R$ {sum(r["receita"] for r in dup):,.2f} ===')
for r in dup:
    v = hyper.get((r['raiz'], r['periodo']), 0)
    print(f'   id {int(r["id"])} {r["periodo"]} {str(r["nome_cliente"])[:26]:26} '
          f'{r["raiz"]:16} nossa {r["receita"]:>10,.2f} | fonte de Hyper {v:>10,.2f}')

print(f'\n=== (b) PEP de BR07 numa receita que a fonte NAO tem — troca pelo projeto '
      f'equivalente: {len(troca)} | R$ {sum(r["receita"] for r, _ in troca):,.2f} ===')
for r, eq in troca:
    print(f'   id {int(r["id"])} {r["periodo"]} {str(r["nome_cliente"])[:26]:26} '
          f'{r["raiz"]} -> {eq}  R$ {r["receita"]:,.2f}')
if apaga:
    print(f'\n=== (b2) sem equivalente na empresa da linha — PEP sai: {len(apaga)} | '
          f'R$ {sum(r["receita"] for r, _ in apaga):,.2f} ===')
    for r, _ in apaga:
        print(f'   id {int(r["id"])} {r["periodo"]} {str(r["nome_cliente"])[:26]:26} '
              f'{r["raiz"]}  R$ {r["receita"]:,.2f}')

print(f'\n=== (c) outras empresas (nao mexo — nao carregamos essas fontes): '
      f'{len(outras)} | R$ {sum(r["receita"] for r in outras):,.2f} ===')
if outras:
    o = pd.DataFrame(outras)
    print(o.groupby(['emp', 'emp_pep', 'nome_cliente'])['receita'].agg(['sum', 'count'])
          .sort_values('sum', ascending=False).round(2).to_string())

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

ids = [int(r['id']) for r in dup] + [int(r['id']) for r, _ in troca + apaga]
bk = httpx.get(f'{url}/rest/v1/nova_base',
               params={'select': '*', 'id': f'in.({",".join(map(str, ids))})'},
               headers=H, timeout=120).json()
json.dump(bk, open(os.path.join(DIR, '_backup_q2_fonte_original.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'backup: _backup_q2_fonte_original.json ({len(bk)} linhas)')

if dup:
    r = httpx.delete(f'{url}/rest/v1/nova_base',
                     params={'id': f'in.({",".join(str(int(x["id"])) for x in dup)})'},
                     headers=H, timeout=120)
    assert r.status_code in (200, 204), r.text[:200]
    print(f'removidas {len(dup)} linhas duplicadas')
for r, eq in troca:
    fd = re.sub(r' \| PEP[^|]*', '', str(r.get('fonte_dados') or ''))[:360]
    body = {'pep': eq, 'pep_base': eq,
            'fonte_dados': (fd + f' | PEP: {r["raiz"]}->{eq} (mesmo projeto no SAP, lado '
                                 f'{r["emp"]}) 16/09')[:500]}
    z = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(r["id"])}'}, json=body,
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert z.status_code in (200, 204), z.text[:200]
for r, _ in apaga:
    fd = re.sub(r' \| PEP[^|]*', '', str(r.get('fonte_dados') or ''))[:360]
    z = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(r["id"])}'},
                    json={'pep': None, 'pep_base': None,
                          'fonte_dados': (fd + ' | PEP de BR07 removido 16/09: nao vem da '
                                               'fonte original')[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert z.status_code in (200, 204), z.text[:200]
print(f'PEP trocado em {len(troca)} linhas | PEP apagado em {len(apaga)}')

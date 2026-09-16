# -*- coding: utf-8 -*-
"""Hyper: o projeto (PEP) passa a ser o do CONTROLE AUGUSTO — decisao da Amanda (16/09),
confirmada pela contabilidade (os codigos e valores da aba "Hyper - Serviços" do
Receita 2Q26_V2.xlsx sao os mesmos que a contabilidade lanca).

Nossa carga de Hyper veio do "Imputs Sales Boost - Hyper - Play.xlsx" (maio) e ficou com
codigos velhos: MUFG, por exemplo, tem o MESMO total (R$ 1.729.825) em tres projetos
diferentes (00098/00097/00034 no lugar de 00099/00203/00204).

Como funciona: para cada cliente x mes em que o NOSSO total e o do Augusto sao iguais
(ate R$ 1), as nossas linhas de receita daquele cliente/mes sao substituidas pelas linhas
do Augusto (um projeto por linha, com o valor dele). Receita, BU, empresa e apuracao
ficam iguais — muda so a quebra por projeto. Cliente x mes que NAO bate fica intacto e
entra no relatorio.

Uso: python _reconstroi_hyper_augusto.py [--apply]
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
AUG = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
       r'\30. FP&A NOVO\03. Apresentações\2026\5. Comitê de Finanças - Fechamentos FP&A'
       r'\00. Fechamento FP&A\6. Contabilidade\Receita 2Q26_V2.xlsx')
MESES = [f'2026-{m:02d}' for m in range(1, 7)]
ALIAS = {'BANCO BV': 'VOTORANTIM', 'BV': 'VOTORANTIM', 'DE TOKYO MITSUBISHI UFJ BRASIL': 'MUFG',
         'MUFG BRASIL': 'MUFG', 'DEXCO': 'DURATEX', 'VIA VAREJO': 'CASAS BAHIA',
         'ULTRAPAR': 'ULTRA', 'ALLPARK': 'ESTAPAR', 'OURINVEST': 'OURIBANK',
         'CIRION TECHNOLOGIES DO BRASIL': 'CIRION', 'RED HAT BRASIL': 'RED HAT',
         'DEL TORO LOAN SERVICING INC': 'DEL TORO US AZ', 'LIGGA TELECOMUNICACOES': 'LIGGA',
         'MULTIPLAN EMPREENDIMENTOS IMOBILIARIOS': 'MULTIPLAN',
         'MULTIPLAN EMPREENDIMENTOS IMOBILIA': 'MULTIPLAN',
         'TOKIO MARINE SEGURADORA': 'TOKIO MARINE', 'MERCADO LIVRE MERCADO PAGO': 'MERCADO LIVRE',
         'IRANI PAPEL E EMBALAGEM': 'IRANI', 'MULTIPLAN EMPREENDIMENTOS IMOBILIA': 'MULTIPLAN',
         'CIP NUCLEA': 'CIP', 'MULTIPLAN EMPREENDIMENTOS': 'MULTIPLAN',
         'MULTIPLAN EMPREENDIMENTOS IMOBILIARIOS S': 'MULTIPLAN'}   # nome truncado na nossa base


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO|FL\s*\d+|SP|MG)\b', ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return ALIAS.get(v, v)


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE') else p.replace('BRO', 'BR0').split('.')[0]


# ---------- Controle Augusto ----------
raw = pd.read_excel(AUG, sheet_name='Hyper - Serviços', header=None)
hdr = 1
cols = {str(raw.iloc[hdr, j]).strip(): j for j in range(raw.shape[1])}
cj, pj = cols['CLIENTE'], cols['Projeto (PEP)']
jid = cols.get('ID SF')
mj = {v.strftime('%Y-%m'): j for j, v in
      ((j, raw.iloc[hdr, j]) for j in range(raw.shape[1])) if hasattr(v, 'strftime')}
aug = []
for i in range(hdr + 1, len(raw)):
    p = raiz(raw.iloc[i, pj])
    if not p.startswith('BR'):
        continue
    for m, j in mj.items():
        v = pd.to_numeric(raw.iloc[i, j], errors='coerce')
        if pd.notna(v) and abs(float(v)) > 0.005:
            aug.append({'periodo': m, 'pep': p, 'cli_raw': str(raw.iloc[i, cj]).strip(),
                        'k': npn(raw.iloc[i, cj]), 'valor': round(float(v), 2),
                        'id_sf': '' if jid is None else str(raw.iloc[i, jid]).strip()})
a = pd.DataFrame(aug)
print(f'Controle Augusto: {len(a)} linhas | {a["pep"].nunique()} projetos | '
      f'R$ {a["valor"].sum():,.2f}')

# ---------- nossas linhas de receita de Hyper ----------
df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
hy = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(MESES)
        & df['fonte'].astype(str).str.startswith('Hyper')].copy()
hy['k'] = hy['nome_cliente'].map(npn)
hy['raiz'] = hy['pep'].map(raiz)
print(f'nossa base (receita Hyper): {len(hy)} linhas | R$ {hy["receita"].sum():,.2f}')

# ---------- compara cliente x mes ----------
A = a.groupby(['k', 'periodo'])['valor'].sum()
B = hy.groupby(['k', 'periodo'])['receita'].sum()
idx = A.index.union(B.index)
cmp = pd.DataFrame({'aug': A.reindex(idx, fill_value=0), 'nossa': B.reindex(idx, fill_value=0)})
cmp['dif'] = cmp['nossa'] - cmp['aug']
bate = cmp[cmp['dif'].abs() <= 1]
naobate = cmp[cmp['dif'].abs() > 1]
print(f'\ncliente x mes: {len(bate)} batem (rebuild) | {len(naobate)} nao batem (intactos)')

# ---------- monta o plano ----------
KEYS = ['fonte', 'fonte_dados', 'periodo', 'empresa', 'pep', 'pep_base', 'nome_pessoa',
        'nome_cliente', 'vertical', 'apuracao_manual', 'tipos', 'receita', 'custo_rateado',
        'classificacao', 'no_hierarquia', 'macro_area', 'area', 'horas', 'tipo_contrato',
        'billable_category', 'agrupador']
colunas_ok = set(httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'limit': '1'},
                           headers=H, timeout=60).json()[0]) - {'id', 'cpf'}
KEYS = [k for k in KEYS if k in colunas_ok]

sai_ids, entra, mudou = [], [], 0
for (k, per) in bate.index:
    nossas = hy[(hy['k'] == k) & (hy['periodo'] == per)]
    novas = a[(a['k'] == k) & (a['periodo'] == per)]
    if nossas.empty or novas.empty:
        continue
    # ja esta certo? mesmo conjunto de (pep, valor) -> nao mexe
    atual = sorted((r['raiz'], round(r['receita'], 2)) for _, r in nossas.iterrows())
    alvo = sorted((r['pep'], round(r['valor'], 2)) for _, r in novas.iterrows())
    if atual == alvo:
        continue
    mudou += 1
    modelo = nossas.sort_values('receita', ascending=False).iloc[0]
    sai_ids += [int(i) for i in nossas['id'].dropna()]
    for _, r in novas.iterrows():
        linha = {c: (None if pd.isna(modelo.get(c)) else modelo.get(c)) for c in KEYS}
        linha.update({'pep': r['pep'], 'pep_base': r['pep'], 'receita': float(r['valor']),
                      'custo_rateado': 0, 'horas': 0, 'nome_pessoa': None,
                      'tipos': (r['id_sf'] or None),
                      'fonte_dados': (f'Controle Augusto (aba Hyper - Serviços do Receita '
                                      f'2Q26_V2.xlsx) | projeto e valor da fonte | 16/09')[:500]})
        entra.append(linha)

print(f'\n=== plano ===')
print(f'   clientes x mes reescritos: {mudou}')
print(f'   linhas que saem: {len(sai_ids)} | R$ {hy[hy["id"].isin(sai_ids)]["receita"].sum():,.2f}')
print(f'   linhas que entram: {len(entra)} | R$ {sum(l["receita"] for l in entra):,.2f}')
dif = sum(l['receita'] for l in entra) - hy[hy['id'].isin(sai_ids)]['receita'].sum()
print(f'   diferenca de receita: R$ {dif:,.2f}  (tem que ser ~0)')

print('\n   exemplos (5 clientes):')
vistos = set()
for l in entra:
    kk = (l['nome_cliente'], l['periodo'])
    if kk[0] in vistos:
        continue
    vistos.add(kk[0])
    ant = hy[(hy['nome_cliente'] == l['nome_cliente']) & (hy['periodo'] == l['periodo'])]
    print(f'      {l["periodo"]} {str(l["nome_cliente"])[:26]:26} antes '
          f'{sorted(set(ant["raiz"]))} -> agora {l["pep"]} R$ {l["receita"]:,.2f}')
    if len(vistos) >= 5:
        break

if len(naobate):
    print(f'\n   NAO reescritos (nosso total != Augusto), top 15:')
    g = naobate.groupby(level=0)[['aug', 'nossa', 'dif']].sum().sort_values('dif', key=abs, ascending=False)
    for kk, x in g.head(15).iterrows():
        print(f'      {kk[:34]:34} augusto {x["aug"]:>12,.2f} | nossa {x["nossa"]:>12,.2f} | '
              f'dif {x["dif"]:>+12,.2f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

bk = []
for i in range(0, len(sai_ids), 100):
    ch = ','.join(map(str, sai_ids[i:i + 100]))
    bk += httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({ch})'},
                    headers=H, timeout=120).json()
json.dump(bk, open(os.path.join(DIR, '_backup_hyper_augusto_antes.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'backup: _backup_hyper_augusto_antes.json ({len(bk)} linhas)')

for i in range(0, len(sai_ids), 100):
    ch = ','.join(map(str, sai_ids[i:i + 100]))
    r = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({ch})'}, headers=H, timeout=120)
    assert r.status_code in (200, 204), r.text[:200]
ids = []
for i in range(0, len(entra), 500):
    r = httpx.post(f'{url}/rest/v1/nova_base', json=entra[i:i + 500],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert r.status_code in (200, 201), f'{r.status_code} {r.text[:300]}'
    ids += [z['id'] for z in r.json()]
json.dump(ids, open(os.path.join(DIR, '_backup_insert_hyper_augusto_ids.json'), 'w'))
print(f'removidas {len(sai_ids)} | inseridas {len(ids)}')

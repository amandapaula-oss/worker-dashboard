# -*- coding: utf-8 -*-
"""DESFAZ o alinhamento do Q1 a peca "Receita Contabil 1Q26" (feito em 16/09).

Motivo (Amanda, 21/09): a Visao BUs que os diretores enxergam de jan-mar deixou de bater
com a apuracao do Q1 que foi paga. O Henrique do Grupo Mult batia ao centavo
(R$ 11.733.281,39) e ficou R$ 978.594 fora. O Q2 NAO e' tocado.

Tres movimentos, todos a partir de _backup_q1_contabil_antes.json (1.430 linhas, 37 colunas):
  1. REPOE  os valores originais nas 1.353 linhas que foram reescaladas/renomeadas
  2. VOLTA  as 77 linhas que foram apagadas
  3. APAGA  as 59 linhas inseridas pela peca (fonte = "Receita Contábil 1Q26")

Uso: python _desfaz_q1_contabil.py [--apply]
"""
import json
import os
import sys

import pandas as pd

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
Q1 = ['2026-01', '2026-02', '2026-03']
FONTE_INSERIDA = 'Receita Contábil 1Q26'
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

bk = json.load(open(os.path.join(DIR, '_backup_q1_contabil_antes.json'), encoding='utf-8'))
bk = [x for x in bk if str(x.get('periodo')) in Q1]
por_id = {int(x['id']): x for x in bk}
print(f'backup: {len(bk)} linhas')

# o que existe hoje
ids = sorted(por_id)
vivas = {}
for i in range(0, len(ids), 150):
    ch = ','.join(map(str, ids[i:i + 150]))
    r = httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({ch})'},
                  headers=H, timeout=180)
    assert r.status_code == 200, r.text[:200]
    for y in r.json():
        vivas[int(y['id'])] = y
inseridas = httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'fonte': f'eq.{FONTE_INSERIDA}'},
                      headers=H, timeout=180).json()

CAMPOS = ['receita', 'pep', 'pep_base', 'no_hierarquia', 'vertical', 'apuracao_manual',
          'nome_cliente', 'empresa', 'fonte', 'fonte_dados', 'projeto', 'custo_rateado', 'horas']
repor, iguais = [], 0
for i, orig in por_id.items():
    atual = vivas.get(i)
    if atual is None:
        continue
    muda = {c: orig.get(c) for c in CAMPOS
            if c in orig and str(orig.get(c)) != str(atual.get(c))}
    if muda:
        repor.append((i, muda, float(atual.get('receita') or 0), float(orig.get('receita') or 0)))
    else:
        iguais += 1
voltar = [x for i, x in por_id.items() if i not in vivas]

v_rep = sum(o - a for _, _, a, o in repor)
v_volta = sum(float(x.get('receita') or 0) for x in voltar)
v_apaga = sum(float(x.get('receita') or 0) for x in inseridas)
print(f'\n=== plano ===')
print(f'   1. REPOR valor/PEP original  {len(repor):>5} linhas | efeito na receita R$ {v_rep:>+14,.2f}')
print(f'      (ja identicas ao backup:  {iguais:>5})')
print(f'   2. VOLTAR linhas apagadas    {len(voltar):>5} linhas | R$ {v_volta:>+14,.2f}')
print(f'   3. APAGAR linhas da peca     {len(inseridas):>5} linhas | R$ {-v_apaga:>+14,.2f}')
print(f'\n   efeito total no Q1: R$ {v_rep + v_volta - v_apaga:+,.2f}')

hoje = httpx.get(f'{url}/rest/v1/nova_base', params={'select': 'periodo,receita,empresa'},
                 headers=H, timeout=300).json()
h = pd.DataFrame(hoje)
h['receita'] = pd.to_numeric(h['receita'], errors='coerce').fillna(0)
q1_hoje = h[h['periodo'].astype(str).isin(Q1)]['receita'].sum()
print(f'   Q1 bruto na tabela: R$ {q1_hoje:,.2f} -> R$ {q1_hoje + v_rep + v_volta - v_apaga:,.2f}')

print(f'\n   --- 10 maiores reposicoes ---')
for i, muda, a, o in sorted(repor, key=lambda z: -abs(z[3] - z[2]))[:10]:
    orig = por_id[i]
    print(f'      id {i:>7} {str(orig.get("nome_cliente"))[:24]:24} {orig.get("periodo")} '
          f'{a:>13,.2f} -> {o:>13,.2f}   campos: {",".join(muda)[:46]}')
print(f'\n   --- linhas que voltam, por cliente ---')
vv = pd.DataFrame(voltar)
if len(vv):
    vv['receita'] = pd.to_numeric(vv['receita'], errors='coerce').fillna(0)
    print(vv.groupby([vv['nome_cliente'].astype(str).str[:26], 'fonte'])['receita']
          .agg(['size', 'sum']).sort_values('sum', ascending=False).head(10).round(2).to_string())
print(f'\n   --- linhas que saem (inseridas pela peca) ---')
ii = pd.DataFrame(inseridas)
if len(ii):
    ii['receita'] = pd.to_numeric(ii['receita'], errors='coerce').fillna(0)
    print(ii.groupby(ii['nome_cliente'].astype(str).str[:30])['receita']
          .sum().sort_values(ascending=False).head(8).round(2).to_string())

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

json.dump({'repostas': [i for i, _, _, _ in repor],
           'voltaram': [x['id'] for x in voltar],
           'apagadas': [x['id'] for x in inseridas]},
          open(os.path.join(DIR, '_desfazer_q1_executado.json'), 'w'), indent=1)

for i, muda, _, _ in repor:
    z = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{i}'}, json=muda,
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert z.status_code in (200, 204), f'{i}: {z.text[:200]}'
print(f'   1. repostas: {len(repor)} linhas')

cols = set(httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'limit': '1'},
                     headers=H, timeout=60).json()[0]) - {'apuracao'}
novas = [{k: v for k, v in x.items() if k in cols and k != 'id'} for x in voltar]
n = 0
for i in range(0, len(novas), 300):
    z = httpx.post(f'{url}/rest/v1/nova_base', json=novas[i:i + 300],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert z.status_code in (200, 201), f'{z.status_code} {z.text[:300]}'
    n += len(z.json())
print(f'   2. voltaram: {n} linhas')

ids_del = [int(x['id']) for x in inseridas]
for i in range(0, len(ids_del), 100):
    ch = ','.join(map(str, ids_del[i:i + 100]))
    z = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({ch})'}, headers=H, timeout=180)
    assert z.status_code in (200, 204), z.text[:200]
print(f'   3. apagadas: {len(ids_del)} linhas')
print('\npronto. rode _run_sync_calculada.py em seguida.')

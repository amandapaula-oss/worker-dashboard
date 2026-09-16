# -*- coding: utf-8 -*-
"""Abril/26: a fonte do Yuri repete linhas INTEIRAS (copia/cola espelhada) e a nossa carga
somou os dois lancamentos. Efeito: receita dobrada para 21 alocacoes.

Deteccao (independente, nao confia no achado): pega os grupos de linha-cheia repetida na
fonte (mesma competencia, empresa, tipo, cliente, PEP, profissional, valor E horas) e
confere, pessoa a pessoa, se a NOSSA base traz o valor multiplicado. Confere ainda:
  - o valor unitario aparece sozinho nos outros meses (mai/jun) -> nao e' catch-up
  - o custo da pessoa em abril e' de um mes normal -> receita dobrou, custo nao

Correcao: a linha da nossa base passa a valer UM lancamento (valor unitario x quantas
alocacoes distintas a pessoa tem de verdade). Quando a carga manteve 2 linhas, apaga a extra.

Uso: python _corrige_dup_abril_racional.py [--apply]
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
SNAP = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
        r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
        r'\scratchpad\auditoria')
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
MES = '2026-04'


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    return ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE') else p.replace('BRO', 'BR0').split('.')[0]


# ---------- 1. grupos repetidos na FONTE ----------
y = pd.read_csv(os.path.join(SNAP, 'fonte_racional_yuri_q2.csv'))
y.columns = [str(c).strip() for c in y.columns]
chave = ['periodo', 'EMPRESA', 'TIPO', 'NOME CLIENTE', 'PEP', 'PROFISSIONAL', 'valor',
         'HRS APROVADAS']
chave = [c for c in chave if c in y.columns]
g = y.groupby(chave, dropna=False).size().reset_index(name='n')
rep = g[(g['n'] > 1) & (g['periodo'] == MES) & (g['valor'].abs() > 0.005)]
print(f'fonte do Yuri: {len(rep)} grupos de linha-cheia repetida em {MES} | '
      f'excesso R$ {(rep["valor"] * (rep["n"] - 1)).sum():,.2f}')
outros = g[(g['n'] > 1) & (g['periodo'] != MES) & (g['valor'].abs() > 0.005)]
print(f'   (para comparar: mai+jun tem {len(outros)} grupos, '
      f'excesso R$ {(outros["valor"] * (outros["n"] - 1)).sum():,.2f})')

# valor unitario da mesma pessoa/PEP nos outros meses (teste do catch-up)
unit_outros = defaultdict(set)
for _, r in y[(y['periodo'] != MES) & (y['valor'].abs() > 0.005)].iterrows():
    unit_outros[(npn(r['PROFISSIONAL']), raiz(r['PEP']))].add(round(float(r['valor']), 2))

# ---------- 2. nossas linhas ----------
rows, off = [], 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,fonte,nome_cliente,nome_pessoa,pep,pep_base,'
                                    'receita,horas,custo_rateado,vertical,fonte_dados',
                          'periodo': f'eq.{MES}', 'fonte': 'eq.racionais',
                          'order': 'id', 'limit': '1000', 'offset': str(off)},
                  headers=H, timeout=90).json()
    rows += r
    if len(r) < 1000:
        break
    off += 1000
n = pd.DataFrame(rows)
n['receita'] = pd.to_numeric(n['receita'], errors='coerce').fillna(0)
n['k'] = n['nome_pessoa'].map(npn)
n['r'] = n['pep'].map(raiz)
print(f'nossa base: {len(n)} linhas de racionais em {MES}')

# ---------- 3. cruza ----------
plano_meta, plano_del, nao_casou = [], [], []
for _, x in rep.iterrows():
    k, p = npn(x['PROFISSIONAL']), raiz(x['PEP'])
    v, cnt = round(float(x['valor']), 2), int(x['n'])
    # casa por PESSOA + valor, nao por PEP: o PEP da fonte as vezes esta errado e nos ja
    # corrigimos na base (Ouribank: fonte BR07CLP00015 = RED HAT, nossa base BR02CLP00015)
    nossas = n[(n['k'] == k) & (n['r'] == p)]
    if nossas.empty and k:
        cand = n[n['k'] == k]
        nossas = cand[(cand['receita'].sub(v * cnt).abs() < 0.02)
                      | (cand['receita'].sub(v).abs() < 0.02)]
    if nossas.empty:
        nao_casou.append((x['NOME CLIENTE'], x['PROFISSIONAL'], v, cnt, 'sem linha nossa'))
        continue
    tot = nossas['receita'].sum()
    esperado_certo = v                      # 1 lancamento
    esperado_dobrado = v * cnt
    sozinho_em_outro_mes = v in unit_outros.get((k, p), set())
    if abs(tot - esperado_dobrado) < 0.02 and len(nossas) == 1:
        plano_meta.append((nossas.iloc[0], v, cnt, x['NOME CLIENTE'], sozinho_em_outro_mes))
    elif abs(tot - esperado_dobrado) < 0.02 and len(nossas) == cnt:
        manter = nossas.iloc[0]
        for _, extra in nossas.iloc[1:].iterrows():
            plano_del.append((extra, v, x['NOME CLIENTE'], sozinho_em_outro_mes))
    elif abs(tot - esperado_certo) < 0.02:
        pass                                 # a carga ja deduplicou: nada a fazer
    else:
        nao_casou.append((x['NOME CLIENTE'], x['PROFISSIONAL'], v, cnt,
                          f'nossa soma {tot:,.2f} != {esperado_certo:,.2f} nem {esperado_dobrado:,.2f}'))

exc_meta = sum(l['receita'] - v for l, v, c, cli, s in plano_meta)
exc_del = sum(l['receita'] for l, v, cli, s in plano_del)
print(f'\n=== plano ===')
print(f'   linhas com o valor DOBRADO (vira o unitario): {len(plano_meta)} | '
      f'excesso R$ {exc_meta:,.2f}')
print(f'   linhas extras a APAGAR: {len(plano_del)} | excesso R$ {exc_del:,.2f}')
print(f'   TOTAL a tirar da receita: R$ {exc_meta + exc_del:,.2f}')
print(f'   grupos que nao casaram (nao serao tocados): {len(nao_casou)}')

print(f'\n   {"cliente":24} {"pessoa":30} {"hoje":>12} {"fica":>12} {"unit. em mai/jun":>17}')
for l, v, c, cli, s in sorted(plano_meta, key=lambda t: -t[0]['receita']):
    print(f'   {str(cli)[:24]:24} {str(l["nome_pessoa"])[:30]:30} {l["receita"]:>12,.2f} '
          f'{v:>12,.2f} {"sim" if s else "-":>17}   id {l["id"]}')
for l, v, cli, s in plano_del:
    print(f'   {str(cli)[:24]:24} {str(l["nome_pessoa"])[:30]:30} {l["receita"]:>12,.2f} '
          f'{"APAGA":>12} {"sim" if s else "-":>17}   id {l["id"]}')
if nao_casou:
    print('\n   nao casaram:')
    for cli, pes, v, c, por in nao_casou[:12]:
        print(f'      {str(cli)[:24]:24} {str(pes)[:28]:28} {v:>11,.2f} x{c}  ({por})')

# ---------- 4. teste do custo (receita dobrou, custo nao) ----------
ids = [int(l['id']) for l, *_ in plano_meta] + [int(l['id']) for l, *_ in plano_del]
pessoas = {npn(l['nome_pessoa']) for l, *_ in plano_meta}
print('\n=== teste do custo: a pessoa teve custo dobrado em abril? ===')
base = pd.read_csv(os.path.join(SNAP, 'base_processada.csv'))
base['k'] = base['nome_pessoa'].map(npn)
cst = base[base['k'].isin(pessoas) & base['periodo'].isin(['2026-03', '2026-04', '2026-05'])]
cst = cst.groupby(['k', 'periodo'])['custo_rateado'].sum().unstack(fill_value=0)
if len(cst):
    cst['abr/mai'] = (cst.get('2026-04', 0) / cst.get('2026-05', 1)).round(2)
    print(cst.head(12).round(0).to_string())

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

bk = []
for i in range(0, len(ids), 100):
    ch = ','.join(map(str, ids[i:i + 100]))
    bk += httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({ch})'},
                    headers=H, timeout=120).json()
json.dump(bk, open(os.path.join(DIR, '_backup_dup_abril_racional.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'backup: _backup_dup_abril_racional.json ({len(bk)} linhas)')

for l, v, c, cli, s in plano_meta:
    fd = (str(l.get('fonte_dados') or '')[:330] +
          f' | dedup 16/09: a fonte repetia a linha {c}x, receita era {l["receita"]:.2f}')
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(l["id"])}'},
                    json={'receita': float(v), 'fonte_dados': fd[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), r.text[:200]
if plano_del:
    ch = ','.join(str(int(l['id'])) for l, *_ in plano_del)
    r = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({ch})'}, headers=H, timeout=120)
    assert r.status_code in (200, 204), r.text[:200]
print(f'corrigidas {len(plano_meta)} linhas | apagadas {len(plano_del)} | '
      f'receita -R$ {exc_meta + exc_del:,.2f}')

# -*- coding: utf-8 -*-
"""ESTAPAR no Q2: a Amanda reviu a decisao de 15/09 ("mantem o do Yuri") e em 16/09
decidiu **manter o do Augusto** — coerente com a regra da Paola (linha em BR02 com
projeto que e' de outra fonte nao vem da fonte original).

Hoje o racional lanca ESTAPAR em BR02CLP00103.1.1 com exatamente os valores da base de
Hyper (115.763,31 / 115.763,31 / 92.610,65). Entao:
  - saem as 3 linhas do racional (BR02CLP00103)
  - voltam as 3 linhas de Hyper (BR0CLP00143), como no Controle Augusto
Receita do Q2 nao muda: e' o mesmo valor trocando de fonte/empresa.
A linha BR05CLP00078 (SGA - MS Infra, 23.136/25.427/25.427) NAO e' tocada: e' outro
contrato, e a fonte de SGA nao esta carregada.

Uso: python _estapar_volta_augusto.py [--apply]
"""
import json
import os
import sys

import pandas as pd

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
SAI = [100908, 100909, 100910]              # racionais ESTAPAR BR02CLP00103 (Q2)
VOLTA = [('2026-04', 115763.31), ('2026-05', 115763.31), ('2026-06', 92610.65)]


def get(p):
    r = httpx.get(f'{url}/rest/v1/nova_base', params=p, headers=H, timeout=120)
    assert r.status_code == 200, r.text[:200]
    return r.json()


sai = get({'select': '*', 'id': f'in.({",".join(map(str, SAI))})', 'order': 'id'})
print(f'saem {len(sai)} linhas do racional | R$ {sum(x["receita"] for x in sai):,.2f}')
for x in sai:
    print(f'   id {x["id"]} {x["periodo"]} {x["fonte"]} {x["pep"]} R$ {x["receita"]:,.2f}')

# modelo: uma linha de receita de Hyper Q2 ja reconstruida pelo Augusto
modelo = get({'select': '*', 'fonte': 'eq.Hyper Q2', 'periodo': 'eq.2026-04',
              'receita': 'gt.1000', 'limit': '1'})[0]
cols = set(modelo) - {'id', 'cpf', 'apuracao'}   # 'apuracao' e coluna gerada no banco
entra = []
for per, val in VOLTA:
    linha = {c: modelo.get(c) for c in cols}
    linha.update({'periodo': per, 'receita': val, 'custo_rateado': 0, 'horas': 0,
                  'nome_cliente': 'ESTAPAR', 'nome_pessoa': None,
                  'pep': 'BR0CLP00143', 'pep_base': 'BR0CLP00143',
                  'vertical': 'BU Multisector', 'tipos': None,
                  'fonte_dados': 'Controle Augusto (aba Hyper - Serviços do Receita 2Q26_V2.xlsx)'
                                 ' | ESTAPAR volta pro lado Hyper — decisao da Amanda 16/09'})
    entra.append(linha)
print(f'\nvoltam {len(entra)} linhas de Hyper | R$ {sum(l["receita"] for l in entra):,.2f}')
print(f'efeito liquido na receita: R$ {sum(l["receita"] for l in entra) - sum(x["receita"] for x in sai):,.2f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

json.dump(sai, open(os.path.join(DIR, '_backup_del_estapar_racional_q2.json'), 'w',
                    encoding='utf-8'), ensure_ascii=False)
r = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(map(str, SAI))})'},
                 headers=H, timeout=120)
assert r.status_code in (200, 204), r.text[:200]
r = httpx.post(f'{url}/rest/v1/nova_base', json=entra,
               headers={**H, 'Prefer': 'return=representation'}, timeout=120)
assert r.status_code in (200, 201), f'{r.status_code} {r.text[:300]}'
json.dump([z['id'] for z in r.json()],
          open(os.path.join(DIR, '_backup_insert_estapar_hyper_q2_ids.json'), 'w'))
print(f'removidas {len(SAI)} | inseridas {len(r.json())}')

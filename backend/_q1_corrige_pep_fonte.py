# -*- coding: utf-8 -*-
"""Q1/26 — corrige PEP pelas FONTES donas (regra da Amanda/Paola, 16/09):

1. OURIBANK, 67 linhas do racional (T&E, BR02): o racional do Yuri traz BR07CLP00015,
   que no SAP e' 212852_REDHAT_RH_DETRAN (RED HAT). A receita e' "Alocação Ourinvest",
   BR02CLP00015 — a contabilidade lanca exatamente R$ 450.518,86 + 434.994,23 +
   431.470,82 = 1.316.983,91, o mesmo total das nossas linhas. Typo de empresa no PEP.
2. UNIMED NACIONAL, 3 linhas da aba Play (BR02): receberam hoje o PEP BR07CLP00123
   (Hyper). Linha de BR02 nao leva projeto de BR07 — o PEP sai.
3. UNIMED NACIONAL, 2 linhas de "ajustes gerencial" (R$ 138.845/mes): idem — a fonte de
   Hyper diz que BR07CLP00123 vale R$ 25.284,86/mes, entao esse valor nao e' desse
   projeto. O PEP sai.

Nenhuma receita muda: so pep/pep_base.
Uso: python _q1_corrige_pep_fonte.py [--apply]
"""
import json
import os
import re
import sys

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
IDS_SEM_PEP = [22407, 22408, 22409, 36546, 36547]


def get(params):
    r = httpx.get(f'{url}/rest/v1/nova_base', params=params, headers=H, timeout=120)
    assert r.status_code == 200, r.text[:200]
    return r.json()


ouri = [x for x in get({'select': 'id,periodo,nome_cliente,pep,receita,fonte_dados',
                        'pep': 'like.BR07CLP00015*', 'order': 'id', 'limit': '500'})
        if str(x['periodo']) < '2026-04']
print(f'1. OURIBANK: {len(ouri)} linhas | R$ {sum(x["receita"] or 0 for x in ouri):,.2f} '
      f'-> BR02CLP00015 (mesmo sufixo)')
sem = get({'select': 'id,periodo,nome_cliente,fonte,pep,receita',
           'id': f'in.({",".join(map(str, IDS_SEM_PEP))})', 'order': 'id'})
print(f'2/3. PEP de BR07 fora de lugar: {len(sem)} linhas | '
      f'R$ {sum(x["receita"] or 0 for x in sem):,.2f} -> PEP removido')
for x in sem:
    print(f'     id {x["id"]} {x["periodo"]} {x["fonte"]:14} {x["pep"]} R$ {x["receita"]:,.2f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

ids = [x['id'] for x in ouri] + [x['id'] for x in sem]
bk = []
for i in range(0, len(ids), 100):
    bk += get({'select': '*', 'id': f'in.({",".join(map(str, ids[i:i + 100]))})'})
json.dump(bk, open(os.path.join(DIR, '_backup_q1_corrige_pep_fonte.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'backup: _backup_q1_corrige_pep_fonte.json ({len(bk)} linhas)')

n = 0
for x in ouri:
    novo = str(x['pep']).replace('BR07CLP00015', 'BR02CLP00015')
    fd = re.sub(r' \| PEP[^|]*', '', str(x.get('fonte_dados') or ''))[:360]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': novo, 'pep_base': 'BR02CLP00015',
                          'fonte_dados': (fd + ' | PEP: BR07CLP00015 (RED HAT) era typo do '
                                               'racional; Ouribank e BR02CLP00015 (contabilidade)')[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), r.text[:200]
    n += 1
for x in sem:
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': None, 'pep_base': None,
                          'fonte_dados': 'PEP de BR07 removido 16/09: linha nao vem da base de Hyper'},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), r.text[:200]
    n += 1
print(f'atualizadas: {n} linhas')

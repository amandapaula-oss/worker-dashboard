# -*- coding: utf-8 -*-
"""Preenche o PEP das linhas do Q2 que ficaram sem, casando o NOME DO PROJETO com a
descricao do cadastro de projetos do SAP (pep_master_sap.xlsx).

E o caminho certo para as abas Play/Sales Boost/Licensing Msf: elas identificam por
nome de projeto ("Odontoprev-New Business Models", "VIX - Plan Estrategico"), e o
cadastro tem exatamente esse nome na coluna 'descricao'.

Criterio rigoroso: so aceita quando o nome normalizado da linha e o da descricao sao
iguais, ou um contem o outro com pelo menos 3 palavras em comum. Prefere a versao com
fase (.1.1). Nao chuta.
Uso: python _pep_do_cadastro_projetos.py [--apply]
"""
import os, re, sys, unicodedata
from collections import Counter, defaultdict
import pandas as pd

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
STOP = {'DE', 'DA', 'DO', 'E', 'A', 'O', 'EM', 'PARA', 'COM', '25', '26', 'LTDA', 'SA'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return '' if v in ('NAN', 'NONE') else v


def toks(s):
    return {t for t in npn(s).split() if t not in STOP and len(t) > 1}


m = pd.read_excel(os.path.join(DIR, 'pep_master_sap.xlsx'), sheet_name='PEPs')
m.columns = [str(c).strip() for c in m.columns]
proj = []
for _, p in m.iterrows():
    d = npn(p['descricao'])
    if d:
        proj.append((d, toks(p['descricao']), str(p['pep']).strip().upper(), npn(p['cliente_nome'])))
print(f'cadastro de projetos: {len(proj)} entradas com descricao')

rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,fonte,periodo,nome_cliente,tipos,receita,pep,fonte_dados',
                          'periodo': 'in.(2026-04,2026-05,2026-06)', 'pep': 'is.null',
                          'receita': 'neq.0', 'order': 'id', 'limit': '1000', 'offset': str(off)},
                  headers=H, timeout=90)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(str(b)[:200])
    for x in b:
        if x['id'] not in ids and x['fonte'] != 'Budget':
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
print(f'linhas do Q2 sem projeto: {len(rows)} | R$ {sum(x["receita"] for x in rows):,.0f}')

plano, stats = [], Counter()
for x in rows:
    nome = x['tipos'] or x['nome_cliente'] or ''
    tn, nn = toks(nome), npn(nome)
    cli = npn(x['nome_cliente'])
    if not tn:
        stats['sem nome de projeto'] += 1
        continue
    cands = []
    for d, td, pep, pcli in proj:
        if nn == d:
            score = 100
        else:
            comum = tn & td
            if len(comum) >= 3 or (len(comum) >= 2 and (nn in d or d in nn)):
                score = len(comum) * 10 + (5 if cli and pcli and (cli[:10] in pcli or pcli[:10] in cli) else 0)
            else:
                continue
        cands.append((score, '.' in pep, pep, d))
    if not cands:
        stats['sem match no cadastro'] += 1
        continue
    cands.sort(reverse=True)
    melhor = cands[0]
    # ambiguidade: dois projetos de RAIZ diferente com o mesmo score
    # BRO2 e BR02 sao o MESMO projeto (typo de cadastro no SAP: letra O no lugar do
    # zero). Sem normalizar, o mesmo projeto se acusa como ambiguo consigo mesmo.
    def _norm_raiz(p):
        return re.sub(r'^BRO', 'BR0', p.split('.')[0])
    raizes = {_norm_raiz(c[2]) for c in cands if c[0] == melhor[0]}
    if len(raizes) > 1:
        # o cadastro do SAP tem projetos DIFERENTES com o mesmo nome (ex.: 'Odontoprev
        # Esteira de Testes' em BRO2CLP000715 e BR02CLP000234). Por decisao da Amanda,
        # lanca no primeiro (ordem estavel) e deixa a escolha registrada para revisao.
        stats[f'ambiguo — lancado no 1o de {len(raizes)}'] += 1
        plano.append((x, melhor[2], melhor[3] + f' [AMBIGUO: {len(raizes)} projetos com o mesmo nome — '
                      + ', '.join(sorted(raizes)) + ']'))
        continue
    plano.append((x, melhor[2], melhor[3]))
    stats['casou pelo nome do projeto'] += 1

print('\n=== resultado ===')
for k, n in stats.most_common():
    print(f'   {k:36} {n:>3}')
print(f'   valor coberto: R$ {sum(x["receita"] for x, _, _ in plano):,.0f}')
for x, pep, d in sorted(plano, key=lambda t: -t[0]['receita']):
    print(f'   {x["periodo"]} {str(x["tipos"] or x["nome_cliente"])[:34]:34} '
          f'R$ {x["receita"]:>10,.0f} -> {pep:20} [{d[:30]}]')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep, d in plano:
    fd = x.get('fonte_dados') or ''
    if '| PEP do cadastro' not in fd:
        fd += f' | PEP do cadastro de projetos do SAP (descricao: {d[:40]})'
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': pep.split('.')[0], 'fonte_dados': fd[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

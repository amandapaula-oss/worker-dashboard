# -*- coding: utf-8 -*-
"""Q1: a fonte 'Play' e a fonte 'P&L Gerencial Ecossistema' carregam a MESMA receita.
O lado Eco vem arredondado em reais inteiros e as vezes com OUTRO nome de cliente
(Track&Field no Play x TFSPORTS no Eco), o que escondeu a colisao.

Deteccao independente: para cada linha do 'P&L Gerencial Ecossistema', procura no 'Play'
o mesmo mes com valor que arredonda para o mesmo inteiro (diferenca < R$ 1,00), casando
por cliente normalizado OU pelo proprio valor.

Fica o lado PLAY (bate com a fonte dona: projetos BR02 reais em DC029 na contabilidade);
sai o lado Eco (copia arredondada atribuida a BR08 Dojo, empresa que nao tem esses
clientes na peca da contabilidade).

Uso: python _corrige_dup_play_eco.py [--apply]
"""
import json
import os
import re
import sys
import unicodedata

import pandas as pd

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
ALIAS = {'TFSPORTS': 'TRACK FIELD', 'T F': 'TRACK FIELD', 'TRACKFIELD': 'TRACK FIELD',
         'MINHAS PROTECOES': 'MP', 'ODONTOPREV': 'ODONTOPREV', 'ELFA': 'ELFA'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO)\b', ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return ALIAS.get(v, v)


def pega(fonte):
    out, off = [], 0
    while True:
        r = httpx.get(f'{url}/rest/v1/nova_base',
                      params={'select': 'id,periodo,empresa,fonte,fonte_dados,nome_cliente,'
                                        'pep,receita,vertical,apuracao_manual,no_hierarquia',
                              'fonte': f'eq.{fonte}', 'order': 'id',
                              'limit': '1000', 'offset': str(off)},
                      headers=H, timeout=90).json()
        out += r
        if len(r) < 1000:
            break
        off += 1000
    d = pd.DataFrame(out)
    if len(d):
        d['receita'] = pd.to_numeric(d['receita'], errors='coerce').fillna(0)
        d['k'] = d['nome_cliente'].map(npn)
    return d


play = pega('Play')
eco = pega('P&L Gerencial Ecossistema')
play = play[play['receita'] != 0]
eco = eco[eco['receita'] != 0]
print(f"Play: {len(play)} linhas | R$ {play['receita'].sum():,.2f}")
print(f"P&L Gerencial Ecossistema: {len(eco)} linhas | R$ {eco['receita'].sum():,.2f}")
print(f"   empresas no Eco: {eco['empresa'].value_counts().to_dict()}")

# compara por CLIENTE x MES: no Play o mesmo cliente vem quebrado por projeto
gp = play.groupby(['k', 'periodo'])['receita'].sum()
ge = eco.groupby(['k', 'periodo'])['receita'].sum()
pares, sobra = [], []
for (k, per), vale in ge.items():
    valp = gp.get((k, per))
    if valp is not None and abs(valp - vale) < 1.0:
        linhas_e = eco[(eco['k'] == k) & (eco['periodo'] == per)]
        linhas_p = play[(play['k'] == k) & (play['periodo'] == per)]
        for _, e in linhas_e.iterrows():
            pares.append((e, linhas_p.iloc[0]))
    else:
        for _, e in eco[(eco['k'] == k) & (eco['periodo'] == per)].iterrows():
            sobra.append(e)

# 2a passada: linha a linha, para quem o total do cliente nao fechou (ex.: Track&Field,
# que no Play aparece tambem como 'T&F', entao o total do cliente nao bate mas a linha bate)
resto, usados = [], set()
for e in sobra:
    cand = play[(play['periodo'] == e['periodo']) & (~play['id'].isin(usados))
                & (play['receita'].sub(e['receita']).abs() < 1.0)]
    mesmo = cand[cand['k'] == e['k']]
    escolha = mesmo if len(mesmo) else cand
    if len(escolha):
        pl = escolha.iloc[0]
        usados.add(pl['id'])
        pares.append((e, pl))
    else:
        resto.append(e)
sobra = resto

print(f'\n=== pares Eco x Play (mesmo mes, valor identico ate R$ 1,00): {len(pares)} ===')
print(f'   {"mes":9} {"cliente (Eco)":26} {"cliente (Play)":26} {"Eco":>12} {"Play (cli/mes)":>14}')
tot = 0
for e, p in sorted(pares, key=lambda t: -t[0]['receita']):
    tot += e['receita']
    print(f'   {e["periodo"]}  {str(e["nome_cliente"])[:26]:26} {str(p["nome_cliente"])[:26]:26} '
          f'{e["receita"]:>12,.2f} {gp.get((e["k"], e["periodo"]), 0):>14,.2f}   id Eco {e["id"]}')
print(f'   TOTAL duplicado (lado Eco): R$ {tot:,.2f}')
if len(sobra):
    print(f'\n   linhas do Eco SEM par no Play (ficam): {len(sobra)} | '
          f'R$ {sum(x["receita"] for x in sobra):,.2f}')
    for x in sorted(sobra, key=lambda t: -t['receita'])[:10]:
        print(f'      {x["periodo"]} {str(x["nome_cliente"])[:30]:30} {x["empresa"]:16} '
              f'{x["receita"]:>12,.2f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

ids = [int(e['id']) for e, _ in pares]
bk = httpx.get(f'{url}/rest/v1/nova_base',
               params={'select': '*', 'id': f'in.({",".join(map(str, ids))})'},
               headers=H, timeout=120).json()
json.dump(bk, open(os.path.join(DIR, '_backup_del_dup_play_eco.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
r = httpx.delete(f'{url}/rest/v1/nova_base',
                 params={'id': f'in.({",".join(map(str, ids))})'}, headers=H, timeout=120)
assert r.status_code in (200, 204), r.text[:200]
print(f'\nbackup: _backup_del_dup_play_eco.json ({len(bk)} linhas)')
print(f'removidas {len(ids)} linhas do lado Eco | receita -R$ {tot:,.2f}')

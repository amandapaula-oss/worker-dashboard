# -*- coding: utf-8 -*-
"""Sobe as abas de receita que faltavam no Q2 (Licensing Hyper, Play, Sales Boost e
Licensing Msf): R$ 5.941.419, conferido ao centavo contra o proprio P&L.

Cada aba vira uma fonte propria — da para achar, auditar e remover sem tocar no resto.
Uso: python _sobe_abas_q2.py [--apply]
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
KEYS = ['fonte', 'fonte_dados', 'periodo', 'empresa', 'pep', 'pep_base', 'nome_pessoa',
        'nome_cliente', 'vertical', 'apuracao_manual', 'tipos', 'receita', 'custo_rateado',
        'classificacao', 'no_hierarquia']
# de onde veio cada aba (para o fonte_dados) e como o P&L trata cada uma
META = {
    'Licensing Hyper Q2': ('FCamara - P&L Gerencial - jun26 v2.xlsx | aba Licensing Hyper (r14)',
                           'BR07 Hyper', 'BU Hyper', 'Ecossistema', 'DC009 Licensing Hyper'),
    'Play Q2': ('FCamara - P&L Gerencial - jun26 v2.xlsx | aba Play (receita liquida)',
                'BR02 FCamara', '', 'Ecossistema', 'DC029 FC Consult. New Rev'),
    'Sales Boost Q2': ('FCamara - P&L Gerencial - jun26 v2.xlsx | aba Sales Boost',
                       'BR02 FCamara', '', 'Ecossistema', 'DC040 FC Consult. B. Sales'),
    'Licensing Msf Q2': ('FCamara - P&L Gerencial - jun26 v2.xlsx | aba Licensing Msf',
                         'BR02 FCamara', 'BU Others', 'Ecossistema', 'DC009 Licensing Hyper'),
}
# BU por cliente quando a aba nao diz (o pipeline ainda pode remapear pelo cadastro)
BU_CLIENTE = {'ODONTOPREV': 'BU Health', 'TRACK&FIELD': 'BU Retail', 'T&F': 'BU Retail',
              'NITA': 'BU Multisector', 'VIX': 'BU Logistics', 'RODOBENS': 'BU Multisector',
              'ADCOS': 'BU Health', 'FUTEBOLCARD': 'BU Multisector', 'DANONE': 'BU Health',
              'BAXTER': 'BU Health', 'ENERGISA': 'BU Others', 'ELFA': 'BU Health'}

linhas = json.load(open(os.path.join(DIR, '_carga_abas_q2.json'), encoding='utf-8'))
rows = []
for x in linhas:
    fd, empresa, bu_pad, apur, nh = META[x['fonte']]
    cli = (x.get('cliente') or '').strip()
    proj = (x.get('projeto') or '').strip()
    bu = bu_pad
    if not bu:
        chave = re.sub(r'[^A-Z&]', '', cli.upper())
        for k, v in BU_CLIENTE.items():
            if k.replace('&', '') in chave.replace('&', ''):
                bu = v
                break
        bu = bu or 'BU Others'
    r = {k: None for k in KEYS}
    r.update({'fonte': x['fonte'], 'fonte_dados': fd, 'periodo': x['periodo'],
              'empresa': empresa, 'nome_cliente': cli or proj or x['fonte'],
              'vertical': bu, 'apuracao_manual': apur, 'no_hierarquia': nh,
              'tipos': proj or None, 'receita': round(float(x['valor']), 2)})
    rows.append(r)

print(f'linhas a inserir: {len(rows)} | receita R$ {sum(r["receita"] for r in rows):,.2f}')
por = defaultdict(float)
for r in rows:
    por[(r['fonte'], r['periodo'])] += r['receita']
for k in sorted(por):
    print(f'   {k[0]:22} {k[1]}  R$ {por[k]:>12,.2f}')
print('\n  por BU:', {k: round(v) for k, v in
                      sorted(((b, sum(r['receita'] for r in rows if r['vertical'] == b))
                              for b in {r['vertical'] for r in rows}), key=lambda t: -t[1])})

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

# limpa carga anterior dessas fontes (idempotente)
for fonte in META:
    r = httpx.delete(f'{url}/rest/v1/nova_base', params={'fonte': f'eq.{fonte}'},
                     headers={**H, 'Prefer': 'count=exact'}, timeout=300)
    assert r.status_code in (200, 204), r.text[:200]
ids = []
for i in range(0, len(rows), 500):
    r = httpx.post(f'{url}/rest/v1/nova_base', json=rows[i:i + 500],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert r.status_code in (200, 201), f'{r.status_code} {r.text[:300]}'
    ids += [z['id'] for z in r.json()]
json.dump(ids, open(os.path.join(DIR, '_backup_insert_abas_q2_ids.json'), 'w'))
print(f'\ninseridas: {len(ids)} linhas')

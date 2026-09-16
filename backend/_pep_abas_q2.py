# -*- coding: utf-8 -*-
"""Popula o PEP das 47 linhas novas (abas Licensing Hyper, Play, Sales Boost e
Licensing Msf), na mesma hierarquia de fontes usada no resto do Q2:

  1. PEP escrito na propria aba do P&L (a Sales Boost traz na coluna C)
  2. razao do SAP (WBSElementExternal) por valor + mes, e por cliente + mes
  3. cadastro mestre de PEPs do SAP, quando o cliente tem projeto unico
  4. historico da nossa base: mesmo cliente, outro mes

Uso: python _pep_abas_q2.py [--apply]
"""
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

import openpyxl
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
FONTES = ['Licensing Hyper Q2', 'Play Q2', 'Sales Boost Q2', 'Licensing Msf Q2']
RAZAO = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos\C - Razão P&L (SAP)'
         r'\C_Razao_PL_2026-01_a_2026-09_extraido_2026-09-04.xlsx')
PL = os.path.join(DIR, '2026 dados', 'FCamara - P&L Gerencial - jun26 v2.xlsx')


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO)\b', ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return '' if v in ('NAN', 'NONE') else v


def pep_ok(v):
    """extrai SO o codigo do PEP: a celula costuma vir como
    'BR02CLP000116.1.1 - ADCOS - FULL COMMERCE'"""
    m = re.match(r'^(BR\d{1,2}[A-Z]{2,4}\d+(?:\.\d+)*)', str(v or '').strip().upper())
    return m.group(1) if m else None


def raiz(p):
    return str(p or '').split('.')[0]


# ---------- 1. PEP escrito na aba Sales Boost ----------
pep_por_cliente_aba = {}
wb = openpyxl.load_workbook(PL, data_only=True)
ws = wb['Sales Boost']
for r in range(6, 22):
    p = pep_ok(ws.cell(r, 3).value)
    cli = ws.cell(r, 5).value
    if p and cli:
        pep_por_cliente_aba.setdefault(npn(cli), p)
wb.close()
print(f'PEP na aba Sales Boost: {len(pep_por_cliente_aba)} clientes -> {list(pep_por_cliente_aba.items())[:3]}')

# ---------- 2. razao do SAP ----------
por_val, por_cli = defaultdict(set), defaultdict(set)
wbz = openpyxl.load_workbook(RAZAO, read_only=True)
wsz = wbz[wbz.sheetnames[0]]
for row in wsz.iter_rows(min_row=2, values_only=True):
    p = pep_ok(row[27])
    if not p:
        continue
    try:
        if int(str(row[4]).strip()) != 2026:
            continue
        per = f'2026-{int(str(row[5]).strip()):02d}'
    except (TypeError, ValueError):
        continue
    v = row[11]
    if v is not None:
        try:
            por_val[(per, round(abs(float(v)), 2))].add(p)
        except (TypeError, ValueError):
            pass
    if row[21]:
        por_cli[npn(row[21])].add(p)
wbz.close()
print(f'razao SAP: {len(por_val)} chaves valor-mes, {len(por_cli)} clientes')

# ---------- 3. cadastro mestre ----------
mestre = pd.read_excel(os.path.join(DIR, 'pep_master_sap.xlsx'), sheet_name='PEPs')
mestre.columns = [str(c).strip() for c in mestre.columns]
cad = defaultdict(set)
for _, r in mestre.iterrows():
    if pd.notna(r['cliente_nome']):
        p = pep_ok(r['pep'])
        if p:
            cad[npn(r['cliente_nome'])].add(p)

# ---------- 4. historico da base ----------
df = main._get_nova_base()
d = df[df['periodo'].astype(str).str.startswith('2026')].copy()
d['receita'] = pd.to_numeric(d['receita'], errors='coerce').fillna(0)
hist = defaultdict(Counter)
for _, x in d[(d['receita'] != 0) & d['pep'].notna()].iterrows():
    hist[npn(x['nome_cliente'])][str(x['pep'])] += 1

# ---------- linhas novas ----------
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,fonte,nome_cliente,tipos,receita,pep,fonte_dados',
                          'fonte': f'in.({",".join(chr(34) + f + chr(34) for f in FONTES)})',
                          'order': 'id', 'limit': '1000', 'offset': str(off)}, headers=H, timeout=90)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(str(b)[:200])
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
print(f'\nlinhas novas: {len(rows)} | com PEP hoje: {sum(1 for x in rows if x["pep"])}')


def escolhe(cands):
    if not cands:
        return None
    if len({raiz(p) for p in cands}) == 1:
        com_fase = [p for p in cands if '.' in p]
        return sorted(com_fase or list(cands))[0]
    return None


plano, stats = [], Counter()
for x in rows:
    cli = npn(x['nome_cliente'])
    pep = motivo = None
    if cli in pep_por_cliente_aba:
        pep, motivo = pep_por_cliente_aba[cli], 'PEP escrito na aba'
    if not pep:
        pep = escolhe(por_val.get((x['periodo'], round(abs(float(x['receita'])), 2))))
        motivo = 'razao SAP: valor+mes'
    if not pep and cli:
        pep = escolhe(por_cli.get(cli))
        motivo = 'razao SAP: cliente'
    if not pep and cli:
        pep = escolhe(cad.get(cli))
        motivo = 'cadastro mestre: projeto unico do cliente'
    if not pep and cli and hist.get(cli):
        c = hist[cli]
        if len({raiz(p) for p in c}) == 1:
            pep, motivo = c.most_common(1)[0][0], 'historico da base (mesmo cliente)'
    if not pep:
        stats['sem PEP'] += 1
        continue
    plano.append((x, pep, motivo))
    stats[motivo] += 1

print('\n=== resultado ===')
for k, n in stats.most_common():
    print(f'   {k:44} {n:>3}')
for x, p, m in sorted(plano, key=lambda t: -t[0]['receita'])[:14]:
    print(f'   {x["periodo"]} {str(x["nome_cliente"])[:30]:30} {x["receita"]:>11,.0f} -> {p:20} [{m}]')
sem = [x for x in rows if x['id'] not in {y['id'] for y, _, _ in plano}]
if sem:
    print(f'\n   seguem sem PEP ({len(sem)}, R$ {sum(x["receita"] for x in sem):,.0f}):')
    for k, n in Counter(str(x['nome_cliente'])[:34] for x in sem).most_common(8):
        print(f'      {k:36} {n}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep, motivo in plano:
    fd = x.get('fonte_dados') or ''
    if '| PEP:' not in fd:          # idempotente: rodar de novo nao acrescenta de novo
        fd += f' | PEP: {motivo}'
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': raiz(pep), 'fonte_dados': fd[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

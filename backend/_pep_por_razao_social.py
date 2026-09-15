# -*- coding: utf-8 -*-
"""Ultima rodada: usa o CADASTRO MESTRE DE PEPs DO SAP (pep_master_sap.xlsx) para
descobrir a RAZAO SOCIAL de cada cliente pendente (ESTAPAR = ALLPARK, DURATEX = DEXCO...)
e, com ela, achar a receita no razao do SAP.

Era isso que faltava: eu procurava 'ESTAPAR' no razao, que registra 'ALLPARK EMPREENDIMENTOS'.
Uso: python _pep_por_razao_social.py [--apply]
"""
import os, re, sys, unicodedata
from collections import Counter, defaultdict
import pandas as pd
import openpyxl

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')
RAZAO = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos\C - Razão P&L (SAP)'
         r'\C_Razao_PL_2026-01_a_2026-09_extraido_2026-09-04.xlsx')
# apelido usado na nossa base -> trecho da razao social no SAP (do cadastro mestre)
APELIDO = {'ESTAPAR': 'ALLPARK', 'DURATEX': 'DEXCO', 'OURINVEST': 'OURINVEST',
           'OURIBANK': 'OURINVEST', 'KOMATSU': 'KOMATSU', 'ODONTOPREV': 'ODONTOPREV',
           'LOJAS RENNER': 'RENNER', 'MERCADO LIVRE': 'MERCADOLIVRE'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def raiz(p):
    return str(p).split('.')[0]


def pep_ok(v):
    v = str(v or '').strip().upper()
    return v if re.match(r'^BR\d{1,2}[A-Z]{2,4}\d+', v) else None    # aceita BR0CLP (malformado no SAP)


# cadastro mestre: PEP -> (empresa, cliente, descricao)
mestre = pd.read_excel('pep_master_sap.xlsx', sheet_name='PEPs')
mestre.columns = [str(c).strip() for c in mestre.columns]
info = {}
por_cliente = defaultdict(set)
for _, r in mestre.iterrows():
    p = str(r['pep']).strip().upper()
    info[p] = {'empresa': str(r['empresa']), 'cliente': str(r['cliente_nome']),
               'desc': str(r['descricao']), 'status': str(r['status'])}
    if pd.notna(r['cliente_nome']):
        por_cliente[npn(r['cliente_nome'])].add(p)
print(f'cadastro mestre: {len(info)} PEPs, {len(por_cliente)} clientes')

# razao do SAP por (cliente, mes, valor)
wb = openpyxl.load_workbook(RAZAO, read_only=True)
ws = wb[wb.sheetnames[0]]
lanc = defaultdict(list)     # cliente_npn -> (per, pep, valor)
for row in ws.iter_rows(min_row=2, values_only=True):
    p = pep_ok(row[27])
    if not p or not row[21]:
        continue
    try:
        if int(str(row[4]).strip()) != 2026:
            continue
        mm = int(str(row[5]).strip())
    except (TypeError, ValueError):
        continue
    lanc[npn(row[21])].append((f'2026-{mm:02d}', p, float(row[11] or 0)))
wb.close()
print(f'razao: {len(lanc)} clientes com lancamento em 2026')

rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,empresa,pep,nome_cliente,receita,fonte,fonte_dados,tipos',
                          'periodo': f'in.({",".join(PERS)})', 'order': 'id', 'limit': '1000', 'offset': str(off)},
                  headers=H, timeout=120)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(str(b)[:200])
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
sem = [x for x in rows if (x['receita'] or 0) != 0 and x['fonte'] != 'Budget' and not x['pep']]
print(f'\nreceitas do Q2 sem PEP: {len(sem)} | R$ {sum(x["receita"] for x in sem):,.0f}\n')

CLI_RAZAO = list(lanc)
plano, stats = [], Counter()
for x in sem:
    k = npn(x['nome_cliente'])
    # descobre a razao social pelo apelido
    alvo = None
    for ap, rs in APELIDO.items():
        if ap in k:
            alvo = rs
            break
    cands = [c for c in CLI_RAZAO if (alvo and alvo in c) or c.startswith(k[:12]) or k.startswith(c[:12])]
    if not cands:
        stats['cliente nao achado no razao'] += 1
        continue
    todos = [t for c in cands for t in lanc[c]]
    v = round(abs(float(x['receita'])), 2)
    # 1) valor + mes exatos
    ex = {p for per, p, val in todos if per == x['periodo'] and abs(abs(val) - v) < 0.51}
    motivo = 'razao: valor+mes exatos'
    if not ex:                       # 2) valor exato em qualquer mes
        ex = {p for _, p, val in todos if abs(abs(val) - v) < 0.51}
        motivo = 'razao: valor exato (outro mes)'
    if not ex:                       # 3) unico PEP do cliente no mes
        ex = {p for per, p, _ in todos if per == x['periodo']}
        motivo = 'razao: unico PEP do cliente no mes'
    if not ex or len({raiz(p) for p in ex}) != 1:
        stats[f'sem match ({len(ex)} candidatos)'] += 1
        continue
    pep = sorted(ex, key=lambda p: ('.' not in p, p))[0]
    meta = info.get(pep) or info.get(raiz(pep)) or {}
    plano.append((x, pep, motivo, meta))
    stats[motivo] += 1

print('=== resultado ===')
for k2 in sorted(stats):
    print(f'   {k2:44} {stats[k2]}')
for x, p, m, meta in sorted(plano, key=lambda t: -t[0]['receita']):
    alerta = ''
    emp = str(x.get('empresa') or '')[:4]
    if meta.get('empresa') and emp and meta['empresa'] != emp:
        alerta = f"  << linha {emp} x PEP {meta['empresa']}"
    print(f'   {x["periodo"]} {str(x["nome_cliente"])[:22]:22} {x["receita"]:>10,.0f} -> {p:20} {str(meta.get("desc"))[:26]:26} [{m}]{alerta}')
if plano:
    print(f'   total: {len(plano)} linhas, R$ {sum(x["receita"] for x, _, _, _ in plano):,.0f}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep, motivo, meta in plano:
    fd = (x.get('fonte_dados') or '')
    marca = f' | PEP via razao social do cadastro SAP ({motivo}; projeto: {str(meta.get("desc"))[:40]})'
    if 'razao social do cadastro' not in fd:
        fd = (fd + marca)[:500]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': raiz(pep), 'fonte_dados': fd},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

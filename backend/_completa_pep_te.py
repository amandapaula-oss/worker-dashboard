# -*- coding: utf-8 -*-
"""Completa/qualifica o PEP das linhas do Q2 usando as fontes oficiais de receita:
  - aba T&E do P&L Gerencial jun26 v2      (PEP com fase: BR02CLP00053.1.2)
  - aba 'Racional (Receita)' da Base Unificada v3

Grava os DOIS numeros que a operacao usa:
  pep       = elemento PEP completo, com o sufixo de fase quando existir
  pep_base  = projeto (raiz, sempre sem sufixo)

Conservador: so aceita match quando o PEP e UNICO para a chave; e, em linha que
ja tem projeto, so aplica o sufixo se a RAIZ bater (nunca troca o projeto).
Ordem de confianca: valor liquido exato+mes > CPF+mes > pessoa+mes.

Uso: python _completa_pep_te.py [--apply]
"""
import os, re, sys, unicodedata
from collections import defaultdict
import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')
BU_PATH = r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\NewDashboard\Apuração de metas 2 Q\Base Unificada v3.xlsx'


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def cpfd(v):
    d = re.sub(r'\D', '', str(v))
    return d[-11:].zfill(11) if len(d) >= 9 else None


def raiz(p):
    return str(p).strip().split('.')[0] if p else None


def valido(p):
    p = str(p).strip().upper()
    return p if re.match(r'^BR\d{2}[A-Z]{2,4}\d+', p) else None


# ---------- fontes ----------
by_val, by_cpf, by_pess = defaultdict(set), defaultdict(set), defaultdict(set)

te = pd.read_excel('2026 dados/FCamara - P&L Gerencial - jun26 v2.xlsx', sheet_name='T&E')
te.columns = [str(c).strip() for c in te.columns]
te['per'] = pd.to_datetime(te['Competência'], errors='coerce').dt.strftime('%Y-%m')
te = te[te['per'].isin(PERS)]
for _, r in te.iterrows():
    p = valido(r.get('PEP')) or valido(r.get('ID PROJETO'))
    if not p:
        continue
    v = pd.to_numeric(r.get('Valor Liquido :)'), errors='coerce')
    if pd.notna(v):
        by_val[(r['per'], round(float(v), 2))].add(p)
    c = cpfd(r.get('BRCPF'))
    if c:
        by_cpf[(r['per'], c)].add(p)
    if pd.notna(r.get('PROFISSIONAL')):
        by_pess[(r['per'], npn(r['PROFISSIONAL']))].add(p)

rc = pd.read_excel(BU_PATH, sheet_name='Racional (Receita)')
rc.columns = [str(c).strip() for c in rc.columns]
def _per(v):
    d = pd.to_datetime(v, errors='coerce')
    if pd.isna(d):
        n = pd.to_numeric(v, errors='coerce')
        if pd.notna(n):
            d = pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(n))
    return None if pd.isna(d) else d.strftime('%Y-%m')
for _, r in rc.iterrows():
    per = _per(r.get('Competência'))
    if per not in PERS:
        continue
    p = valido(r.get('PEP')) or valido(r.get('ID PROJETO'))
    if not p:
        continue
    v = pd.to_numeric(r.get('Valor Liquido :)'), errors='coerce')
    if pd.notna(v):
        by_val[(per, round(float(v), 2))].add(p)
    c = cpfd(r.get('BRCPF'))
    if c:
        by_cpf[(per, c)].add(p)
    if pd.notna(r.get('PROFISSIONAL')):
        by_pess[(per, npn(r['PROFISSIONAL']))].add(p)
print(f'fontes: T&E {len(te)} ln + Racional Receita | chaves: valor {len(by_val)}, cpf {len(by_cpf)}, pessoa {len(by_pess)}')

# ---------- linhas do banco ----------
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,fonte,periodo,pep,pep_base,receita,custo_rateado,nome_pessoa',
                          'periodo': f'in.({",".join(PERS)})', 'order': 'id', 'limit': '1000', 'offset': str(off)},
                  headers=H, timeout=90)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(f'erro lendo nova_base: {str(b)[:200]}')
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
alvo = [x for x in rows if x['fonte'] in ('racionais', 'Base Unificada Q2')]
print(f'linhas da carga no Q2: {len(alvo)}')


def acha(x):
    """devolve (pep_completo, origem) ou (None, None) — so quando unico."""
    v = round(float(x['receita'] or x['custo_rateado'] or 0), 2)
    for chave, origem in (((x['periodo'], v), 'valor'),):
        c = by_val.get(chave)
        if c and len(c) == 1:
            return next(iter(c)), origem
    if x.get('nome_pessoa'):
        c = by_pess.get((x['periodo'], npn(x['nome_pessoa'])))
        if c and len(c) == 1:
            return next(iter(c)), 'pessoa'
    return None, None


plano, stats = [], defaultdict(int)
for x in alvo:
    novo, origem = acha(x)
    atual, base_atual = x.get('pep'), x.get('pep_base')
    pep_final, base_final = atual, raiz(atual)
    if novo:
        if not atual:
            pep_final, base_final = novo, raiz(novo)
            stats[f'preenchido ({origem})'] += 1
        elif raiz(novo) == raiz(atual) and '.' in novo and '.' not in str(atual):
            pep_final, base_final = novo, raiz(novo)     # ganhou a fase
            stats[f'fase adicionada ({origem})'] += 1
        elif raiz(novo) != raiz(atual):
            stats['ignorado (projeto diferente)'] += 1
    if not pep_final:
        stats['segue sem PEP'] += 1
        continue
    if pep_final != atual or base_final != base_atual:
        plano.append((x['id'], pep_final, base_final))

print('\n=== o que muda ===')
for k in sorted(stats):
    print(f'   {k:34} {stats[k]}')
print(f'   linhas a atualizar no banco       {len(plano)}')
com_fase = sum(1 for _, p, _ in plano if '.' in p)
print(f'   -> dessas, com fase (.1.x)        {com_fase}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

por_valor = defaultdict(list)
for i, p, b in plano:
    por_valor[(p, b)].append(str(i))
feitas = 0
for (p, b), lote in por_valor.items():
    for i in range(0, len(lote), 100):
        chunk = lote[i:i + 100]
        r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                        json={'pep': p, 'pep_base': b},
                        headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
        assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
        feitas += len(chunk)
print(f'\natualizadas: {feitas} linhas')

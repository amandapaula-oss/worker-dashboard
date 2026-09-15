# -*- coding: utf-8 -*-
"""Decide o PEP das receitas do Q2 que sobraram (cliente com varios projetos),
combinando as evidencias na ordem de forca certa para cada natureza de receita:

  1. VALOR IDENTICO ja lancado no cliente com o MESMO TIPO  -> Fee/WIP/licenca sao
     recorrentes; valor igual e praticamente assinatura do contrato
  2. APONTAMENTO DA PESSOA no mes (quando a linha tem pessoa) -> alocacao real
  3. APONTAMENTO DO CLIENTE dominante em horas no mes -> so quando a linha e de
     alocacao (T&E) e nao tem pessoa
  4. mesmo tipo de receita num unico PEP do cliente

Nunca escolhe quando as evidencias se contradizem. Trava de empresa mantida.
Uso: python _decide_pep_ambiguos.py [--apply]
"""
import os, re, sys, unicodedata
from collections import Counter, defaultdict
import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')
APONT = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos'
         r'\B - Apontamentos (Orange Juice)\Apontamentos 2Q26_V2.xlsx')
EMPRESA_PREFIXO = {'BR02 FCamara': 'BR02', 'BR09 NextGen': 'BR09', 'BR07 Hyper': 'BR07',
                   'BR05 SGA': 'BR05', 'BR08 Dojo': 'BR08'}
ALOCACAO = {'Time & Expenses'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def raiz(p):
    return str(p).split('.')[0]


def pep_ok(v):
    v = str(v or '').strip().upper()
    return v if re.match(r'^BR\d{2}[A-Z]{2,4}\d+', v) else None


# ---------- apontamentos ----------
ap = pd.read_excel(APONT, sheet_name='Orange')
ap.columns = [str(c).strip() for c in ap.columns]
hor_cli, hor_pess = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
for _, r in ap.iterrows():
    try:
        if str(r.get('Ano')).strip() not in ('2026', '2026.0'):
            continue
        per = f"2026-{int(r['Period']):02d}"
    except (TypeError, ValueError):
        continue
    if per not in PERS:
        continue
    wp = pep_ok(r.get('Work Package')) or pep_ok(r.get('ID Projeto'))
    if not wp:
        continue
    h = float(pd.to_numeric(r.get('Total Horas Orange'), errors='coerce') or 0)
    cli = npn(r.get('Nome Cliente'))
    if cli and cli != '0':
        hor_cli[(cli, per)][wp] += h
    nm = npn(r.get('Nome do Consultor'))
    if nm:
        hor_pess[(nm, per)][wp] += h

# ---------- historico da base ----------
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,empresa,pep,nome_cliente,nome_pessoa,receita,'
                                    'fonte,fonte_dados,tipos',
                          'order': 'id', 'limit': '1000', 'offset': str(off)}, headers=H, timeout=120)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(str(b)[:200])
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
hist = defaultdict(list)
for x in rows:
    if x['pep'] and x['nome_cliente'] and (x['receita'] or 0) != 0:
        hist[npn(x['nome_cliente'])].append(x)

CLI_AP = {k for k, _ in hor_cli}


def casa_cli(k):
    if any(k == c for c, _ in hor_cli):
        return k
    c = [c for c, _ in hor_cli if c.startswith(k[:14]) or k.startswith(c[:14])]
    return c[0] if c else None


sem = [x for x in rows if x['periodo'] in PERS and (x['receita'] or 0) != 0
       and x['fonte'] != 'Budget' and not x['pep']]
print(f'receitas do Q2 sem PEP: {len(sem)} | R$ {sum(x["receita"] for x in sem):,.0f}\n')

plano, stats = [], Counter()
for x in sem:
    cli = npn(x['nome_cliente'])
    h = hist.get(cli, [])
    tipo = str(x['tipos'])
    pep = motivo = None

    # 1. valor identico com o mesmo tipo
    iguais = Counter(y['pep'] for y in h
                     if abs((y['receita'] or 0) - x['receita']) < 0.01 and str(y['tipos']) == tipo)
    if not iguais:
        iguais = Counter(y['pep'] for y in h if abs((y['receita'] or 0) - x['receita']) < 0.01)
    if iguais and len({raiz(p) for p in iguais}) == 1:
        pep, motivo = iguais.most_common(1)[0][0], 'valor identico no historico'

    # 2. apontamento da pessoa
    if not pep and x.get('nome_pessoa'):
        c = hor_pess.get((npn(x['nome_pessoa']), x['periodo']))
        if c:
            top = sorted(c.items(), key=lambda t: -t[1])
            if top[0][1] > 0 and (len(top) == 1 or top[0][1] >= 2 * top[1][1]):
                pep, motivo = top[0][0], f'apontamento da pessoa ({top[0][1]:.0f}h)'

    # 3. apontamento do cliente — so para alocacao
    if not pep and tipo in ALOCACAO:
        k = casa_cli(cli)
        c = hor_cli.get((k, x['periodo'])) if k else None
        if c:
            top = sorted(c.items(), key=lambda t: -t[1])
            if top[0][1] > 0 and (len(top) == 1 or top[0][1] >= 2 * top[1][1]):
                pep, motivo = top[0][0], f'apontamento do cliente ({top[0][1]:.0f}h)'

    # 4. mesmo tipo num unico PEP do cliente
    if not pep:
        mt = Counter(y['pep'] for y in h if str(y['tipos']) == tipo)
        if mt and len({raiz(p) for p in mt}) == 1:
            pep, motivo = mt.most_common(1)[0][0], f'unico PEP do cliente com receita {tipo}'

    if not pep:
        stats['sem evidencia suficiente'] += 1
        continue
    pref = EMPRESA_PREFIXO.get(str(x.get('empresa')))
    if pref and not raiz(pep).startswith(pref):
        stats['BLOQUEADO (empresa nao bate)'] += 1
        continue
    plano.append((x, pep, motivo))
    stats[motivo.split(' (')[0]] += 1

print('=== decisao ===')
for k in sorted(stats):
    print(f'   {k:42} {stats[k]}')
print(f'   -> preenche {len(plano)} linhas, R$ {sum(x["receita"] for x, _, _ in plano):,.0f}\n')
for x, p, m in sorted(plano, key=lambda t: -t[0]['receita']):
    print(f'   {x["periodo"]} {str(x["nome_cliente"])[:24]:24} {str(x["tipos"])[:11]:11} {x["receita"]:>10,.0f} -> {p:20} [{m}]')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep, motivo in plano:
    fd = (x.get('fonte_dados') or '')
    marca = f' | PEP definido por: {motivo}'
    if 'PEP definido por' not in fd:
        fd = (fd + marca)[:500]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': raiz(pep), 'fonte_dados': fd},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

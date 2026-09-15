# -*- coding: utf-8 -*-
"""PEP pelas NOTAS FISCAIS (D_Fato_Ciclo_Caixa), que trazem wbs_element por nota,
cliente, competencia e valor. Receita de Fee/WIP/licenca E nota fiscal — esta e a
fonte natural desses casos, e eu nao tinha usado.

Atencao ao campo wbs_origem: 'FALLBACK'/'CLIENTE_UNICO' sao inferencias da propria
extracao; so aceito origem confiavel (o WBS que veio do documento).
Uso: python _pep_das_notas.py [--apply]
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
NOTAS = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos\D - Ciclo de Caixa (PMR)'
         r'\D_Fato_Ciclo_Caixa_2025-06_a_2026-09_snapshot_2026-09-04.xlsx')
EMPRESA_PREFIXO = {'BR02 FCamara': 'BR02', 'BR09 NextGen': 'BR09', 'BR07 Hyper': 'BR07',
                   'BR05 SGA': 'BR05', 'BR08 Dojo': 'BR08'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def raiz(p):
    return str(p).split('.')[0]


def pep_ok(v):
    v = str(v or '').strip().upper()
    return v if re.match(r'^BR\d{2}[A-Z]{2,4}\d+', v) else None


nf = pd.read_excel(NOTAS, sheet_name='fato_ciclo_caixa')
nf.columns = [str(c).strip() for c in nf.columns]
nf['per'] = pd.to_datetime(nf['competencia'], errors='coerce').dt.strftime('%Y-%m')
print('origens de wbs:', dict(Counter(nf['wbs_origem'].astype(str)).most_common(8)))
nfq = nf[nf['per'].isin(PERS)].copy()
print(f'notas do Q2: {len(nfq)} | com wbs: {nfq["wbs_element"].notna().sum()}')

CONFIAVEL = {o for o in nfq['wbs_origem'].astype(str).unique()
             if o.upper() not in ('FALLBACK', 'CLIENTE_UNICO', 'NAN', 'NONE', '')}
print('origens aceitas:', CONFIAVEL)

por_cli_per, por_val, por_cli = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
for _, r in nfq.iterrows():
    pep = pep_ok(r.get('wbs_element'))
    if not pep or str(r.get('wbs_origem')) not in CONFIAVEL:
        continue
    cli = npn(r.get('client_name'))
    if cli:
        por_cli_per[(cli, r['per'])][pep] += 1
        por_cli[cli][pep] += 1
    for col in ('valor', 'valor_bruto'):
        v = pd.to_numeric(r.get(col), errors='coerce')
        if pd.notna(v) and float(v) != 0:
            por_val[(r['per'], round(abs(float(v)), 2))][pep] += 1
print(f'   clientes utilizaveis: {len(por_cli)} | chaves valor: {len(por_val)}')

rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,empresa,pep,nome_cliente,nome_pessoa,receita,'
                                    'fonte,fonte_dados,tipos',
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

CL = sorted(por_cli)


def casa(k):
    if k in por_cli:
        return k
    c = [x for x in CL if x.startswith(k[:12]) or k.startswith(x[:12])]
    if len(c) == 1:
        return c[0]
    c = [x for x in CL if k[:9] in x or x[:9] in k]
    return c[0] if len(c) == 1 else None


def unico(c):
    if c and len({raiz(p) for p in c}) == 1:
        com_fase = [p for p in c if '.' in p]
        return (Counter({p: c[p] for p in com_fase}) if com_fase else c).most_common(1)[0][0]
    return None


plano, stats = [], Counter()
for x in sem:
    v = round(abs(float(x['receita'])), 2)
    pep = unico(por_val.get((x['periodo'], v)))
    motivo = 'nota com o mesmo valor'
    if not pep:
        k = casa(npn(x['nome_cliente']))
        if k:
            pep = unico(por_cli_per.get((k, x['periodo'])))
            motivo = 'unica nota do cliente no mes'
            if not pep:
                pep = unico(por_cli.get(k))
                motivo = 'unico projeto faturado ao cliente no trimestre'
    if not pep:
        stats['sem nota que resolva'] += 1
        continue
    pref = EMPRESA_PREFIXO.get(str(x.get('empresa')))
    if pref and not raiz(pep).startswith(pref):
        stats['BLOQUEADO (empresa nao bate)'] += 1
        continue
    plano.append((x, pep, motivo))
    stats[motivo] += 1

print('=== resultado ===')
for k2 in sorted(stats):
    print(f'   {k2:44} {stats[k2]}')
if plano:
    print(f'   -> {len(plano)} linhas, R$ {sum(x["receita"] for x, _, _ in plano):,.0f}')
    for x, p, m in sorted(plano, key=lambda t: -t[0]['receita']):
        print(f'      {x["periodo"]} {str(x["nome_cliente"])[:26]:26} {str(x["tipos"])[:11]:11} {x["receita"]:>10,.0f} -> {p:20} [{m}]')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep, motivo in plano:
    fd = (x.get('fonte_dados') or '')
    marca = f' | PEP da nota fiscal ({motivo})'
    if 'nota fiscal' not in fd:
        fd = (fd + marca)[:500]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': raiz(pep), 'fonte_dados': fd},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

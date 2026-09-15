# -*- coding: utf-8 -*-
"""PEP pela CENTRAL DE FECHAMENTO (B_Central_Fechamento_2026-04/05/06), que e bem mais
completa que o 'Apontamentos 2Q26_V2' (6-8 mil linhas/mes contra 2.9 mil no trimestre).
Traz Cliente, Work Package, Worker ID, horas Orange e horas aprovadas p/ SAP.

Usa a mesma hierarquia de evidencia: alocacao segue horas; Fee/WIP/licenca so entram
quando o cliente tem um unico projeto na Central (ai nao ha escolha a fazer).
Uso: python _pep_central_fechamento.py [--apply]
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
BASE = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
        r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos\B - Apontamentos (Orange Juice)')
ARQ = {p: f'{BASE}\\B_Central_Fechamento_{p}_extraido_2026-08-05.xlsx' for p in PERS}
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


def horas(v):
    """a Central grava horas como texto HH:MM."""
    s = str(v or '').strip()
    if ':' in s:
        try:
            hh, mm = s.split(':')[:2]
            return int(hh) + int(mm) / 60
        except ValueError:
            return 0.0
    n = pd.to_numeric(v, errors='coerce')
    return float(n) if pd.notna(n) else 0.0


hor_cli, hor_pess = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
clientes_central = set()
total = 0
for per, p in ARQ.items():
    if not os.path.exists(p):
        print(f'   !! nao achei {os.path.basename(p)}')
        continue
    d = pd.read_excel(p, sheet_name='Central de Fechamento')
    d.columns = [str(c).strip() for c in d.columns]
    total += len(d)
    for _, r in d.iterrows():
        wp = pep_ok(r.get('Work Package'))
        if not wp:
            continue
        hrs = horas(r.get('Total de horas no Orange'))
        cli = npn(r.get('Cliente'))
        if cli and cli != '0':
            hor_cli[(cli, per)][wp] += hrs
            clientes_central.add(cli)
        nm = npn(r.get('Nome do Parceiro'))
        if nm:
            hor_pess[(nm, per)][wp] += hrs
print(f'Central de Fechamento: {total} linhas no Q2 | {len(clientes_central)} clientes | {len(hor_cli)} chaves cliente-mes')

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
print(f'receitas do Q2 sem PEP: {len(sem)} | R$ {sum(x["receita"] for x in sem):,.0f}\n')

CL = sorted(clientes_central)


def casa(k):
    if k in clientes_central:
        return k
    c = [x for x in CL if x.startswith(k[:12]) or k.startswith(x[:12])]
    if len(c) == 1:
        return c[0]
    c = [x for x in CL if k[:9] in x or x[:9] in k]
    return c[0] if len(c) == 1 else None


plano, stats = [], Counter()
for x in sem:
    tipo = str(x['tipos'])
    k = casa(npn(x['nome_cliente']))
    pep = motivo = None
    if not k:
        stats['cliente nao esta na Central'] += 1
        continue
    c = hor_cli.get((k, x['periodo'])) or {}
    if not c:
        # cliente existe na Central, mas nao nesse mes: olha o trimestre
        for p2 in PERS:
            for wp, hh in (hor_cli.get((k, p2)) or {}).items():
                c[wp] = c.get(wp, 0) + hh
        if c:
            motivo_extra = ' (trimestre)'
        else:
            stats['sem apontamento do cliente'] += 1
            continue
    else:
        motivo_extra = ''
    raizes = {raiz(p) for p in c}
    if len(raizes) == 1:
        wp = sorted(c.items(), key=lambda t: -t[1])[0][0]
        pep, motivo = wp, f'unico projeto do cliente na Central{motivo_extra}'
    elif tipo in ALOCACAO:
        top = sorted(c.items(), key=lambda t: -t[1])
        if top[0][1] > 0 and (len(top) == 1 or top[0][1] >= 2 * top[1][1]):
            pep, motivo = top[0][0], f'alocacao: projeto dominante em horas ({top[0][1]:.0f}h)'
    if not pep:
        stats[f'cliente com {len(raizes)} projetos (nao decido)'] += 1
        continue
    pref = EMPRESA_PREFIXO.get(str(x.get('empresa')))
    if pref and not raiz(pep).startswith(pref):
        stats['BLOQUEADO (empresa nao bate)'] += 1
        print(f'   !! {str(x["nome_cliente"])[:26]:26} empresa={x.get("empresa")} x PEP={pep}')
        continue
    plano.append((x, pep, motivo))
    stats['preenche'] += 1

print('=== resultado ===')
for k2 in sorted(stats):
    print(f'   {k2:40} {stats[k2]}')
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
    marca = f' | PEP da Central de Fechamento: {motivo}'
    if 'Central de Fechamento' not in fd:
        fd = (fd + marca)[:500]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': raiz(pep), 'fonte_dados': fd},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

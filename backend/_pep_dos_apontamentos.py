# -*- coding: utf-8 -*-
"""PEP a partir dos APONTAMENTOS (extração Orange Juice) — fonte que eu não tinha usado.
Apontamentos 2Q26_V2.xlsx traz Work Package (PEP com fase), ID Projeto (raiz),
Nome Cliente, Worker ID e Period: o projeto onde a hora foi de fato lançada.

Faz duas coisas:
  1) tenta preencher as receitas do Q2 que seguem sem PEP (por cliente+mes / pessoa+mes)
  2) AUDITA os PEPs que preenchi por heranca, conferindo contra o apontamento
Uso: python _pep_dos_apontamentos.py [--apply]
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
MARCA = ' | PEP do apontamento (Orange)'
APONT = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
         r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos'
         r'\B - Apontamentos (Orange Juice)\Apontamentos 2Q26_V2.xlsx')
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


ap = pd.read_excel(APONT, sheet_name='Orange')
ap.columns = [str(c).strip() for c in ap.columns]
ap['per'] = ap.apply(lambda r: f"2026-{int(r['Period']):02d}"
                     if pd.notna(r.get('Period')) and str(r.get('Ano')).strip() in ('2026', '2026.0') else None, axis=1)
ap = ap[ap['per'].isin(PERS)]
print(f'apontamentos do Q2: {len(ap)} linhas')

por_cli, por_cli_per, por_pess = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
horas = defaultdict(float)
for _, r in ap.iterrows():
    wp = pep_ok(r.get('Work Package')) or pep_ok(r.get('ID Projeto'))
    if not wp:
        continue
    hrs = pd.to_numeric(r.get('Total Horas Orange'), errors='coerce') or 0
    cli = npn(r.get('Nome Cliente'))
    if cli and cli != '0':
        por_cli[cli][wp] += 1
        por_cli_per[(cli, r['per'])][wp] += 1
        horas[(cli, r['per'], wp)] += float(hrs)
    nm = npn(r.get('Nome do Consultor'))
    if nm:
        por_pess[(nm, r['per'])][wp] += 1
print(f'   clientes com apontamento: {len(por_cli)} | chaves cliente-mes: {len(por_cli_per)}')

rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,periodo,empresa,pep,pep_base,nome_cliente,nome_pessoa,receita,'
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

CLI_AP = list(por_cli)


def casa(k):
    if k in por_cli:
        return k
    c = [x for x in CLI_AP if x.startswith(k[:14]) or k.startswith(x[:14])]
    return c[0] if len(c) == 1 else None


def escolhe(c, cli=None, per=None):
    """1 WP -> usa; varios da mesma raiz -> raiz; varias raizes -> o de MAIS HORAS."""
    if not c:
        return None, None
    if len(c) == 1:
        return next(iter(c)), 'unico'
    if len({raiz(p) for p in c}) == 1:
        com_fase = [p for p in c if '.' in p]
        return (Counter({p: c[p] for p in com_fase}) if com_fase else c).most_common(1)[0][0], 'mesma raiz'
    if cli and per:
        h = {p: horas.get((cli, per, p), 0) for p in c}
        top = sorted(h.items(), key=lambda t: -t[1])
        if top and top[0][1] > 0 and (len(top) == 1 or top[0][1] >= 2 * max(t[1] for t in top[1:])):
            return top[0][0], f'dominante em horas ({top[0][1]:.0f}h vs {max(t[1] for t in top[1:]):.0f}h)'
    return None, None


# ---------- 1) preencher o que falta ----------
sem = [x for x in rows if (x['receita'] or 0) != 0 and x['fonte'] != 'Budget' and not x['pep']]
print(f'\nreceitas do Q2 sem PEP: {len(sem)} | R$ {sum(x["receita"] for x in sem):,.0f}')
plano, stats = [], Counter()
for x in sem:
    k = casa(npn(x['nome_cliente']))
    pep = motivo = None
    if x.get('nome_pessoa'):
        pep, motivo = escolhe(por_pess.get((npn(x['nome_pessoa']), x['periodo'])))
        if pep:
            motivo = 'pessoa+mes: ' + motivo
    if not pep and k:
        pep, motivo = escolhe(por_cli_per.get((k, x['periodo'])), k, x['periodo'])
        if pep:
            motivo = 'cliente+mes: ' + motivo
    if not pep:
        stats['sem apontamento que resolva'] += 1
        continue
    pref = EMPRESA_PREFIXO.get(str(x.get('empresa')))
    if pref and not raiz(pep).startswith(pref):
        stats['BLOQUEADO (empresa nao bate)'] += 1
        continue
    plano.append((x, pep, motivo))
    stats['preenche'] += 1
for k2 in sorted(stats):
    print(f'   {k2:34} {stats[k2]}')
for x, p, m in sorted(plano, key=lambda t: -t[0]['receita']):
    print(f'      {x["periodo"]} {str(x["nome_cliente"])[:24]:24} {str(x["tipos"])[:11]:11} {x["receita"]:>10,.0f} -> {p:20} [{m}]')

# ---------- 2) auditar o que ja preenchi por heranca ----------
herdadas = [x for x in rows if x['pep'] and 'herdado' in str(x.get('fonte_dados', ''))]
print(f'\n=== auditoria: {len(herdadas)} linhas que preenchi por heranca ===')
ok = dif = semref = 0
for x in herdadas:
    k = casa(npn(x['nome_cliente']))
    ref = por_cli_per.get((k, x['periodo'])) if k else None
    if not ref:
        semref += 1
        continue
    if raiz(x['pep']) in {raiz(p) for p in ref}:
        ok += 1
    else:
        dif += 1
        print(f'   DIVERGE: {x["periodo"]} {str(x["nome_cliente"])[:24]:24} gravei {x["pep"]:20} | apontamento diz {sorted({raiz(p) for p in ref})}')
print(f'   confere: {ok} | diverge: {dif} | sem apontamento do cliente: {semref}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

feitas = 0
for x, pep, _ in plano:
    fd = (x.get('fonte_dados') or '')
    if MARCA not in fd:
        fd = (fd + MARCA)[:500]
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{x["id"]}'},
                    json={'pep': pep, 'pep_base': raiz(pep), 'fonte_dados': fd},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

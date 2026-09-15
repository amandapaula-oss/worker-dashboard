# -*- coding: utf-8 -*-
"""(1) Linha sem BU tem que entrar em alguma BU. (2) Hyper x Others tem que ser
consistente entre os meses.

Regra de classificacao, na ordem (da mais objetiva para a menos):
  1. PEP -> BU: o mesmo projeto ja classificado em outra linha/mes manda
  2. PEP BR07 -> BU Hyper (prefixo da empresa no cadastro do SAP)
  3. cliente -> BU dominante do cliente na propria base (pertinencia)
  4. pessoa -> BU onde a pessoa trabalha no mesmo mes
Quem nao resolve por nada disso fica como esta (nao chuto).

O 'BU Others' so deve sobrar para o que realmente nao pertence a uma vertical.
Uso: python _classifica_bu_vazia_e_others.py [--apply]
"""
import os, sys, unicodedata, re
from collections import Counter, defaultdict

import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx
import main

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
BUS_REAIS = {'BU Finance', 'BU Retail', 'BU Health', 'BU Multisector', 'BU Logistics', 'BU Hyper'}


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return '' if v in ('NAN', 'NONE', '0') else v


def raiz(p):
    """CUIDADO: str(NaN) == 'nan'. Sem esta guarda, toda linha sem PEP cai num
    balde comum e herda a BU de quem por acaso dominar esse balde."""
    s = str(p or '').split('.')[0].strip().upper()
    return '' if s in ('', 'NAN', 'NONE', '0') else s


df = main._get_nova_base()
d = df[df['periodo'].astype(str).str.startswith('2026')].copy()
for c in ('receita', 'custo_rateado'):
    d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
v = d['vertical'].fillna('').astype(str).str.strip()

# ---------- mapas de referencia, so das linhas ja bem classificadas ----------
ok = d[v.isin(BUS_REAIS)]
bu_por_pep, bu_por_cli, bu_por_pessoa = {}, {}, {}
for rz, g in ok.groupby(ok['pep_base'].fillna(ok['pep']).map(raiz)):
    if rz:
        peso = g.groupby(g['vertical'].astype(str))[['receita', 'custo_rateado']].sum().abs().sum(axis=1)
        bu_por_pep[rz] = peso.idxmax()
for cli, g in ok.groupby(ok['nome_cliente'].map(npn)):
    if cli:
        peso = g.groupby(g['vertical'].astype(str))[['receita', 'custo_rateado']].sum().abs().sum(axis=1)
        bu_por_cli[cli] = peso.idxmax()
for (nm, per), g in ok.groupby([ok['nome_pessoa'].map(npn), ok['periodo'].astype(str)]):
    if nm:
        bu_por_pessoa[(nm, per)] = g['vertical'].astype(str).mode().iat[0]
print(f'referencias: {len(bu_por_pep)} projetos, {len(bu_por_cli)} clientes, {len(bu_por_pessoa)} pessoa-mes')

alvo = d[v.eq('') | v.eq('BU Others')]
print(f'\nlinhas a reclassificar: {len(alvo)} '
      f'(sem BU: {int(v.eq("").sum())}, Others: {int(v.eq("BU Others").sum())}) | '
      f'receita R$ {alvo["receita"].sum():,.0f} | custo R$ {alvo["custo_rateado"].sum():,.0f}')


def decide(x):
    rz = raiz(x.get('pep_base') or x.get('pep'))
    if rz:
        if rz in bu_por_pep:
            return bu_por_pep[rz], 'projeto ja classificado'
        if rz.startswith('BR07'):
            return 'BU Hyper', 'PEP do BR07 (Hyper)'
    cli = npn(x.get('nome_cliente'))
    if cli and cli in bu_por_cli:
        return bu_por_cli[cli], 'BU do cliente'
    nm = npn(x.get('nome_pessoa'))
    if nm and (nm, x['periodo']) in bu_por_pessoa:
        return bu_por_pessoa[(nm, x['periodo'])], 'BU da pessoa no mes'
    if str(x.get('fonte')) in ('Hyper', 'Hyper Q2') or str(x.get('empresa')).startswith('BR07'):
        return 'BU Hyper', 'fonte/empresa Hyper'
    return None, None


plano, stats = [], Counter()
val = defaultdict(float)
for _, x in alvo.iterrows():
    bu, motivo = decide(x)
    atual = str(x['vertical'] or '').strip()
    if not bu or bu == atual:
        stats['fica como esta'] += 1
        continue
    if pd.isna(x.get('id')):
        # linha criada pelo proprio pipeline (rateio/derivacao): nao existe na
        # tabela, herda a BU de quem a originou — corrigir a origem resolve
        stats['derivada do pipeline (segue a origem)'] += 1
        continue
    plano.append((int(x['id']), bu, motivo))
    stats[f'{atual or "(sem BU)"} -> {bu} [{motivo}]'] += 1
    val[bu] += abs(x['receita']) + abs(x['custo_rateado'])

print('\n=== plano ===')
for k, n in stats.most_common(20):
    print(f'   {k[:66]:66} {n:>5}')
print(f'   linhas a mover: {len(plano)}')
print('   valor por BU de destino:', {k: round(x) for k, x in sorted(val.items(), key=lambda t: -t[1])})

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

por_bu = defaultdict(list)
for i, bu, _ in plano:
    por_bu[bu].append(str(i))
feitas = 0
for bu, lote in por_bu.items():
    for i in range(0, len(lote), 100):
        chunk = lote[i:i + 100]
        r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                        json={'vertical': bu}, headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
        assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
        feitas += len(chunk)
print(f'\natualizadas: {feitas} linhas')

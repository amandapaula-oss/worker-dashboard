# -*- coding: utf-8 -*-
"""Preenche PEP e centro de lucro do Q1/26 usando o "Receita Contábil 1Q26" da
contabilidade (a peça oficial: 927 projetos, todos com Elemento PEP).

O de-para de cliente NAO e' por nome (la e' razao social: OURIBANK=BANCO OURINVEST,
ESTAPAR=ALLPARK, Track&Field=TFSPORTS): e' construido pelos PEPs que ja temos em
comum com eles (2026 inteiro), e so cai no nome quando a raiz normalizada bate.

Hierarquia, por linha nossa sem PEP:
  1. cliente + mes + valor exato        (casamento contabil de verdade)
  2. cliente + valor exato em outro mes
  3. cliente tem 1 projeto so com receita no trimestre
  4. cliente tem N projetos -> AMBIGUO, nao grava (lista no fim)
Depois, para toda linha com PEP e sem centro de lucro, escreve o centro de lucro
que a contabilidade tem para aquele PEP.

Uso: python _pep_q1_da_contabilidade.py [--apply]
"""
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

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
CT_COLS = ['cod_empresa', 'projeto', 'tipo_prj', 'elemento_pep', 'nome_prj',
           'cod_cliente', 'nome_cliente', 'centro_lucro', 'responsavel']
CONTABIL = os.path.join(os.environ['TEMP'], 'receita_contabil_1q26_copy.xlsx')
MES = ['m2026-01', 'm2026-02', 'm2026-03']


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    v = re.sub(r'\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA|GRUPO|BANCO|CNPJ)\b', ' ', v)
    v = ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())
    return '' if v in ('NAN', 'NONE') else v


def raiz(p):
    p = str(p or '').strip().upper()
    if p in ('', 'NAN', 'NONE', 'NAT'):
        return ''
    return p.replace('BRO', 'BR0').split('.')[0]


def parse_contabil(path):
    raw = pd.read_excel(path, sheet_name='Planilha1', header=None)
    hdr = c0 = None
    for i in range(min(8, len(raw))):
        row = raw.iloc[i].astype(str).str.strip()
        hit = row[row == 'Cod Empresa']
        if len(hit):
            hdr, c0 = i, hit.index[0]
            break
    df = raw.iloc[hdr + 1:].rename(columns={c0 + k: n for k, n in enumerate(CT_COLS)})
    from datetime import datetime
    mes_cols = {}
    for i in (max(0, hdr - 1), hdr):
        for j, v in raw.iloc[i].items():
            if isinstance(v, datetime):
                mes_cols.setdefault(f'm{v.strftime("%Y-%m")}', j)
    for name, j in mes_cols.items():
        df[name] = pd.to_numeric(df[j], errors='coerce').fillna(0.0)
    for c in CT_COLS:
        df[c] = (df[c].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                 .replace({'nan': '', 'None': ''}))
    return df[df['projeto'] != ''][CT_COLS + sorted(mes_cols)].reset_index(drop=True)


ct = parse_contabil(CONTABIL)
ct['raiz'] = ct['elemento_pep'].map(raiz)
ct['tot'] = -ct[MES].sum(axis=1)
pc_por_raiz = {r['raiz']: r['centro_lucro'] for _, r in ct.iterrows() if r['centro_lucro']}
nome_por_raiz = {r['raiz']: r['nome_prj'] for _, r in ct.iterrows()}
pep_cheio = {r['raiz']: r['elemento_pep'] for _, r in ct.iterrows()}

df = main._get_nova_base().copy()
df['receita'] = pd.to_numeric(df['receita'], errors='coerce').fillna(0)
df['raiz'] = df['pep'].map(raiz)
df['k'] = df['nome_cliente'].map(npn)

# ---------- de-para de cliente: NOME primeiro, PEP compartilhado depois ----------
# A contabilidade usa razao social (OURIBANK=BANCO OURINVEST, ESTAPAR=ALLPARK,
# Track&Field=TFSPORTS EVENTOS). Duas evidencias independentes:
#   (a) palavras em comum no nome  (b) PEPs que os dois lados ja compartilham
# Quando discordam, e' sinal de PEP trocado na NOSSA base — vai pro relatorio.
GENERICO = {'DO', 'DA', 'DE', 'E', 'EM', 'COMERCIO', 'INDUSTRIA', 'INDUSTRIAL', 'SERVICOS',
            'PARTICIPACOES', 'TECNOLOGIA', 'BRASIL', 'CONSULTORIA', 'SOLUCOES', 'SISTEMAS',
            'HOLDING', 'S', 'DIGITAL', 'INFORMATICA', 'LOGISTICA', 'DISTRIBUICAO', 'ALIMENTOS',
            'SEGUROS', 'TRANSPORTES', 'EMPREENDIMENTOS', 'IMOBILIARIA', 'IMOBILIARIOS',
            'IMOBILIARIAS', 'COOPERATIVA', 'SOCIEDADE', 'COMPANHIA', 'EDITORA', 'ASSISTENCIA',
            'GERACAO', 'VALOR', 'COBRANCA', 'ARMAZENAGENS', 'ENGENHARIA', 'COMERCIAL'}
ct_cli = sorted(set(ct['nome_cliente'].map(npn)) - {''})
tok_ct = {c: {t for t in c.split() if len(t) >= 4 and t not in GENERICO} for c in ct_cli}


def por_nome(k):
    """melhor cliente da contabilidade por palavras em comum (>=4 letras)."""
    if k in tok_ct:
        return k, 1.0
    tk = {t for t in k.split() if len(t) >= 4 and t not in GENERICO}
    if not tk:
        return None, 0.0
    melhor, score = None, 0.0
    for c, tc in tok_ct.items():
        if not tc:
            continue
        s = len(tk & tc) / len(tk | tc)
        if s > score:
            melhor, score = c, s
    return (melhor, score) if score >= 0.34 else (None, score)


ct_cli_por_raiz = {r['raiz']: r['nome_cliente'] for _, r in ct.iterrows() if r['nome_cliente']}
peso = defaultdict(lambda: defaultdict(float))
peps_liga = defaultdict(lambda: defaultdict(set))
for _, x in df[(df['raiz'] != '') & (df['k'] != '')].iterrows():
    c = ct_cli_por_raiz.get(x['raiz'])
    if c:
        peso[x['k']][npn(c)] += abs(x['receita']) + 1
        peps_liga[x['k']][npn(c)].add(x['raiz'])

nosso_para_ct, conflitos = {}, []
for k in set(df['k']) - {''}:
    nome, score = por_nome(k)
    pep_best = pep_dom = None
    if peso.get(k):
        tot = sum(peso[k].values())
        pep_best = max(peso[k], key=peso[k].get)
        pep_dom = peso[k][pep_best] / tot
    if nome and pep_best and nome != pep_best:
        conflitos.append((k, nome, round(score, 2), pep_best, round(pep_dom, 2),
                          sorted(peps_liga[k][pep_best])[:3]))
    # vale a evidencia mais forte: nome identico ganha de tudo; senao um PEP
    # compartilhado quase unanime; depois o nome parecido; por ultimo o PEP dominante
    if score >= 1.0:
        escolha = nome
    elif (pep_dom or 0) >= 0.9:
        escolha = pep_best
    elif nome:
        escolha = nome
    else:
        escolha = pep_best if (pep_dom or 0) >= 0.7 else None
    if escolha:
        nosso_para_ct[k] = escolha
for c in ct_cli:
    nosso_para_ct.setdefault(c, c)
print(f'de-para de cliente: {len(nosso_para_ct)} chaves')
if conflitos:
    print(f'\n  !! {len(conflitos)} clientes onde NOME e PEP discordam '
          f'(sinal de PEP de outro cliente na nossa base):')
    for k, n, s, p, d, pp in sorted(conflitos)[:20]:
        print(f'     {k[:26]:26} nome-> {n[:24]:24} ({s:.0%})  PEP-> {p[:22]:22} ({d:.0%}) {pp}')

# ---------- indices da contabilidade ----------
por_cli = defaultdict(list)
for _, r in ct.iterrows():
    if r['nome_cliente']:
        por_cli[npn(r['nome_cliente'])].append(r)
val_cli_mes = defaultdict(set)
val_cli = defaultdict(set)
for _, r in ct.iterrows():
    kc = npn(r['nome_cliente'])
    for i, m in enumerate(MES, 1):
        v = round(abs(r[m]), 2)
        if v > 0.005:
            val_cli_mes[(kc, f'2026-{i:02d}', v)].add(r['raiz'])
            val_cli[(kc, v)].add(r['raiz'])

q1 = df[df['periodo'].astype(str).between('2026-01', '2026-03')
        & (df['receita'] != 0)
        & (~df['fonte'].astype(str).isin(['Budget', 'de para']))]
sem_pep = q1[q1['raiz'] == '']
print(f'\nQ1: {len(q1)} linhas de receita | sem PEP: {len(sem_pep)} '
      f'(R$ {sem_pep["receita"].sum():,.2f})')

plano, ambig, nada = [], [], []
stats = defaultdict(lambda: [0, 0.0])
for _, x in sem_pep.iterrows():
    kc = nosso_para_ct.get(x['k'], x['k'])
    v = round(abs(x['receita']), 2)
    pep = motivo = None
    for cand, m in ((val_cli_mes.get((kc, x['periodo'], v)), 'cliente + mes + valor exato'),
                    (val_cli.get((kc, v)), 'cliente + valor exato (outro mes)')):
        if cand and len(cand) == 1 and not pep:
            pep, motivo = next(iter(cand)), m
    if not pep:
        proj = [r for r in por_cli.get(kc, []) if abs(r['tot']) > 0.005]
        if len({r['raiz'] for r in proj}) == 1:
            pep, motivo = proj[0]['raiz'], 'cliente tem 1 projeto so'
        elif proj:
            # desempate 1: o centro de lucro da NOSSA linha aponta o projeto
            meu_pc = re.match(r'^(DC\d+)', str(x['no_hierarquia'] or '').strip())
            if meu_pc:
                mesmo = {r['raiz'] for r in proj
                         if str(r['centro_lucro']).startswith(meu_pc.group(1))}
                if len(mesmo) == 1:
                    pep, motivo = mesmo.pop(), 'cliente + mesmo centro de lucro'
            # desempate 2 (so com --arbitrario): o maior projeto do cliente no trimestre
            if not pep and '--arbitrario' in sys.argv:
                pep = max(proj, key=lambda r: abs(r['tot']))['raiz']
                motivo = 'AMBIGUO: maior projeto do cliente'
            if not pep:
                ambig.append((x, sorted({(r['raiz'], r['nome_prj'], round(r['tot'])) for r in proj},
                                        key=lambda t: -t[2])))
                continue
        else:
            nada.append(x)
            continue
    plano.append((x, pep, motivo))
    stats[motivo][0] += 1
    stats[motivo][1] += x['receita']

print('\n=== o que a peca da contabilidade resolve ===')
for m, (q, v) in sorted(stats.items(), key=lambda t: -t[1][1]):
    print(f'   {m:38} {q:>4} linhas  R$ {v:>13,.2f}')
print(f'   {"AMBIGUO (cliente com N projetos)":38} {len(ambig):>4} linhas  '
      f'R$ {sum(x["receita"] for x, _ in ambig):>13,.2f}')
print(f'   {"sem nada na contabilidade":38} {len(nada):>4} linhas  '
      f'R$ {sum(x["receita"] for x in nada):>13,.2f}')

print('\n  top 25 do que casou:')
for x, pep, m in sorted(plano, key=lambda t: -t[0]['receita'])[:25]:
    print(f'   {x["periodo"]} {str(x["nome_cliente"])[:26]:26} {x["receita"]:>11,.0f} -> '
          f'{pep:15} {str(nome_por_raiz.get(pep, ""))[:28]:28} {str(pc_por_raiz.get(pep, ""))[:24]}  [{m}]')

if ambig:
    print(f'\n  AMBIGUOS ({len(ambig)}): cliente existe mas com varios projetos')
    ag = defaultdict(lambda: [0, 0.0, None])
    for x, ps in ambig:
        e = ag[str(x['nome_cliente'])]
        e[0] += 1; e[1] += x['receita']; e[2] = ps
    for cli, (q, v, ps) in sorted(ag.items(), key=lambda t: -t[1][1]):
        det = '; '.join(f'{p[0]} {str(p[1])[:20]} ({p[2]:,.0f})' for p in ps[:3])
        print(f'   {cli[:30]:30} {q:>3} linhas R$ {v:>11,.0f} -> {det}')
if nada:
    d = pd.DataFrame([(str(x['nome_cliente']), x['receita']) for x in nada],
                     columns=['cliente', 'receita'])
    print(f'\n  SEM NADA na contabilidade ({len(nada)} linhas) — top 15:')
    print(d.groupby('cliente')['receita'].agg(['sum', 'count'])
          .sort_values('sum', ascending=False).head(15).round(0).to_string())

# ---------- centro de lucro ----------
nh = q1['no_hierarquia'].fillna('').astype(str).str.strip()
sem_pc = q1[nh.eq('') | nh.str.lower().isin(['nan', 'none'])]
pc_plano = []
for _, x in sem_pc.iterrows():
    r = x['raiz'] or dict((int(y['id']), p) for y, p, _ in plano).get(int(x['id']), '')
    pc = pc_por_raiz.get(r, '')
    if pc:
        pc_plano.append((x, pc))
print(f'\n=== centro de lucro ===')
print(f'   linhas sem centro de lucro: {len(sem_pc)} (R$ {sem_pc["receita"].sum():,.2f})')
print(f'   a contabilidade preenche  : {len(pc_plano)} (R$ {sum(x["receita"] for x, _ in pc_plano):,.2f})')

# ---------- impacto por BU: o pipeline aplica pep_vertical por pep E por pep_base ----------
# (main._aplicar_vertical_por_pep, etapa 2). Escrever o PEP pode, portanto, MUDAR a BU
# de um trimestre fechado — essas linhas ficam de fora e viram decisao da Amanda.
VERT_MAP = {'Finance': 'BU Finance', 'Retail': 'BU Retail', 'Health': 'BU Health',
            'Multisector': 'BU Multisector', 'Logistics': 'BU Logistics',
            'Grupo Mult': 'BU Logistics', 'Others': 'BU Others', 'Hyper': 'BU Hyper',
            'BU Hyper': 'BU Hyper'}
try:
    pv = pd.read_excel(os.path.join(DIR, 'parametros.xlsx'), sheet_name='pep_vertical')
    pv.columns = [str(c).strip().lower() for c in pv.columns]
    mapa_v = {str(a).strip(): VERT_MAP.get(str(b).strip(), str(b).strip())
              for a, b in zip(pv['pep'], pv['vertical']) if str(a).strip()}
except Exception as e:
    mapa_v = {}
    print(f'   (sem aba pep_vertical: {e})')


def bu_nova(p):
    return mapa_v.get(pep_cheio.get(p, p)) or mapa_v.get(p)


seguro, muda_bu = [], []
for x, p, m in plano:
    v = bu_nova(p)
    (muda_bu if (v and v != str(x['vertical']).strip()) else seguro).append((x, p, m, v))
print(f'\n=== impacto em BU ===')
print(f'   {len(seguro)} linhas nao mexem na BU  |  {len(muda_bu)} mudariam '
      f'(R$ {sum(x["receita"] for x, _, _, _ in muda_bu):,.2f}) — essas NAO sao gravadas:')
for x, p, m, v in sorted(muda_bu, key=lambda t: -t[0]['receita']):
    print(f'      {x["periodo"]} {str(x["nome_cliente"])[:26]:26} {x["receita"]:>11,.0f} '
          f'{x["vertical"]} -> {v}  ({p} no pep_vertical)')
if '--tudo' in sys.argv:
    print('   (--tudo: as de risco TAMBEM vao ser gravadas; medir a BU depois e reverter'
          ' com _backup_pep_q1_contabil.json se mudar)')
    plano = [(x, p, m) for x, p, m, _ in seguro + muda_bu]
else:
    plano = [(x, p, m) for x, p, m, _ in seguro]

json.dump({'pep': [{'id': int(x['id']), 'pep': pep_cheio.get(p, p), 'raiz': p, 'motivo': m,
                    'cliente': str(x['nome_cliente']), 'periodo': x['periodo'],
                    'receita': float(x['receita']), 'centro_lucro': pc_por_raiz.get(p, '')}
                   for x, p, m in plano],
           'centro_lucro': [{'id': int(x['id']), 'centro_lucro': pc} for x, pc in pc_plano],
           'ambiguos': [{'id': int(x['id']), 'cliente': str(x['nome_cliente']),
                         'periodo': x['periodo'], 'receita': float(x['receita']),
                         'opcoes': [list(map(str, p)) for p in ps]} for x, ps in ambig]},
          open(os.path.join(DIR, '_plano_pep_q1_contabil.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\nplano: _plano_pep_q1_contabil.json')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

# backup das linhas que vao ser tocadas, antes de qualquer PATCH
ids = sorted({int(x['id']) for x, _, _ in plano} | {int(x['id']) for x, _ in pc_plano})
bk = []
for i in range(0, len(ids), 100):
    ch = ','.join(str(v) for v in ids[i:i + 100])
    bk += httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({ch})'},
                    headers=H, timeout=120).json()
json.dump(bk, open(os.path.join(DIR, '_backup_pep_q1_contabil.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'backup: _backup_pep_q1_contabil.json ({len(bk)} linhas)')

feitas = 0
pc_por_id = {int(x['id']): pc for x, pc in pc_plano}
for x, p, m in plano:
    i = int(x['id'])
    body = {'pep': pep_cheio.get(p, p), 'pep_base': p,
            'fonte_dados': ((str(x.get('fonte_dados') or ''))[:380]
                            + f' | PEP: Receita Contábil 1Q26 ({m})')[:500]}
    if i in pc_por_id:
        body['no_hierarquia'] = pc_por_id.pop(i)
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{i}'}, json=body,
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
for i, pc in pc_por_id.items():
    r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{i}'},
                    json={'no_hierarquia': pc}, headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
    feitas += 1
print(f'\natualizadas: {feitas} linhas')

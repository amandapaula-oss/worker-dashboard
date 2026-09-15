# -*- coding: utf-8 -*-
"""Regra da Amanda (15/09) para o custo do Hyper no Q2:
  1) custo do Hyper e ECOSSISTEMA (sai da margem; a receita Eco entra a 33,3%)
  2) custo ligado a receita vai pra MESMA BU da receita

A folha do BR07 nao traz cliente/projeto, entao o vinculo vem da CENTRAL DE FECHAMENTO
(pessoa x mes x Work Package x horas). Cada linha de custo e RATEADA por horas entre os
projetos apontados; cada parte carrega o PEP e o cliente do apontamento, e o pipeline
leva a BU pelo mesmo cadastro que levou a receita. Quem nao apontou fica no Hyper.
O total do custo nao muda — so a distribuicao.
Uso: python _hyper_custo_rateio_apontamentos.py [--apply]
"""
import os, sys, re, json, unicodedata
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
FONTE = 'Hyper Q2'
PERS = ('2026-04', '2026-05', '2026-06')
BASE = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
        r'\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\Arquivos Extraídos\B - Apontamentos (Orange Juice)')
KEYS = ['fonte', 'fonte_dados', 'periodo', 'empresa', 'pep', 'pep_base', 'nome_pessoa', 'nome_cliente',
        'vertical', 'apuracao_manual', 'tipos', 'receita', 'custo_rateado', 'classificacao',
        'tipo_contrato', 'billable_category', 'no_hierarquia']


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def raiz(p):
    return str(p or '').split('.')[0].strip().upper()


def horas(v):
    s = str(v or '').strip()
    if ':' in s:
        try:
            hh, mm = s.split(':')[:2]
            return int(hh) + int(mm) / 60
        except ValueError:
            return 0.0
    n = pd.to_numeric(v, errors='coerce')
    return float(n) if pd.notna(n) else 0.0


# ---------- apontamentos: (pessoa, mes) -> {wp: horas}; wp -> cliente ----------
ap, wp_cli = defaultdict(lambda: defaultdict(float)), {}
for per in PERS:
    d = pd.read_excel(f'{BASE}\\B_Central_Fechamento_{per}_extraido_2026-08-05.xlsx', sheet_name='Central de Fechamento')
    d.columns = [str(c).strip() for c in d.columns]
    for _, x in d.iterrows():
        wp = str(x.get('Work Package') or '').strip().upper()
        if not re.match(r'^BR\d{1,2}[A-Z]{2,4}\d+', wp):
            continue
        ap[(npn(x.get('Nome do Parceiro')), per)][wp] += horas(x.get('Total de horas no Orange'))
        c = str(x.get('Cliente') or '').strip()
        if c and c.lower() not in ('nan', '0'):
            wp_cli.setdefault(wp, c)
print(f'Central de Fechamento: {len(ap)} pessoa-mes com apontamento, {len(wp_cli)} WPs com cliente')

# ---------- receita do Hyper: BU e cliente por projeto (como o pipeline calcula) ----------
df = main._get_nova_base()
hq = df[df['fonte'].astype(str) == FONTE].copy()
hq['receita'] = pd.to_numeric(hq['receita'], errors='coerce').fillna(0)
bu_rec, cli_rec = {}, {}
for _, r in hq[hq['receita'] != 0].iterrows():
    rz = raiz(r.get('pep_base') or r.get('pep'))
    if rz:
        bu_rec.setdefault(rz, str(r['vertical']))
        cli_rec.setdefault(rz, str(r['nome_cliente']))

# ---------- custo cru ----------
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': '*', 'fonte': f'eq.{FONTE}', 'custo_rateado': 'neq.0',
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
total_antes = sum(float(x['custo_rateado']) for x in rows)
print(f'custo Hyper Q2: {len(rows)} linhas, R$ {total_antes:,.0f}')

novas, stats, por_bu = [], Counter(), defaultdict(float)
for x in rows:
    k = (npn(x['nome_pessoa']), x['periodo'])
    hs = {w: h for w, h in ap.get(k, {}).items() if h > 0}
    base = {kk: x.get(kk) for kk in KEYS}
    base['apuracao_manual'] = 'Ecossistema'
    tot = sum(hs.values())
    if not hs:
        base['fonte_dados'] = (str(x.get('fonte_dados') or '') + ' | custo Hyper = Ecossistema; sem apontamento no mes (fica no Hyper)')[:500]
        novas.append(base); stats['sem apontamento -> BU Hyper'] += 1
        por_bu['BU Hyper'] += float(x['custo_rateado'])
        continue
    partes = sorted(hs.items(), key=lambda t: -t[1])
    acum = 0.0
    for i, (wp, h) in enumerate(partes):
        v = round(float(x['custo_rateado']) * h / tot, 2)
        if i == len(partes) - 1:                          # ultima parte fecha o centavo
            v = round(float(x['custo_rateado']) - acum, 2)
        acum += v
        rz = raiz(wp)
        y = dict(base)
        y.update({'pep': wp, 'pep_base': rz, 'custo_rateado': v,
                  'nome_cliente': cli_rec.get(rz) or wp_cli.get(wp) or x.get('nome_cliente'),
                  'vertical': bu_rec.get(rz, 'BU Hyper'),
                  'fonte_dados': (str(x.get('fonte_dados') or '') + f' | custo Hyper = Ecossistema; rateado por horas da Central ({h:.0f}h de {tot:.0f}h no {wp})')[:500]})
        novas.append(y)
        por_bu[y['vertical']] += v
        stats['com receita ligada' if rz in bu_rec else 'apontado, projeto sem receita no Hyper Q2'] += 1

total_depois = sum(float(y['custo_rateado']) for y in novas)
print(f'\n=== resultado do rateio ===')
for k2, v in stats.most_common():
    print(f'   {k2:44} {v:>5} linhas')
print(f'   linhas: {len(rows)} -> {len(novas)} | custo: {total_antes:,.2f} -> {total_depois:,.2f} (dif {total_depois - total_antes:+,.2f})')
print('\n   custo por BU (BU crua; o pipeline ainda pode mover pelo cadastro de cliente):')
for bu, v in sorted(por_bu.items(), key=lambda t: t[1]):
    print(f'      {bu:16} R$ {v:>13,.0f}')
cli_top = Counter()
for y in novas:
    cli_top[str(y['nome_cliente'])[:28]] += float(y['custo_rateado'])
print('\n   maiores clientes de custo:', [(k, round(v)) for k, v in sorted(cli_top.items(), key=lambda t: t[1])[:8]])

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

json.dump(rows, open('_backup_hyper_q2_custo_antes_rateio.json', 'w', encoding='utf-8'), ensure_ascii=False)
r = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(str(x["id"]) for x in rows)})'},
                 headers={**H, 'Prefer': 'count=exact'}, timeout=300) if len(rows) <= 300 else None
if r is None:
    for i in range(0, len(rows), 200):
        chunk = rows[i:i + 200]
        r = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(str(x["id"]) for x in chunk)})'},
                         headers=H, timeout=300)
        assert r.status_code in (200, 204), r.text[:200]
else:
    assert r.status_code in (200, 204), r.text[:200]
print(f'removidas {len(rows)} linhas antigas (backup _backup_hyper_q2_custo_antes_rateio.json)')
novos_ids = []
for i in range(0, len(novas), 500):
    r = httpx.post(f'{url}/rest/v1/nova_base', json=novas[i:i + 500],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert r.status_code in (200, 201), f'{r.status_code} {r.text[:300]}'
    novos_ids += [z['id'] for z in r.json()]
json.dump(novos_ids, open('_backup_insert_hyper_q2_custo_rateado_ids.json', 'w'))
print(f'inseridas {len(novos_ids)} linhas')

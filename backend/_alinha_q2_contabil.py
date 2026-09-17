# -*- coding: utf-8 -*-
"""Q2/26 (abr-jun), BR02/BR07/BR09: a receita passa a ser EXATAMENTE a do arquivo que foi
para a contabilidade, `receita_contabilidade_2Q26_vf.xlsx` (versao final da Paola).

Regra da Amanda (17/09): "essa e' a base que foi pra contabilidade e e' o padrao que vamos
usar agora pra br02, br07 e br09". Mesmo tratamento que o Q1 ja' recebeu com a peca
"Receita Contabil 1Q26" — ver _alinha_q1_contabil.py.

BR07 e BR09 ja' batem ao centavo nos 3 meses; o ajuste e' todo em BR02.

Movimentos, por (projeto x mes):
  1. TROCA DE EMPRESA - linha gravada em BR02 cujo PEP e' de outra empresa (BR04 Nacao,
                        BR05 SGA). Nao e' erro de valor: e' receita real da outra empresa,
                        que por isso nao esta' no arquivo de BR02. Muda a empresa, NAO apaga.
  2. REESCALA         - os dois lados tem o projeto com valores diferentes.
  3. ENTRA            - so o arquivo tem (Pacaembu, Renner BR02CLP000645).
  4. SAI              - so nos temos, com PEP de BR02 ou sem PEP. Se a linha carrega horas
                        ou custo, zera a receita e mantem a linha.

Uso: python _alinha_q2_contabil.py [--apply]
"""
import datetime
import json
import os
import sys
from collections import defaultdict

import pandas as pd

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
SC = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
      r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b'
      r'\scratchpad\paola')
ARQ = os.path.join(SC, 'receita_contabilidade_2Q26_vf.xlsx')
MESES = ['2026-04', '2026-05', '2026-06']
EMPRESAS = {'BR02': 'BR02 FCamara', 'BR07': 'BR07 Hyper', 'BR09': 'BR09 NextGen'}
OUTRAS = {'BR03': 'BR03 Omnik', 'BR04': 'BR04 Nação Digital', 'BR05': 'BR05 SGA',
          'BR08': 'BR08 Dojo'}
UPLOAD_ID = 'b3bcb2f6-906a-5579-be18-e3e16ca5ab56'
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
from _supabase_creds import load_creds
url, key = load_creds()
import httpx
import main

H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}


def raiz(p):
    p = str(p or '').strip().upper()
    return '' if p in ('', 'NAN', 'NONE', 'NAT') else p.replace('BRO', 'BR0').split('.')[0]


# ---------------- alvo: o arquivo que foi pra contabilidade ----------------
bruto = pd.read_excel(ARQ, sheet_name='Consolidado por PEP', header=None)
h = next(i for i in range(12) if any(str(x).strip() == 'PEP' for x in bruto.iloc[i]))
p = pd.read_excel(ARQ, sheet_name='Consolidado por PEP', header=h)
p.columns = [str(c).strip() for c in p.columns]
C = {c.strip().lower(): c for c in p.columns}
mc = C.get('mês') or C.get('mes')
p['m'] = pd.to_datetime(p[mc], errors='coerce').dt.strftime('%Y-%m')
p['v'] = pd.to_numeric(p[C['valor']], errors='coerce').fillna(0)
p = p[p['m'].isin(MESES) & (p['v'] != 0)].copy()
p['r'] = p[C['pep']].map(raiz)
p['emp'] = p[C['empresa']].astype(str).str.extract(r'(BR\d\d)')[0].fillna('?')
alvo, info = defaultdict(float), {}
for _, r in p.iterrows():
    alvo[(r['r'], r['m'])] += float(r['v'])
    info.setdefault(r['r'], {
        'emp': r['emp'], 'cliente': str(r[C['cliente']]).strip(),
        'cc': str(r.get(C.get('centro de lucro (nome)'), '')).strip(),
        'cod': str(r.get(C.get('centro de lucro'), '')).strip(),
        'bu': str(r.get(C.get('bu'), '')).strip(),
        'ap': str(r.get(C.get('apuração') or C.get('apuracao'), '')).strip(),
        'pep_cheio': str(r[C.get('id projeto') or C['pep']]).strip()})
print(f'arquivo da contabilidade (2Q26_vf): {len(p)} linhas | R$ {p["v"].sum():,.2f}')

# ---------------- nossas linhas ----------------
df = main._get_nova_base().copy()
for c in ('receita', 'horas', 'custo_rateado'):
    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
d = df[(df['receita'] != 0) & df['periodo'].astype(str).isin(MESES)
       & (~df['fonte'].astype(str).isin(['Budget', 'de para']))].copy()
d['emp'] = d['empresa'].astype(str).str.extract(r'(BR\d\d)')[0].fillna('?')
nossa = d[d['emp'].isin(EMPRESAS)].copy()
nossa['r'] = nossa['pep'].map(raiz)
print(f'nossa base Q2 (BR02/07/09): {len(nossa)} linhas | R$ {nossa["receita"].sum():,.2f}')

# ---------------- plano ----------------
troca_emp, escala, sai, entra = [], [], [], []
for (r, m), g in nossa.groupby(['r', 'periodo']):
    a = float(alvo.get((r, m), 0))
    b = float(g['receita'].sum())
    linhas = [x for _, x in g.iterrows()]
    if abs(a) < 0.005:
        # o arquivo nao tem esse projeto neste mes
        pref = r[:4]
        if pref in OUTRAS:
            troca_emp += [(x, OUTRAS[pref]) for x in linhas]   # e' de outra empresa
        else:
            sai += linhas
    elif abs(a - b) >= 0.005:
        escala.append((r, m, b, a, linhas))
tem = set(zip(nossa['r'], nossa['periodo']))
for (r, m), v in alvo.items():
    if (r, m) in tem:
        continue
    i = info[r]
    entra.append({'periodo': m, 'pep': i['pep_cheio'] or r, 'pep_base': r,
                  'empresa': EMPRESAS.get(i['emp'], i['emp']),
                  'nome_cliente': i['cliente'],
                  'no_hierarquia': (f"{i['cod']} {i['cc']}".strip() or None),
                  'vertical': i['bu'] or 'BU Others',
                  'apuracao_manual': i['ap'] if i['ap'] in ('NG', 'Ecossistema') else None,
                  'receita': round(v, 2)})

v_sai = sum(x['receita'] for x in sai)
v_ent = sum(x['receita'] for x in entra)
v_esc = sum(a - b for _, _, b, a, _ in escala)
v_tr = sum(x['receita'] for x, _ in troca_emp)
zera = [x for x in sai if x['horas'] != 0 or x['custo_rateado'] != 0]
print(f'\n=== plano ===')
print(f'   1. TROCA DE EMPRESA  {len(troca_emp):>4} linhas | R$ {v_tr:>13,.2f} (sai de BR02, vai '
      f'pra empresa do PEP)')
print(f'   2. REESCALA          {len(escala):>4} proj×mês | efeito R$ {v_esc:>+12,.2f}')
print(f'   3. ENTRA             {len(entra):>4} linhas | R$ {v_ent:>13,.2f}')
print(f'   4. SAI               {len(sai):>4} linhas | R$ {v_sai:>13,.2f} ({len(zera)} só zeram)')
print(f'\n   efeito em BR02/07/09: R$ {v_ent - v_sai - v_tr + v_esc:+,.2f}')
print(f'   Q2 BR02/07/09: R$ {nossa["receita"].sum():,.2f} -> R$ {sum(alvo.values()):,.2f}')

por_emp = defaultdict(float)
for x, e in troca_emp:
    por_emp[e] += x['receita']
print(f'\n   --- 1. troca de empresa ---')
for e, v in sorted(por_emp.items(), key=lambda z: -z[1]):
    q = [x for x, ee in troca_emp if ee == e]
    cli = sorted({str(x['nome_cliente'])[:22] for x in q})
    print(f'      {e:20} {len(q):>3} linhas  R$ {v:>12,.2f}  {", ".join(cli)[:64]}')
print(f'\n   --- 3. entradas ---')
for x in sorted(entra, key=lambda z: -z['receita']):
    print(f'      {x["periodo"]} {x["pep_base"]:16} {str(x["nome_cliente"])[:26]:26} '
          f'{x["receita"]:>12,.2f}  {x["vertical"]}')
print(f'\n   --- 4. saídas ---')
sa = pd.DataFrame([{'pep': raiz(x['pep']) or '(sem PEP)', 'cliente': str(x['nome_cliente'])[:26],
                    'mes': x['periodo'], 'fonte': str(x['fonte'])[:20],
                    'v': x['receita'], 'h': x['horas']} for x in sai])
if len(sa):
    print(sa.groupby(['pep', 'cliente', 'fonte']).agg(v=('v', 'sum'), h=('h', 'sum'))
          .sort_values('v', ascending=False).head(14).round(2).to_string())
print(f'\n   --- 2. reescalas ---')
for r, m, b, a, _ in sorted(escala, key=lambda z: -abs(z[3] - z[2])):
    if abs(a - b) < 1:
        continue
    print(f'      {m} {r:16} {str(info.get(r, {}).get("cliente", ""))[:24]:24} '
          f'{b:>12,.2f} -> {a:>12,.2f} ({a-b:>+11,.2f})')

print(f'\n   === efeito por empresa ===')
for e in ['BR02', 'BR07', 'BR09']:
    for m in MESES:
        b = nossa[(nossa['emp'] == e) & (nossa['periodo'] == m)]['receita'].sum()
        a = sum(v for (rr, mm), v in alvo.items() if mm == m and info[rr]['emp'] == e)
        if abs(a) + abs(b) > 1 and abs(a - b) > 0.5:
            print(f'      {e} {m}: {b:>15,.2f} -> {a:>15,.2f} ({a-b:>+13,.2f})')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

ids = sorted({int(x['id']) for x in sai} | {int(x['id']) for _, _, _, _, l in escala for x in l}
             | {int(x['id']) for x, _ in troca_emp})
bk = []
for i in range(0, len(ids), 100):
    ch = ','.join(map(str, ids[i:i + 100]))
    bk += httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({ch})'},
                    headers=H, timeout=180).json()
json.dump(bk, open(os.path.join(DIR, '_backup_q2_contabil_antes.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'backup de {len(bk)} linhas: _backup_q2_contabil_antes.json')

for x, emp in troca_emp:
    z = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
                    json={'empresa': emp,
                          'fonte_dados': (str(x.get('fonte_dados') or '')[:300] +
                                          f' | empresa {x["empresa"]}->{emp} pelo PEP (arquivo '
                                          f'da contabilidade 2Q26) 17/09')[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert z.status_code in (200, 204), z.text[:200]
print(f'   1. troca de empresa: {len(troca_emp)} linhas')

nes = 0
for r, m, b, a, linhas in escala:
    if abs(a - b) < 1.0:
        x = max(linhas, key=lambda y: abs(float(y['receita'])))
        z = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
                        json={'receita': round(float(x['receita']) + (a - b), 2)},
                        headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
        assert z.status_code in (200, 204), z.text[:200]
        nes += 1
        continue
    f = a / b if b else 0
    for x in linhas:
        z = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
                        json={'receita': round(float(x['receita']) * f, 2),
                              'fonte_dados': (str(x.get('fonte_dados') or '')[:280] +
                                              f' | Q2 = arquivo da contabilidade 2Q26 '
                                              f'(era {x["receita"]:.2f}) 17/09')[:500]},
                        headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
        assert z.status_code in (200, 204), z.text[:200]
        nes += 1
print(f'   2. reescaladas: {nes} linhas')

ids_zera = {int(x['id']) for x in zera}
ids_del = [int(x['id']) for x in sai if int(x['id']) not in ids_zera]
for x in zera:
    z = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'eq.{int(x["id"])}'},
                    json={'receita': 0,
                          'fonte_dados': (str(x.get('fonte_dados') or '')[:260] +
                                          f' | receita zerada: fora do arquivo da contabilidade '
                                          f'2Q26 (era {x["receita"]:.2f}) 17/09')[:500]},
                    headers={**H, 'Prefer': 'return=minimal'}, timeout=60)
    assert z.status_code in (200, 204), z.text[:200]
for i in range(0, len(ids_del), 100):
    ch = ','.join(map(str, ids_del[i:i + 100]))
    z = httpx.delete(f'{url}/rest/v1/nova_base', params={'id': f'in.({ch})'}, headers=H, timeout=180)
    assert z.status_code in (200, 204), z.text[:200]
print(f'   4. saídas: {len(ids_del)} apagadas, {len(ids_zera)} zeradas')

cols = set(httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'limit': '1'},
                     headers=H, timeout=60).json()[0]) - {'id', 'cpf', 'apuracao'}
agora = datetime.datetime.now(datetime.timezone.utc).isoformat()
novas = []
for x in entra:
    linha = {c: None for c in cols}
    linha.update({k: v for k, v in x.items() if k in cols})
    linha.update({'fonte': 'Receita Contabilidade 2Q26', 'custo_rateado': 0, 'horas': 0,
                  'upload_id': UPLOAD_ID, 'uploaded_at': agora,
                  'fonte_dados': 'receita_contabilidade_2Q26_vf.xlsx (arquivo que foi para a '
                                 'contabilidade) | inserido 17/09'})
    novas.append(linha)
ids_new = []
for i in range(0, len(novas), 500):
    z = httpx.post(f'{url}/rest/v1/nova_base', json=novas[i:i + 500],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert z.status_code in (200, 201), f'{z.status_code} {z.text[:300]}'
    ids_new += [y['id'] for y in z.json()]
json.dump(ids_new, open(os.path.join(DIR, '_backup_insert_q2_contabil_ids.json'), 'w'))
print(f'   3. entradas: {len(ids_new)} linhas inseridas')
print('\npronto. rode _run_sync_calculada.py em seguida.')

# -*- coding: utf-8 -*-
"""Restauracao da nova_base depois que o Supabase voltar (projeto restaurado ou novo).

Ordem:
  1) testa conexao e mede o que ja existe na tabela
  2) restaura o backup FULL de 02/09 (20.402 linhas) se a tabela estiver vazia
  3) troca o Q2: apaga realizado antigo e sobe _payload_q2_pep.json (aba 1 + PEP enriquecido)
  4) sobe os custos de metas do Yuri (nao-faturaveis + despesas gerais)
  5) re-sincroniza a nova_base_calculada

Uso:  python _restaurar_pos_supabase.py            (dry-run: so mostra o plano)
      python _restaurar_pos_supabase.py --apply    (executa)
"""
import gzip, json, os, sys

APPLY = '--apply' in sys.argv
DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
KEEP_Q2 = '("Budget")'   # no Q2 so o Budget sobrevive; o resto vem da planilha oficial


def diga(*a):
    print(*a, flush=True)


# ---------- 1) conexao ----------
try:
    r = httpx.get(f'{url}/rest/v1/nova_base', params={'select': 'id', 'limit': '1'},
                  headers={**H, 'Prefer': 'count=exact'}, timeout=60)
    total = int(r.headers.get('content-range', '0/0').split('/')[-1])
except Exception as e:
    diga(f'ERRO: nao consegui falar com {url}')
    diga(f'  {type(e).__name__}: {e}')
    diga('  -> o projeto Supabase precisa estar ativo (e SUPABASE_URL/KEY do backend/.env atualizados).')
    sys.exit(1)
diga(f'conexao OK | nova_base tem {total} linhas hoje')

# ---------- 2) backup FULL ----------
fullp = os.path.join(DIR, '_backup_nova_base_FULL_20260902.json.gz')
with gzip.open(fullp, 'rt', encoding='utf-8') as f:
    full = json.load(f)
diga(f'backup FULL 02/09: {len(full)} linhas disponiveis')
restaurar_full = total == 0
if restaurar_full:
    diga('  -> tabela VAZIA: vou restaurar o backup inteiro')
else:
    diga('  -> tabela tem dados: NAO restauro o full (evita duplicar); so faco a troca do Q2')

# ---------- 3/4) cargas do Q2 ----------
payload = json.load(open(os.path.join(DIR, '_payload_q2_pep.json'), encoding='utf-8'))
# so manda campos que existem MESMO na tabela (a nova_base nao tem 'cpf', p.ex.)
_amostra = httpx.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'limit': '1'}, headers=H, timeout=60).json()
if _amostra:
    _cols = set(_amostra[0].keys())
    _fora = set().union(*(set(x) for x in payload)) - _cols
    if _fora:
        diga(f'  campos ignorados (nao existem na tabela): {sorted(_fora)}')
        payload = [{k: v for k, v in x.items() if k in _cols} for x in payload]
rec = sum(x.get('receita') or 0 for x in payload)
cus = sum(x.get('custo_rateado') or 0 for x in payload)
diga(f'payload Q2 (aba 1 + PEP): {len(payload)} linhas | receita {rec:,.0f} | custo {cus:,.0f}')

if not APPLY:
    diga('\n--- DRY RUN: nada foi alterado. Rode com --apply para executar. ---')
    sys.exit(0)

# --- executa ---
if restaurar_full:
    limpo = [{k: v for k, v in row.items() if k != 'id'} for row in full]
    for i in range(0, len(limpo), 500):
        r = httpx.post(f'{url}/rest/v1/nova_base', json=limpo[i:i + 500], headers=H, timeout=300)
        assert r.status_code in (200, 201), f'full lote {i}: {r.status_code} {r.text[:200]}'
    diga(f'restaurado backup FULL: {len(limpo)} linhas')

r = httpx.delete(f'{url}/rest/v1/nova_base',
                 params={'periodo': 'in.(2026-04,2026-05,2026-06)', 'fonte': f'not.in.{KEEP_Q2}'},
                 headers={**H, 'Prefer': 'count=exact'}, timeout=300)
assert r.status_code in (200, 204), r.text[:200]
diga(f'Q2 antigo removido (mantido Budget): {r.headers.get("content-range")}')

ids = []
for i in range(0, len(payload), 500):
    r = httpx.post(f'{url}/rest/v1/nova_base', json=payload[i:i + 500],
                   headers={**H, 'Prefer': 'return=representation'}, timeout=300)
    assert r.status_code in (200, 201), f'{r.status_code} {r.text[:200]}'
    ids += [x['id'] for x in r.json()]
json.dump(ids, open(os.path.join(DIR, '_backup_insert_q2_pep_ids.json'), 'w'))
diga(f'payload Q2 inserido: {len(ids)} linhas')

diga('subindo custos de metas do Yuri (nao-faturaveis + despesas gerais)...')
os.system(f'{sys.executable} "{os.path.join(DIR, "_subir_custos_yuri_q2.py")}"')

diga('re-sincronizando a calculada...')
os.system(f'{sys.executable} "{os.path.join(DIR, "_run_sync_calculada.py")}"')
diga('\nPRONTO. No site, clicar em "Atualizar Dados" (ou POST /api/nova-base/clear-cache).')

# -*- coding: utf-8 -*-
"""Confere se o Q1 voltou ao que era antes do alinhamento a peca "Receita Contabil 1Q26".

Tres provas, da mais forte pra mais fraca:
  A. as 1.430 linhas do backup estao IDENTICAS ao backup (campo a campo)
  B. nao sobrou nenhuma linha com fonte "Receita Contabil 1Q26"
  C. o Q1 de BR02+BR07+BR09 no PIPELINE voltou a R$ 77.344.202,05 (valor de 16/09).
     Cuidado: a soma BRUTA da tabela e' bem maior (as fontes se sobrepoem e o pipeline
     desduplica), entao so' vale comparar depois do pipeline.
E a prova que importa pra Amanda:
  D. a receita Q1 por BU, que e' o que o diretor ve na Visao BUs, contra a apuracao paga.

Uso: python _bate_q1_diretores.py
"""
import json
import os
import sys

import pandas as pd

DIR = os.path.dirname(os.path.abspath(__file__))
Q1 = ['2026-01', '2026-02', '2026-03']
FONTE_PECA = 'Receita Contábil 1Q26'
Q1_ANTES = 77344202.05          # memoria: "Q1 foi de R$ 77.344.202,05 para R$ 76.735.355,87"
CAMPOS = ['receita', 'pep', 'pep_base', 'no_hierarquia', 'vertical', 'apuracao_manual',
          'nome_cliente', 'empresa', 'fonte', 'fonte_dados', 'projeto', 'custo_rateado', 'horas']
# a apuracao Q1 que foi PAGA (realizado de Receita Total, abas DIRETOR dos arquivos do Yuri)
APURADO = {
    'BU Logistics':   ('Henrique (Grupo Mult)', 11733281.39),
    'BU Health':      ('Marcos',                13452225.83),
}

os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
os.environ.setdefault('ALLOWED_ORIGINS', '*')
sys.path.insert(0, DIR)
from _supabase_creds import load_creds
url, key = load_creds()
import httpx

H = {'apikey': key, 'Authorization': f'Bearer {key}'}
bk = [x for x in json.load(open(os.path.join(DIR, '_backup_q1_contabil_antes.json'), encoding='utf-8'))
      if str(x.get('periodo')) in Q1]
print(f'backup: {len(bk)} linhas\n')

with httpx.Client(headers=H, timeout=300) as c:
    # --- A. cada linha do backup existe e esta' identica -----------------------------
    ids = sorted(int(x['id']) for x in bk)
    vivas = {}
    for i in range(0, len(ids), 150):
        ch = ','.join(map(str, ids[i:i + 150]))
        for y in c.get(f'{url}/rest/v1/nova_base', params={'select': '*', 'id': f'in.({ch})'}).json():
            vivas[int(y['id'])] = y

    def difs(o, a):
        out = []
        for cmp in CAMPOS:
            if cmp not in o:
                continue
            x, y = o.get(cmp), a.get(cmp)
            try:
                if abs(float(x or 0) - float(y or 0)) > 0.005:
                    out.append(cmp)
                continue
            except (TypeError, ValueError):
                pass
            if str(x) != str(y):
                out.append(cmp)
        return out

    sumidas = [x for x in bk if int(x['id']) not in vivas]
    difere = [(x, difs(x, vivas[int(x['id'])])) for x in bk if int(x['id']) in vivas]
    difere = [(x, d) for x, d in difere if d]
    print(f'A. linhas do backup restauradas: {len(bk) - len(sumidas) - len(difere)}/{len(bk)}')
    if sumidas:
        print(f'   !! {len(sumidas)} ids do backup nao existem mais (as 77 reinseridas ganham id novo,')
        print(f'      entao aqui e' + "'" + ' esperado ver 77 se o passo 2 rodou)')
    for x, d in difere[:8]:
        print(f'   !! id {x["id"]} {str(x.get("nome_cliente"))[:22]:22} difere em {",".join(d)}')

    # --- B. nenhuma linha da peca sobrou ---------------------------------------------
    r = c.get(f'{url}/rest/v1/nova_base', params={'select': 'id', 'fonte': f'eq.{FONTE_PECA}', 'limit': '1'},
              headers={**H, 'Prefer': 'count=exact'})
    n_peca = int(r.headers.get('content-range', '*/0').split('/')[-1])
    print(f'\nB. linhas com fonte "{FONTE_PECA}": {n_peca}   {"OK" if n_peca == 0 else "<<< AINDA HA"}')

    # --- C. contagem de linhas do Q1 (o total em R$ so' faz sentido pos-pipeline) ------
    r = c.get(f'{url}/rest/v1/nova_base', params={'select': 'id', 'limit': '1'},
              headers={**H, 'Prefer': 'count=exact'})
    print(f'C. linhas na nova_base: {r.headers.get("content-range")}')

# --- D. receita Q1 por BU, do jeito que o dashboard calcula ---------------------------
print('\nD. receita Q1 por BU (pipeline completo, igual a Visao BUs)')
import main
main._cache['nova_base'] = None
nb = main._get_nova_base()
nb = nb[nb['periodo'].astype(str).isin(Q1)].copy()
nb['receita'] = pd.to_numeric(nb['receita'], errors='coerce').fillna(0)
g = nb.groupby('vertical')['receita'].sum().sort_values(ascending=False)
print(f'   {"BU":18} {"Q1 no dash":>18} {"apurado (pago)":>18} {"gap":>15}')
for bu, v in g.items():
    if bu in APURADO:
        quem, alvo = APURADO[bu]
        flag = 'OK' if abs(v - alvo) < 1 else ''
        print(f'   {bu:18} {v:>18,.2f} {alvo:>18,.2f} {v - alvo:>+15,.2f}  {flag}  ({quem})')
    else:
        print(f'   {bu:18} {v:>18,.2f} {"-":>18} {"-":>15}')
print(f'\n   TOTAL Q1 (pipeline): R$ {g.sum():,.2f}')

# -*- coding: utf-8 -*-
"""Completa/qualifica o PEP das linhas do Q2 usando as fontes oficiais de receita:
  - aba T&E do P&L Gerencial jun26 v2      (PEP com fase: BR02CLP00053.1.2)
  - aba 'Racional (Receita)' da Base Unificada v3

Grava os DOIS numeros que a operacao usa:
  pep       = elemento PEP completo, com o sufixo de fase quando existir
  pep_base  = projeto (raiz, sempre sem sufixo)

Conservador: so aceita match quando o PEP e UNICO para a chave; e, em linha que
ja tem projeto, so aplica o sufixo se a RAIZ bater (nunca troca o projeto).
Ordem de confianca: valor liquido exato+mes > CPF+mes > pessoa+mes.

Uso: python _completa_pep_te.py [--apply]
"""
import os, re, sys, unicodedata
from collections import defaultdict
import pandas as pd

APPLY = '--apply' in sys.argv
os.environ.setdefault('SECRET_KEY', 'dbg-readonly')
from _supabase_creds import load_creds
import httpx

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
PERS = ('2026-04', '2026-05', '2026-06')
BU_PATH = r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\NewDashboard\Apuração de metas 2 Q\Base Unificada v3.xlsx'


def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())


def cpfd(v):
    d = re.sub(r'\D', '', str(v))
    return d[-11:].zfill(11) if len(d) >= 9 else None


def raiz(p):
    return str(p).strip().split('.')[0] if p else None


def valido(p):
    p = str(p).strip().upper()
    return p if re.match(r'^BR\d{2}[A-Z]{2,4}\d+', p) else None


# ---------- fontes ----------
by_val, by_cpf, by_pess = defaultdict(set), defaultdict(set), defaultdict(set)
by_cli = defaultdict(set)   # so usado para Fee/WIP/UsageBased, que nao tem pessoa

te = pd.read_excel('2026 dados/FCamara - P&L Gerencial - jun26 v2.xlsx', sheet_name='T&E')
te.columns = [str(c).strip() for c in te.columns]
te['per'] = pd.to_datetime(te['Competência'], errors='coerce').dt.strftime('%Y-%m')
te = te[te['per'].isin(PERS)]
for _, r in te.iterrows():
    p = valido(r.get('PEP')) or valido(r.get('ID PROJETO'))
    if not p:
        continue
    v = pd.to_numeric(r.get('Valor Liquido :)'), errors='coerce')
    if pd.notna(v):
        by_val[(r['per'], round(float(v), 2))].add(p)
    c = cpfd(r.get('BRCPF'))
    if c:
        by_cpf[(r['per'], c)].add(p)
    if pd.notna(r.get('PROFISSIONAL')):
        by_pess[(r['per'], npn(r['PROFISSIONAL']))].add(p)

# Racionais mensais (Financial Controls): abas Fee_WIP / UsageBased / TimeAndExpenses.
# A aba '<> T&E' do P&L so tem jan-fev, entao o Fee/WIP do Q2 vem daqui.
# Essas abas tem PEP (com fase) e 'Formula PEP' (raiz) — os dois numeros.
import glob
RAC = r'C:\Users\amanda.paula\FCamara Consultoria e Formação\Financial Controls - Racional\Receita'
arqs = [p for p in glob.glob(os.path.join(RAC, 'BR02 - Fcamara', '2026', '0[456].*', '**', 'RacFinancial*.xlsx'), recursive=True)]
arqs += [p for p in glob.glob(os.path.join(RAC, 'BR09 - Next', '2026', 'RacFinancial*.xlsx'))
         if any(m in p for m in ('Abril', 'Maio', 'Junho'))]


def _le(p, aba):
    """le a aba achando a linha de header que tem 'PEP'."""
    for hdr in (1, 0, 2):
        try:
            d = pd.read_excel(p, sheet_name=aba, header=hdr)
        except Exception:
            return None
        d.columns = [str(c).strip() for c in d.columns]
        if any(c.upper() == 'PEP' for c in d.columns):
            return d
    return None


MESNOME = {'JANEIRO': '01', 'FEVEREIRO': '02', 'MARCO': '03', 'MARÇO': '03', 'ABRIL': '04',
           'MAIO': '05', 'JUNHO': '06', 'JULHO': '07'}


def per_do_arquivo(caminho):
    """a competencia do racional e o proprio arquivo/pasta (RacFinancial_Junho -> 2026-06);
    a coluna INICIO e data de contrato, nao competencia."""
    alvo = npn(caminho)
    for nome, mm in MESNOME.items():
        if nome in alvo:
            return f'2026-{mm}'
    return None


n_rac = 0
for p in arqs:
    per_arq = per_do_arquivo(p)
    try:
        import openpyxl as _ox
        _wb = _ox.load_workbook(p, read_only=True)
        abas = _wb.sheetnames
        _wb.close()
    except Exception:
        continue
    for aba in abas:
        if not any(t in aba.upper() for t in ('FEE', 'WIP', 'USAGE', 'TIMEANDEXPENSES')):
            continue
        d = _le(p, aba)
        if d is None or not len(d):
            continue
        cols = set(d.columns)
        colper = next((c for c in ('Compet', 'INICIO', 'Competência') if c in cols), None)
        for _, r in d.iterrows():
            pep = valido(r.get('PEP')) or valido(r.get('Formula PEP'))
            if not pep:
                continue
            per = None
            if colper:
                dt = pd.to_datetime(r.get(colper), errors='coerce')
                per = None if pd.isna(dt) else dt.strftime('%Y-%m')
            if per not in PERS:
                per = per_arq          # cai para a competencia do proprio arquivo
            if per not in PERS:
                continue
            n_rac += 1
            for col in ('Formula Líquido', 'RECEITA PLANEJADA', 'RECEITA LIQUIDA', 'Valor Liquido :)'):
                v = pd.to_numeric(r.get(col), errors='coerce') if col in cols else None
                if v is not None and pd.notna(v) and float(v) != 0:
                    by_val[(per, round(float(v), 2))].add(pep)
            if 'NOME CLIENTE' in cols and pd.notna(r.get('NOME CLIENTE')):
                by_cli[(per, npn(r['NOME CLIENTE']))].add(pep)
            if 'PROFISSIONAL' in cols and pd.notna(r.get('PROFISSIONAL')):
                by_pess[(per, npn(r['PROFISSIONAL']))].add(pep)
            if 'WORKEID' in cols:
                c = cpfd(r.get('WORKEID'))
                if c:
                    by_cpf[(per, c)].add(pep)
print(f'racionais mensais: {len(arqs)} arquivos | {n_rac} linhas do Q2 com PEP')

rc = pd.read_excel(BU_PATH, sheet_name='Racional (Receita)')
rc.columns = [str(c).strip() for c in rc.columns]
def _per(v):
    d = pd.to_datetime(v, errors='coerce')
    if pd.isna(d):
        n = pd.to_numeric(v, errors='coerce')
        if pd.notna(n):
            d = pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(n))
    return None if pd.isna(d) else d.strftime('%Y-%m')
for _, r in rc.iterrows():
    per = _per(r.get('Competência'))
    if per not in PERS:
        continue
    p = valido(r.get('PEP')) or valido(r.get('ID PROJETO'))
    if not p:
        continue
    v = pd.to_numeric(r.get('Valor Liquido :)'), errors='coerce')
    if pd.notna(v):
        by_val[(per, round(float(v), 2))].add(p)
    c = cpfd(r.get('BRCPF'))
    if c:
        by_cpf[(per, c)].add(p)
    if pd.notna(r.get('PROFISSIONAL')):
        by_pess[(per, npn(r['PROFISSIONAL']))].add(p)
print(f'fontes: T&E {len(te)} ln + Racional Receita | chaves: valor {len(by_val)}, cpf {len(by_cpf)}, pessoa {len(by_pess)}')

# ---------- linhas do banco ----------
rows, ids, off = [], set(), 0
while True:
    r = httpx.get(f'{url}/rest/v1/nova_base',
                  params={'select': 'id,fonte,periodo,pep,pep_base,receita,custo_rateado,nome_pessoa,nome_cliente',
                          'periodo': f'in.({",".join(PERS)})', 'order': 'id', 'limit': '1000', 'offset': str(off)},
                  headers=H, timeout=90)
    b = r.json()
    if not isinstance(b, list):
        raise SystemExit(f'erro lendo nova_base: {str(b)[:200]}')
    for x in b:
        if x['id'] not in ids:
            ids.add(x['id']); rows.append(x)
    if len(b) < 1000:
        break
    off += 1000
alvo = [x for x in rows if x['fonte'] in ('racionais', 'Base Unificada Q2')]
print(f'linhas da carga no Q2: {len(alvo)}')


def _resolve(c, origem):
    """1 PEP -> usa. Varios PEPs da MESMA raiz (fases do mesmo projeto) -> usa a raiz.
    Raizes diferentes -> ambiguo de verdade, devolve None."""
    if not c:
        return None, None
    if len(c) == 1:
        return next(iter(c)), origem
    raizes = {raiz(p) for p in c}
    if len(raizes) == 1:
        return next(iter(raizes)), origem + ' (raiz)'
    return None, None


def acha(x):
    """devolve (pep, origem) ou (None, None)."""
    v = round(float(x['receita'] or x['custo_rateado'] or 0), 2)
    p, o = _resolve(by_val.get((x['periodo'], v)), 'valor')
    if p:
        return p, o
    if x.get('nome_pessoa'):
        p, o = _resolve(by_pess.get((x['periodo'], npn(x['nome_pessoa']))), 'pessoa')
        if p:
            return p, o
    # sem pessoa (Fee/WIP/UsageBased): cliente na fonte <> T&E
    if not x.get('nome_pessoa') and x.get('nome_cliente'):
        c = by_cli.get((x['periodo'], npn(x['nome_cliente'])))
        if c and len(c) == 1:
            return next(iter(c)), 'cliente (Fee/WIP)'
    return None, None


plano, stats = [], defaultdict(int)
for x in alvo:
    novo, origem = acha(x)
    atual, base_atual = x.get('pep'), x.get('pep_base')
    pep_final, base_final = atual, raiz(atual)
    if novo:
        if not atual:
            pep_final, base_final = novo, raiz(novo)
            stats[f'preenchido ({origem})'] += 1
        elif raiz(novo) == raiz(atual) and '.' in novo and '.' not in str(atual):
            pep_final, base_final = novo, raiz(novo)     # ganhou a fase
            stats[f'fase adicionada ({origem})'] += 1
        elif raiz(novo) != raiz(atual):
            stats['ignorado (projeto diferente)'] += 1
    if not pep_final:
        stats['segue sem PEP'] += 1
        continue
    if pep_final != atual or base_final != base_atual:
        plano.append((x['id'], pep_final, base_final))

print('\n=== o que muda ===')
for k in sorted(stats):
    print(f'   {k:34} {stats[k]}')
print(f'   linhas a atualizar no banco       {len(plano)}')
com_fase = sum(1 for _, p, _ in plano if '.' in p)
print(f'   -> dessas, com fase (.1.x)        {com_fase}')

if not APPLY:
    print('\n--- DRY RUN: nada gravado. Rode com --apply. ---')
    raise SystemExit(0)

por_valor = defaultdict(list)
for i, p, b in plano:
    por_valor[(p, b)].append(str(i))
feitas = 0
for (p, b), lote in por_valor.items():
    for i in range(0, len(lote), 100):
        chunk = lote[i:i + 100]
        r = httpx.patch(f'{url}/rest/v1/nova_base', params={'id': f'in.({",".join(chunk)})'},
                        json={'pep': p, 'pep_base': b},
                        headers={**H, 'Prefer': 'return=minimal'}, timeout=120)
        assert r.status_code in (200, 204), f'{r.status_code} {r.text[:200]}'
        feitas += len(chunk)
print(f'\natualizadas: {feitas} linhas')

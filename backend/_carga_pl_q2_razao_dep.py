# -*- coding: utf-8 -*-
"""Q2/26: refaz SO as linhas da fonte 'Razao' da carga P&L Q2, agora com departamento.

Problema (26/11): na aba 'Razao' do P&L a coluna AG "Departamento Centro de Custo" esta'
preenchida em jan-mar e ago-set e VAZIA em abr-jul. Como o `_carga_pl_q2.py` le AG direto,
as 51 linhas do Q2 entraram todas com 'Sem departamento' -> no dash R$ 7,80 mi de despesa
do Q2 ficam sem macro_area e a aba "P&L por Macro Area" mostra Backoffice caindo 7,1 mi e
Go To Market zerado, o que nao aconteceu.

Solucao: a coluna P "CostCenter" esta' 92-94% preenchida em abr-jun. O de-para
CostCenter -> Departamento sai dos proprios meses em que AG existe (84 centros de custo,
ZERO ambiguidade: cada CostCenter aponta para um departamento so'). Com o departamento vem
de graca a BU real (`bu(dep)`) e a macro_area pelo DEPARA_MACRO abaixo.

So' mexe nas linhas `fonte='Razao'` com `fonte_dados` da carga de 26/11 e periodo abr-jun.
O total NAO muda: e' a mesma soma, quebrada por departamento.

Uso: python _carga_pl_q2_razao_dep.py PL.xlsx DESPESAS_GERAIS.xlsx [--apply]
"""
import datetime, json, os, re, sys, uuid
from collections import defaultdict

import httpx, openpyxl, pandas as pd
from _supabase_creds import load_creds

PL, DG = sys.argv[1], sys.argv[2]
APPLY = '--apply' in sys.argv
MESES = {4: '2026-04', 5: '2026-05', 6: '2026-06'}
EMP = {'BR02': 'BR02 FCamara', 'BR09': 'BR09 NextGen', 'BR07': 'BR07 Hyper', 'BR04': 'BR04 Nação Digital',
       'BR05': 'BR05 SGA', 'BR08': 'BR08 Dojo', 'BR01': 'BR01 Holding', 'BR03': 'BR03 Omnik'}
TAG = ' | carga P&L Q2 (26/11)'
FONTE_DADOS = f'P&L Gerencial set26 (base unica 19.11) | aba Razão{TAG}'
AGR = ['Commission expenses', 'Marketing and selling expenses', 'General and administrative expenses',
       'Consulting expenses', 'Occupancy expenses', 'Travel expenses', 'Tax expenses',
       'Other operating income (expenses) net']

# Departamento Centro de Custo -> macro_area do dash.
# Regua: as duplas (area, macro_area) que JA' existem na nova_base. Onde a base e' ambigua
# o comentario diz por que. Departamento de BU/produto fica fora de proposito: no Q1 a
# macro_area e' dimensao de ESTRUTURA (centro de custo corporativo), nao de BU.
DEPARA_MACRO = {
    # --- Backoffice (estrutura corporativa) ---
    'Accounting, Tax and Internal Audit': 'Backoffice',   # base: 'Acc, Tax & Audit' -> Backoffice
    'Administrative FC': 'Backoffice',
    'Legal': 'Backoffice',                                 # base: 'Legal' -> Backoffice
    'Facilities': 'Backoffice',                            # base: 'Facilities' -> Backoffice
    'Human Resources FC': 'Backoffice',                    # base: 'Human Resources' -> Backoffice
    'Treasury': 'Backoffice',                              # base: 'Treasury' -> Backoffice
    'Employee Experience': 'Backoffice',                    # base: idem
    'Financial Controls': 'Backoffice',                     # base: idem
    'FP&A and VMO/PMI': 'Backoffice',                       # base: idem
    'M&A': 'Backoffice',                                    # base: 'M&A' -> Backoffice
    'Infrastructure & Cybersecurity': 'Backoffice',         # base: 'Infra & Cyber'/'Cyber' -> Backoffice
    'R&S': 'Backoffice',                                    # AMBIGUO na base (Backoffice 65 / Delivery 59); R&S do CC e' corporativo
    'HRBP': 'Backoffice',                                   # AMBIGUO na base (Backoffice 18 / Delivery 17)
    'Training': 'Backoffice',
    'AI': 'Backoffice',
    # --- Internal Systems ---
    'Internal Systems': 'Internal Systems',
    # --- Go To Market ---
    'Marketing (FC)': 'Go To Market',                       # base: 'Marketing' -> Go To Market (74) vs Backoffice (9)
    'Sales Excellence': 'Go To Market',
    'Alianças': 'Go To Market',
    'FC Consult. B. Sales': 'Go To Market',
    # --- Executive Leadership ---
    'Shareholders FC': 'Executive Leadership',
}
# Departamento de BU / produto / intercompany: NAO recebem macro_area (decisao pendente da
# Amanda). Ficam com departamento e BU preenchidos, macro_area vazia, como hoje.
SEM_MACRO = {'BU Finance', 'BU Health', 'BU Hyper', 'BU Logistics', 'BU Multisector', 'BU Others', 'BU Retail',
             'E-commerce', 'Play Studio', 'Open-X', 'Community', 'Imagine', 'Licensing Microsoft',
             'Global Operations', 'Orange App', 'Pods & Engineering', 'Sem departamento', '0',
             'Intercompany BR03', 'Intercompany BR04', 'Intercompany BR05', 'Intercompany BR08',
             'Intercompany PT01', 'Intercompany UK01'}

url, key = load_creds()
H = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
AQUI = os.path.dirname(os.path.abspath(__file__))


def num(v):
    try:
        return float(str(v).replace(',', '.')) if v not in (None, '') else 0.0
    except ValueError:
        return 0.0


def txt(v):
    s = str(v or '').strip()
    return None if s in ('', '0', 'None', 'nan') else s


def mes(v):
    return MESES.get(v.month) if hasattr(v, 'month') and v.year == 2026 else None


def bu(v):
    s = str(v or '').strip()
    return s if s.startswith('BU ') and ' - ' not in s else (s.split(' - ')[0] if s.startswith('BU ') else 'BU Others')


# ---------------- 1. de-para CostCenter -> Departamento (dos meses em que AG existe) ------
wb = openpyxl.load_workbook(PL, read_only=True, data_only=True)
sh = wb['Razão']
peso = defaultdict(lambda: defaultdict(float))
for r in sh.iter_rows(min_row=2, values_only=True):
    cc, dep = txt(r[15]), txt(r[32])
    if cc and dep and txt(r[3]) in AGR:
        peso[cc][dep] += abs(num(r[11])) + 1
ambig = {cc: dict(d) for cc, d in peso.items() if len(d) > 1}
DEP_DE = {cc: max(d.items(), key=lambda x: x[1])[0] for cc, d in peso.items()}
print(f'de-para CostCenter->Departamento: {len(DEP_DE)} centros de custo, {len(ambig)} ambiguos')
for cc, d in ambig.items():
    print(f'  AMBIGUO {cc}: {d}')

# ---------------- 2. documentos que ja' entraram por 'Despesas gerais da BU' --------------
d2 = pd.read_excel(DG, sheet_name='Planilha1')
d2 = d2[pd.to_numeric(d2.FiscalPeriod, errors='coerce').isin([4, 5, 6])]
ja_doc = {(str(c).strip(), str(int(a)), str(int(i)))
          for c, a, i in zip(d2.CompanyCode, d2.AccountingDocument, d2.AccountingDocumentItem)
          if pd.notna(a) and pd.notna(i)}

# ---------------- 3. reagrupa abr-jun por mes x empresa x agrupador x departamento --------
raz, raz_fora, sem_cc = {}, 0.0, 0.0
for r in sh.iter_rows(min_row=2, values_only=True):
    p, agr = mes(r[31]), str(r[3] or '').strip()
    if not p or agr not in AGR:
        continue
    try:
        doc = (str(r[0]).strip(), str(int(float(r[8]))), str(int(float(r[9]))))
    except (TypeError, ValueError):
        doc = None
    if doc in ja_doc:
        raz_fora += num(r[11])
        continue
    cc = txt(r[15])
    dep = txt(r[32]) or (DEP_DE.get(cc) if cc else None) or 'Sem departamento'
    if dep == 'Sem departamento':
        sem_cc += num(r[11])
    k = (p, str(r[0]).strip(), agr, dep)
    raz[k] = raz.get(k, 0.0) + num(r[11])

out = []
for (p, emp, agr, dep), v in raz.items():
    if abs(v) < 0.005:
        continue
    ma = DEPARA_MACRO.get(dep)
    if ma is None and dep not in SEM_MACRO:
        print(f'  !! departamento sem de-para de macro_area: {dep!r} ({v:,.2f})')
    out.append(dict(fonte='Razão', fonte_dados=FONTE_DADOS, periodo=p, empresa=EMP.get(emp, emp),
                    nome_pessoa=None, nome_cliente=dep, vertical=bu(dep), classificacao='despesa',
                    custo_rateado=round(-v, 2), agrupador=agr, macro_area=ma,
                    billable_category='non-billable'))
o = pd.DataFrame(out)

# ---------------- 4. linhas que estao na base hoje ---------------------------------------
rows, off = [], 0
while True:
    z = httpx.get(f'{url}/rest/v1/nova_base', headers=H, timeout=180, params={
        'select': '*', 'fonte': 'eq.Razão', 'fonte_dados': f'eq.{FONTE_DADOS}',
        'periodo': 'gte.2026-04', 'order': 'id', 'limit': 1000, 'offset': off})
    z.raise_for_status()
    b = z.json()
    rows += b
    off += len(b)
    if len(b) < 1000:
        break
atual = pd.DataFrame(rows)
atual = atual[atual.periodo.astype(str).str[:7].isin(MESES.values())] if len(atual) else atual

print(f'\nRazao excluida por ja estar em Despesas gerais da BU: {raz_fora:,.2f}')
print(f'Razao que fica sem departamento (CostCenter vazio):  {sem_cc:,.2f}')
print(f'\nBASE HOJE : {len(atual):4d} linhas  {atual.custo_rateado.sum() if len(atual) else 0:>16,.2f}')
print(f'NOVO      : {len(o):4d} linhas  {o.custo_rateado.sum():>16,.2f}')
print(f'DIFERENCA :            {(o.custo_rateado.sum() - (atual.custo_rateado.sum() if len(atual) else 0)):>16,.2f}')

print('\n=== novo, por macro_area ===')
print(o.assign(ma=o.macro_area.fillna('(VAZIO)')).groupby('ma').custo_rateado.agg(['size', 'sum']).sort_values('sum').to_string(float_format=lambda x: f'{x:,.2f}'))
print('\n=== novo, por departamento ===')
print(o.groupby(['nome_cliente', 'vertical']).custo_rateado.agg(['size', 'sum']).sort_values('sum').to_string(float_format=lambda x: f'{x:,.2f}'))
print('\n=== novo, por vertical (BU) ===')
print(o.groupby('vertical').custo_rateado.agg(['size', 'sum']).sort_values('sum').to_string(float_format=lambda x: f'{x:,.2f}'))
print('\n=== novo, por mes ===')
print(o.groupby('periodo').custo_rateado.sum().to_string(float_format=lambda x: f'{x:,.2f}'))

SP = os.environ.get('SP', '.')
o.to_pickle(os.path.join(SP, '_razao_dep_preview.pkl'))
if not APPLY:
    print('\ndry-run (sem --apply): nada foi gravado')
    sys.exit()

# ---------------- 5. aplica: backup -> delete -> insert ----------------------------------
assert len(atual), 'nao achei as linhas atuais do Razao; abortando para nao duplicar'
bkp = os.path.join(AQUI, '_backup_razao_q2_antes_departamento.json')
json.dump(rows, open(bkp, 'w', encoding='utf-8'), ensure_ascii=False, default=str)
print('backup das linhas atuais em', bkp)

ids = [int(x) for x in atual.id]
for i in range(0, len(ids), 100):
    z = httpx.delete(f'{url}/rest/v1/nova_base', headers=H, timeout=120,
                     params={'id': f'in.({",".join(str(y) for y in ids[i:i + 100])})'})
    assert z.status_code in (200, 204), (z.status_code, z.text[:300])
print('deletadas:', len(ids))

up = str(uuid.uuid4())
agora = datetime.datetime.now(datetime.timezone.utc).isoformat()
ZERO = {c: 0 for c in ('receita', 'horas', 'margem', 'valor_liquido', 'valor', 'taxa_hora', 'hour_price',
                       'gross_revenue', 'custo_gerencial_sap', 'custo_h_hora_extra', 'custo_h_sobreaviso')}
cols = sorted(set(o.columns))
reg = [{**ZERO, **{c: (None if (isinstance(x.get(c), float) and pd.isna(x.get(c))) else x.get(c)) for c in cols},
        'upload_id': up, 'uploaded_at': agora} for x in o.to_dict('records')]
novos = []
for i in range(0, len(reg), 200):
    z = httpx.post(f'{url}/rest/v1/nova_base', headers={**H, 'Prefer': 'return=representation'},
                   json=reg[i:i + 200], timeout=120)
    assert z.status_code in (200, 201), (z.status_code, z.text[:300])
    novos += [y['id'] for y in z.json()]
json.dump({'upload_id': up, 'ids': novos, 'substituiu': ids},
          open(os.path.join(AQUI, '_backup_razao_q2_departamento_ids.json'), 'w'))
print('inseridas:', len(novos), 'upload_id', up)
print('\nLEMBRAR: limpar o cache (POST /api/nova-base/clear-cache) e rodar re_aplicar_ajustes.py --apply')

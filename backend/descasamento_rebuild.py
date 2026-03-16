import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd
import unicodedata, re

WP_PATH = "C:/Users/amanda.paula/FCamara Consultoria e Formação/FCamara Files - CONTROLADORIA/30. FP&A NOVO/06. Cockpit - Desenvolvimentos/NewDashboard/Worker Dashboard/worker_project_20260310.xlsx"
BUILD_UP = "C:/Users/amanda.paula/FCamara Consultoria e Formação/FCamara Files - CONTROLADORIA/30. FP&A NOVO/06. Cockpit - Desenvolvimentos/NewDashboard/Dados para apuração de metas/Build-Up P&L Janeiro26.xlsx"

def norm(s):
    if not isinstance(s, str): return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().upper()

brl = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Load
wp       = pd.read_excel(WP_PATH)
rp       = pd.read_excel("relacao_pessoas.xlsx")
metas    = pd.read_csv("metas_custo.csv", dtype={"numero_pessoal": str})
rac_proj  = pd.read_csv("rac_projetos.csv",  dtype={"pep": str})
rac_pess  = pd.read_csv("rac_pessoas.csv",   dtype={"pep": str, "cpf": str})
marg_pess = pd.read_csv("margem_pessoas.csv", dtype={"pep": str, "cpf": str})
marg_proj = pd.read_csv("margem_projetos.csv", dtype={"pep": str})
clt_bu   = pd.read_excel(BUILD_UP, sheet_name="CLT - DP")
pj_bu    = pd.read_excel(BUILD_UP, sheet_name="Base Pgto PJs")
clt_bu.columns = [c.strip() for c in clt_bu.columns]
pj_bu.columns  = [c.strip() for c in pj_bu.columns]

# Billable classification from build-up
clt_bu['nome_norm'] = clt_bu['Nome'].apply(norm)
clt_bu['billable_category'] = clt_bu['billable_category'].fillna('non-billable')
clt_class = (clt_bu.sort_values('billable_category')
             .drop_duplicates('nome_norm', keep='first')[['nome_norm', 'billable_category']])

pj_bu['nome_norm'] = pj_bu['worker_name'].apply(norm)
pj_class_nome = pj_bu.drop_duplicates('nome_norm', keep='first')[['nome_norm', 'billable_category']]

# Worker project: ALL periods
wp['nome_norm'] = wp['worker_name'].apply(norm)
wp_names_list   = wp['nome_norm'].unique().tolist()
wp_names_set    = set(wp_names_list)
wp_cpfs         = set(wp['worker_id'].dropna().astype(str))

def edit_distance(a, b):
    if a == b: return 0
    if abs(len(a) - len(b)) > 2: return 99
    dp = list(range(len(b) + 1))
    for ca in a:
        ndp = [dp[0] + 1]
        for j, cb in enumerate(b):
            ndp.append(min(dp[j] + (0 if ca == cb else 1), dp[j+1] + 1, ndp[j] + 1))
        dp = ndp
    return dp[len(b)]

def names_compatible(full_parts, wn_parts):
    """True if wp short name is compatible with full base name.
    Rules:
    - First name must fuzzy-match first word of full name (edit <= 1)
    - All wp words must fuzzy-match some word anywhere in full name (edit <= 1)
    - At least one wp word must be an exact match (prevents pure fuzzy false positives)
    """
    if len(wn_parts) < 2 or len(full_parts) < 2:
        return False
    # First name must match first name (fuzzy)
    if edit_distance(wn_parts[0], full_parts[0]) > 1:
        return False
    # All wp words must appear somewhere in full name (fuzzy)
    if not all(any(edit_distance(w, p) <= 1 for p in full_parts) for w in wn_parts):
        return False
    # At least one word must be exact to anchor the match
    return any(w in full_parts for w in wn_parts)

def word_match(full):
    parts = full.split()
    if full in wp_names_set:
        return True
    for wn in wp_names_list:
        wn_p = wn.split()
        if names_compatible(parts, wn_p):
            return True
    return False

def get_best_wp_match(full):
    parts = full.split()
    if full in wp_names_set:
        return full
    best = None
    for wn in wp_names_list:
        wn_p = wn.split()
        if names_compatible(parts, wn_p):
            if best is None or len(wn_p) > len(best.split()):
                best = wn
    return best

# relacao_pessoas link status
rp['nome_norm'] = rp['Nome'].apply(norm)
rp['cpf_norm']  = rp['CPF / Worker ID'].apply(lambda x: str(x).strip() if pd.notna(x) else "")

# Overrides manuais confirmados (nome diferente mas mesma pessoa)
try:
    overrides = pd.read_csv("match_overrides.csv")
    override_set = set(overrides['nome_base_norm'].dropna().unique())
except FileNotFoundError:
    override_set = set()

rp['linked_cpf']      = rp['cpf_norm'].isin(wp_cpfs) & (rp['cpf_norm'].str.len() > 5)
rp['linked_word']     = rp['nome_norm'].apply(word_match)
rp['linked_override'] = rp['nome_norm'].isin(override_set)
rp['linked']          = rp['linked_cpf'] | rp['linked_word'] | rp['linked_override']

# Active Q4
metas_q4 = metas[metas['competencia'].astype(str).str.startswith('2025-1')].copy()
metas_q4['nome_norm'] = metas_q4['nome'].apply(norm)
metas_q4_names = set(metas_q4['nome_norm'])
rp['ativo_q4'] = rp['nome_norm'].isin(metas_q4_names)

# Custo Q4 per person
custo_q4 = (metas_q4.groupby('nome_norm', as_index=False)['custo']
            .sum().rename(columns={'custo': 'custo_q4'}))

# SHEET: Pessoas sem projeto
sem_link = rp[~rp['linked'] & rp['ativo_q4']].copy()
sem_link = sem_link.merge(custo_q4, on='nome_norm', how='left')
sem_link['custo_q4'] = sem_link['custo_q4'].fillna(0).abs()
sem_link = sem_link.merge(clt_class.rename(columns={'billable_category': 'bc_clt'}), on='nome_norm', how='left')
sem_link = sem_link.merge(pj_class_nome.rename(columns={'billable_category': 'bc_pj'}), on='nome_norm', how='left')
sem_link['billable_category'] = sem_link['bc_clt'].fillna(sem_link['bc_pj']).fillna('nao classificado')
sem_link['classificacao'] = sem_link['billable_category'].apply(
    lambda bc: 'despesa' if bc == 'non-billable' else 'custo'
)
sem_link['custo_q4_fmt'] = sem_link['custo_q4'].apply(brl)
sem_link = sem_link.sort_values(['classificacao', 'billable_category', 'Tipo', 'Empresa', 'Nome'])

print(f"Pessoas sem projeto (ativos Q4, todos os periodos wp): {len(sem_link)}")
print(sem_link['billable_category'].value_counts())

# SHEET: Batimento de nomes (nome_base vs nome_wp)
override_map = dict(zip(overrides['nome_base_norm'], overrides['nome_wp_norm'])) if len(override_set) else {}

batimento = []
for _, row in rp[(rp['linked_word'] | rp['linked_override']) & rp['ativo_q4']].iterrows():
    wn = override_map.get(row['nome_norm']) or get_best_wp_match(row['nome_norm'])
    if wn and wn != row['nome_norm']:
        batimento.append({
            'tipo':      row['Tipo'],
            'nome_base': row['Nome'],
            'nome_wp':   wp[wp['nome_norm'] == wn]['worker_name'].iloc[0],
            'empresa':   row['Empresa'],
        })

batimento_df = pd.DataFrame(batimento).sort_values(['tipo', 'nome_base'])
print(f"\nBatimento por nome (diferente): {len(batimento_df)} pares")

# SHEET: Receita sem custo
# Usa PEP base (sem sufixo .0.x) para casar entre fontes
def pep_base(p): return str(p).split('.')[0] if pd.notna(p) else ''

rp_q4      = rac_proj[rac_proj['periodo'].astype(str).str.startswith('2025-1')].copy()
rp_pess_q4 = rac_pess[rac_pess['periodo'].astype(str).str.startswith('2025-1')].copy()

rp_q4['pep_base']      = rp_q4['pep'].apply(pep_base)
rp_pess_q4['pep_base'] = rp_pess_q4['pep'].apply(pep_base)

# Fontes de custo: rac_pessoas + margem_pessoas + margem_projetos (todas com PEP base)
mp_q4 = marg_pess[marg_pess['periodo'].astype(str).str.startswith('2025-1')].copy()
mpr_q4 = marg_proj[marg_proj['periodo'].astype(str).str.startswith('2025-1')].copy()
mp_q4['pep_base']  = mp_q4['pep'].apply(pep_base)
mpr_q4['pep_base'] = mpr_q4['pep'].apply(pep_base)

peps_com_custo = (
    set(rp_pess_q4['pep_base'].dropna()) |
    set(mp_q4['pep_base'].dropna()) |
    set(mpr_q4['pep_base'].dropna())
)
peps_com_receita = set(rp_q4[rp_q4['valor_liquido'].fillna(0) != 0]['pep_base'].dropna())

sem_custo_grp = (
    rp_q4[~rp_q4['pep_base'].isin(peps_com_custo) & (rp_q4['valor_liquido'].fillna(0) != 0)]
    .groupby(['empresa', 'nome_cliente', 'pep', 'tipo'], as_index=False)
    .agg(receita_q4=('valor_liquido', 'sum'),
         meses=('periodo', lambda x: ', '.join(sorted(x.unique()))))
    .sort_values('receita_q4', ascending=False)
)
sem_custo_grp['receita_q4_fmt'] = sem_custo_grp['receita_q4'].apply(brl)

# SHEET: Custo sem receita — todas as fontes de custo
# rac_pessoas: custo por pessoa/PEP (T&E)
pess_sr = (
    rp_pess_q4[~rp_pess_q4['pep_base'].isin(peps_com_receita)]
    .groupby(['empresa', 'pep', 'cpf', 'nome'], as_index=False)
    .agg(custo_q4=('valor_liquido', 'sum'),
         meses=('periodo', lambda x: ', '.join(sorted(x.unique()))))
)
pess_sr['fonte'] = 'rac_pessoas'

# margem_pessoas: custo rateado por pessoa/PEP
mp_sr = (
    mp_q4[~mp_q4['pep_base'].isin(peps_com_receita)]
    .groupby(['empresa', 'pep', 'cpf', 'nome'], as_index=False)
    .agg(custo_q4=('custo_rateado', 'sum'),
         meses=('periodo', lambda x: ', '.join(sorted(x.unique()))))
)
mp_sr['fonte'] = 'margem_pessoas'

# margem_projetos: custo rateado por projeto/PEP (sem pessoa)
mpr_sr = (
    mpr_q4[~mpr_q4['pep_base'].isin(peps_com_receita) & (mpr_q4['custo_rateado'].fillna(0) != 0)]
    .groupby(['empresa', 'pep', 'nome_cliente'], as_index=False)
    .agg(custo_q4=('custo_rateado', 'sum'),
         meses=('periodo', lambda x: ', '.join(sorted(x.unique()))))
)
mpr_sr = mpr_sr.rename(columns={'nome_cliente': 'nome'})
mpr_sr['cpf'] = ''
mpr_sr['fonte'] = 'margem_projetos'

pess_sem_rec = pd.concat([pess_sr, mp_sr, mpr_sr], ignore_index=True)
pess_sem_rec = pess_sem_rec[pess_sem_rec['custo_q4'].fillna(0) != 0].sort_values('custo_q4')
pess_sem_rec['custo_q4_fmt'] = pess_sem_rec['custo_q4'].apply(brl)

# SHEET: Classificacao Billable
clt_all = clt_bu[['Nome', 'Empresa', 'billable_category']].copy()
clt_all.columns = ['nome', 'empresa', 'billable_category']
clt_all['tipo'] = 'CLT'
pj_all = pj_bu[['worker_name', 'name_company', 'billable_category', 'categoria']].copy()
pj_all.columns = ['nome', 'empresa', 'billable_category', 'categoria']
pj_all['tipo'] = 'PJ'
class_all = pd.concat([
    clt_all[['tipo', 'nome', 'empresa', 'billable_category']],
    pj_all[['tipo', 'nome', 'empresa', 'billable_category', 'categoria']],
], ignore_index=True).sort_values(['tipo', 'billable_category', 'nome'])

# SHEET: Resumo
total_receita  = rp_q4['valor_liquido'].sum()
total_sc       = sem_custo_grp['receita_q4'].sum()
total_psr      = abs(pess_sem_rec['custo_q4'].sum())
custo_sem_proj = sem_link[sem_link['classificacao'] == 'custo']['custo_q4'].sum()
desp_sem_proj  = sem_link[sem_link['classificacao'] == 'despesa']['custo_q4'].sum()
n_custo        = (sem_link['classificacao'] == 'custo').sum()
n_desp         = (sem_link['classificacao'] == 'despesa').sum()

resumo = pd.DataFrame([
    {"Categoria": "RECEITA",  "Indicador": "Receita total Q4",                   "Valor": brl(total_receita), "Detalhe": f"{rp_q4['pep_base'].nunique()} PEPs"},
    {"Categoria": "RECEITA",  "Indicador": "Receita sem custo atrelado",          "Valor": brl(total_sc),      "Detalhe": f"{len(sem_custo_grp)} PEPs ({100*total_sc/total_receita:.1f}%) — principalmente Usage Based"},
    {"Categoria": "CUSTO",    "Indicador": "Custo sem projeto (billable/nao classif.)", "Valor": brl(custo_sem_proj), "Detalhe": f"{n_custo} pessoas — entra na Margem Bruta"},
    {"Categoria": "DESPESA",  "Indicador": "Despesa sem projeto (non-billable)",  "Valor": brl(desp_sem_proj), "Detalhe": f"{n_desp} pessoas — abaixo da Margem Bruta"},
    {"Categoria": "CUSTO",    "Indicador": "Custo em PEPs sem receita",           "Valor": brl(total_psr),     "Detalhe": f"{pess_sem_rec['pep'].nunique()} PEPs — rac_pessoas + margem_pessoas + margem_projetos"},
])

# Export
out = "descasamento_receita_custo_q4.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as w:
    resumo.to_excel(w, sheet_name="Resumo", index=False)
    sem_custo_grp[['empresa', 'nome_cliente', 'pep', 'tipo', 'meses', 'receita_q4', 'receita_q4_fmt']].to_excel(w, sheet_name="Receita sem custo", index=False)
    pess_sem_rec[['empresa', 'pep', 'cpf', 'nome', 'meses', 'custo_q4', 'custo_q4_fmt']].to_excel(w, sheet_name="Custo sem receita", index=False)
    sem_link[['Tipo', 'Nome', 'Empresa', 'billable_category', 'classificacao', 'custo_q4', 'custo_q4_fmt']].to_excel(w, sheet_name="Pessoas sem projeto", index=False)
    class_all.assign(classificacao=class_all['billable_category'].apply(lambda bc: 'despesa' if bc == 'non-billable' else 'custo')).to_excel(w, sheet_name="Classificacao Billable", index=False)
    batimento_df.to_excel(w, sheet_name="Batimento de Nomes", index=False)

print(f"\nSalvo: {out}")
print(f"\nResumo P&L:")
print(f"  Receita total Q4:           {brl(total_receita)}")
print(f"  Receita sem custo:          {brl(total_sc)} ({100*total_sc/total_receita:.1f}%)")
print(f"  [CUSTO] sem projeto:        {brl(custo_sem_proj)} — {n_custo} pessoas (billable/nao classif.)")
print(f"  [DESPESA] sem projeto:      {brl(desp_sem_proj)} — {n_desp} pessoas (non-billable)")
print(f"  Custo em PEPs sem receita:  {brl(total_psr)}")
print(f"  Batimento de nomes:           {len(batimento_df)} pares para conferencia")

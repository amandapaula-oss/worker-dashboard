"""
Gera margem_projetos.csv e margem_pessoas.csv
Lógica:
  1. Custo total por pessoa/mês vem de metas_custo.csv (CLT + PJ)
  2. Horas por pessoa/projeto/mês vem de RacFinancial (TimeAndExpenses)
  3. Custo rateado = custo_total_pessoa * (horas_projeto / horas_totais_pessoa)
  4. Receita = valor_liquido do RacFinancial (TE + Fee_WIP + UsageBased)
  5. Margem = Receita - Custo rateado

Execute com: py gen_margem_csv.py
"""
import pathlib
import pandas as pd
import unicodedata
import re
import os
from rapidfuzz import process, fuzz

BASE = list(pathlib.Path("C:/Users/amanda.paula").glob("FCamara*"))[0]
RAC_PATH = (
    BASE / "FCamara Files - CONTROLADORIA" / "30. FP&A NOVO"
    / "06. Cockpit - Desenvolvimentos" / "NewDashboard"
    / "Dados para apuração de metas" / "RacFinancial_Consolidado.xlsx"
)
METAS_CSV = os.path.join(os.path.dirname(__file__), "metas_custo.csv")

COMPANY_NAMES = {
    "BR01": "FCamara", "BR02": "FCamara", "BR03": "FCamara",
    "BR07": "Hyper",   "BR09": "NextGen",  "BR05": "SGA",
    "BR06": "Dojo",    "BR04": "Nação Digital", "BR08": "Omnik",
}

def fmt_periodo(ts):
    if pd.isna(ts): return None
    try:
        t = pd.Timestamp(ts)
        return f"{t.year}-{t.month:02d}"
    except Exception:
        return None

def norm_nome(s):
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s

# ── 1. Ler TimeAndExpenses (horas + receita por pessoa/projeto) ────────────────
print("Lendo TimeAndExpenses...")
te = pd.read_excel(RAC_PATH, sheet_name="TimeAndExpenses", header=1)
te.columns = [c.strip() for c in te.columns]
te = te.rename(columns={
    "Período": "periodo_raw", "EMPRESA": "empresa_cod", "PEP": "pep",
    "NOME CLIENTE": "nome_cliente", "BRCPF": "cpf_raw",
    "PROFISSIONAL": "nome_raw", "HRS APROVADAS": "horas",
    "Valor Liquido :)": "receita",
})
te = te[["periodo_raw","empresa_cod","pep","nome_cliente","cpf_raw","nome_raw","horas","receita"]]
te = te.dropna(subset=["pep","receita"])
te = te[pd.to_numeric(te["receita"], errors="coerce").notna()]
te["receita"]  = te["receita"].astype(float)
te["horas"]    = pd.to_numeric(te["horas"], errors="coerce").fillna(0)
te["periodo"]  = te["periodo_raw"].apply(fmt_periodo)
te["empresa"]  = te["empresa_cod"].map(COMPANY_NAMES).fillna(te["empresa_cod"])
te["cpf"]      = te["cpf_raw"].astype(str).str.strip()
te["nome_norm"] = te["nome_raw"].apply(norm_nome)
te = te.dropna(subset=["periodo"])
te = te[te["periodo"] <= "2025-12"]
print(f"  {len(te)} linhas com {te['pep'].nunique()} projetos únicos")

# ── 2. Ler metas_custo (custo CLT + PJ por pessoa/mês) ────────────────────────
print("Lendo metas_custo.csv...")
metas = pd.read_csv(METAS_CSV, dtype={"numero_pessoal": str})
metas["nome_norm"] = metas["nome"].apply(norm_nome)
metas["custo"] = pd.to_numeric(metas["custo"], errors="coerce").fillna(0)

# Custo total por pessoa/mês  (identidade = (periodo, cpf_ou_nome))
# Para PJ: join por CPF (numero_pessoal = BRCPFXXXXX)
# Para CLT: join por nome normalizado (SAP IDs não batem)
pj  = metas[metas["tipo"] == "PJ"].copy()
clt = metas[metas["tipo"] == "CLT"].copy()

custo_pj  = pj.groupby(["competencia","numero_pessoal","nome_norm"], as_index=False)["custo"].sum()
custo_clt = clt.groupby(["competencia","nome_norm"], as_index=False)["custo"].sum()
print(f"  PJ: {len(custo_pj)} registros pessoa/mês | CLT: {len(custo_clt)} registros pessoa/mês")

# ── Fuzzy match: mapeia nomes do RAC para nomes do metas_custo ────────────────
print("Construindo mapa fuzzy de nomes...")
FUZZY_THRESHOLD = 88  # score mínimo (0-100)

# Confirmados manualmente como mesma pessoa
FUZZY_FORCE = {
    "PEDRO HENRIQUE SILVA":          "PEDRO HENRIQUE SILVA EGG",
    "DENISE DOS SANTOS CAMPANHA":    "DENISE DOS SANTOS CAMPANHA MURO",
    "GUILHERME SOARES DOS SANTOS":   "GUILHERME SOARES DOS SANTOS SOUSA",
    "JAMILLE RENATA FERREIRA PEREIRA": "JAMILLE RENATA FERREIRA PEREIRA RICHTER",
}

all_metas_nomes = list(metas["nome_norm"].unique())

# Cache: nome_norm_rac → nome_norm_metas (ou None se abaixo do threshold)
_fuzzy_cache: dict = {}

def fuzzy_map(nome_norm_rac: str) -> str | None:
    if nome_norm_rac in _fuzzy_cache:
        return _fuzzy_cache[nome_norm_rac]
    result = process.extractOne(
        nome_norm_rac, all_metas_nomes,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=FUZZY_THRESHOLD,
    )
    mapped = result[0] if result else None
    _fuzzy_cache[nome_norm_rac] = mapped
    return mapped

# Aplica apenas nos nomes que não têm match exato
exact_nomes = set(all_metas_nomes)
te_sem_match = te[~te["nome_norm"].isin(exact_nomes)]["nome_norm"].unique()
print(f"  Nomes sem match exato: {len(te_sem_match)} — aplicando fuzzy...")

fuzzy_map_dict = {}
for n in te_sem_match:
    mapped = fuzzy_map(n)
    if mapped:
        fuzzy_map_dict[n] = mapped

print(f"  Fuzzy matches encontrados: {len(fuzzy_map_dict)} de {len(te_sem_match)}")
if fuzzy_map_dict:
    print("  Exemplos de fuzzy matches:")
    for orig, mapped in list(fuzzy_map_dict.items())[:8]:
        print(f"    '{orig}' -> '{mapped}'")

# Cria coluna nome_norm_join: força confirmados, depois exato, depois fuzzy
te["nome_norm_join"] = te["nome_norm"].apply(
    lambda n: FUZZY_FORCE.get(n) or (n if n in exact_nomes else fuzzy_map_dict.get(n, n))
)

# ── 3. Calcular horas totais por pessoa/mês ────────────────────────────────────
horas_totais = te.groupby(["periodo","cpf","nome_norm"])["horas"].sum().reset_index()
horas_totais = horas_totais.rename(columns={"horas": "horas_total"})

te = te.merge(horas_totais, on=["periodo","cpf","nome_norm"], how="left")

# ── 4. Join de custo: PJ via CPF, CLT via nome (exato + fuzzy) ────────────────
# PJ join
te_pj = te.merge(
    custo_pj.rename(columns={"competencia":"periodo","numero_pessoal":"cpf","custo":"custo_pessoa"}),
    on=["periodo","cpf"], how="left", suffixes=("","_pj")
)

# CLT join por nome_norm_join (inclui fuzzy)
te_pj = te_pj.merge(
    custo_clt.rename(columns={"competencia":"periodo","nome_norm":"nome_norm_join","custo":"custo_clt"}),
    on=["periodo","nome_norm_join"], how="left"
)

# Escolhe custo: PJ tem prioridade (se existir), senão CLT
te_pj["custo_pessoa"] = te_pj["custo_pessoa"].fillna(te_pj["custo_clt"])
te_pj["custo_pessoa"] = te_pj["custo_pessoa"].fillna(0)

# ── 5. Ratear custo por horas ──────────────────────────────────────────────────
te_pj["fator"] = te_pj.apply(
    lambda r: r["horas"] / r["horas_total"] if r["horas_total"] > 0 else 0, axis=1
)
te_pj["custo_rateado"] = te_pj["custo_pessoa"] * te_pj["fator"]

matched = (te_pj["custo_pessoa"] != 0).sum()
total   = len(te_pj)
print(f"\nMatch custo: {matched}/{total} linhas ({matched/total*100:.1f}%)")

# ── 6. Agregar por projeto ─────────────────────────────────────────────────────
proj = te_pj.groupby(["pep","nome_cliente","empresa"], as_index=False).agg(
    receita      = ("receita",       "sum"),
    custo_rateado= ("custo_rateado", "sum"),
    horas_total  = ("horas",         "sum"),
)
proj["margem"]     = proj["receita"] + proj["custo_rateado"]  # custo já é negativo
proj["margem_pct"] = proj.apply(
    lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
)

# Adiciona Fee_WIP e UsageBased (receita sem custo rateado)
print("Lendo Fee_WIP e UsageBased...")
fw = pd.read_excel(RAC_PATH, sheet_name="Fee_WIP", header=1)
fw.columns = [c.strip() for c in fw.columns]
fw = fw.rename(columns={"Período":"periodo_raw","EMPRESA":"empresa_cod","PEP":"pep",
                         "NOME CLIENTE":"nome_cliente","Formula Líquido":"receita"})
fw = fw[["periodo_raw","empresa_cod","pep","nome_cliente","receita"]].dropna(subset=["pep","receita"])
fw = fw[pd.to_numeric(fw["receita"], errors="coerce").notna()]
fw["receita"] = fw["receita"].astype(float)
fw["periodo"] = fw["periodo_raw"].apply(fmt_periodo)
fw = fw[fw["periodo"] <= "2025-12"]
fw["empresa"] = fw["empresa_cod"].map(COMPANY_NAMES).fillna(fw["empresa_cod"])
fw_agg = fw.groupby(["pep","nome_cliente","empresa"], as_index=False).agg(receita=("receita","sum"))
fw_agg["custo_rateado"] = 0.0
fw_agg["horas_total"]   = 0.0
fw_agg["margem"]        = fw_agg["receita"]
fw_agg["margem_pct"]    = 1.0
fw_agg["tipo"]          = "Fee_WIP"

ub = pd.read_excel(RAC_PATH, sheet_name="UsageBased", header=1)
ub.columns = [c.strip() for c in ub.columns]
ub = ub.rename(columns={"Período":"periodo_raw","EMPRESA":"empresa_cod","PEP":"pep",
                         "NOME CLIENTE":"nome_cliente","Valor Liquido :)":"receita"})
ub = ub[["periodo_raw","empresa_cod","pep","nome_cliente","receita"]].dropna(subset=["pep","receita"])
ub = ub[pd.to_numeric(ub["receita"], errors="coerce").notna()]
ub["receita"] = ub["receita"].astype(float)
ub["periodo"] = ub["periodo_raw"].apply(fmt_periodo)
ub = ub[ub["periodo"] <= "2025-12"]
ub["empresa"] = ub["empresa_cod"].map(COMPANY_NAMES).fillna(ub["empresa_cod"])
ub_agg = ub.groupby(["pep","nome_cliente","empresa"], as_index=False).agg(receita=("receita","sum"))
ub_agg["custo_rateado"] = 0.0
ub_agg["horas_total"]   = 0.0
ub_agg["margem"]        = ub_agg["receita"]
ub_agg["margem_pct"]    = 1.0
ub_agg["tipo"]          = "UsageBased"

proj["tipo"] = "TimeAndExpenses"

proj_final = pd.concat([proj, fw_agg, ub_agg], ignore_index=True)
proj_final = proj_final.groupby(["pep","nome_cliente","empresa"], as_index=False).agg(
    receita      = ("receita",       "sum"),
    custo_rateado= ("custo_rateado", "sum"),
    horas_total  = ("horas_total",   "sum"),
).assign(
    margem    = lambda d: d["receita"] + d["custo_rateado"],
    margem_pct= lambda d: d.apply(lambda r: r["margem"]/r["receita"] if r["receita"]!=0 else None, axis=1),
)

# ── 7. Agregar por pessoa/projeto ──────────────────────────────────────────────
pess_final = te_pj.groupby(["pep","cpf","nome_raw","empresa"], as_index=False).agg(
    receita      = ("receita",       "sum"),
    custo_rateado= ("custo_rateado", "sum"),
    horas        = ("horas",         "sum"),
).rename(columns={"nome_raw":"nome"})
pess_final["margem"] = pess_final["receita"] + pess_final["custo_rateado"]

# ── 8. Salvar ──────────────────────────────────────────────────────────────────
out_dir = os.path.dirname(__file__)

proj_path = os.path.join(out_dir, "margem_projetos.csv")
proj_final.to_csv(proj_path, index=False)
print(f"\nSalvo: {proj_path} ({len(proj_final)} projetos)")

pess_path = os.path.join(out_dir, "margem_pessoas.csv")
pess_final.to_csv(pess_path, index=False)
print(f"Salvo: {pess_path} ({len(pess_final)} linhas pessoa/projeto)")

print("\nResumo geral:")
print(f"  Receita total:       R$ {proj_final['receita'].sum():>15,.0f}")
print(f"  Custo rateado total: R$ {proj_final['custo_rateado'].sum():>15,.0f}")
print(f"  Margem total:        R$ {proj_final['margem'].sum():>15,.0f}")
margem_pct = proj_final['margem'].sum() / proj_final['receita'].sum() * 100
print(f"  Margem %:            {margem_pct:.1f}%")
print(f"\nProjetos sem custo rateado: {(proj_final['custo_rateado']==0).sum()}")

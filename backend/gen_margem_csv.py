"""
Gera margem_projetos.csv e margem_pessoas.csv
Lógica:
  1. Custo total por pessoa/mês vem de metas_custo.csv (CLT + PJ)
  2. Horas por pessoa/projeto/mês vem de RacFinancial (TimeAndExpenses)
  3. Custo rateado = custo_total_pessoa * (horas_projeto / horas_totais_pessoa)
  4. Receita = valor_liquido do RacFinancial (TE + Fee_WIP + UsageBased)
  5. Margem = Receita - Custo rateado
  5b. Para pessoas sem horas no RacFinancial: ratear custo por receita dos projetos
      via worker_project_20260310.xlsx

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
WP_PATH   = (
    BASE / "FCamara Files - CONTROLADORIA" / "30. FP&A NOVO"
    / "06. Cockpit - Desenvolvimentos" / "NewDashboard"
    / "Dados para apuração de metas" / "worker_project_20260310.xlsx"
)

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
print(f"\nMatch custo (por horas): {matched}/{total} linhas ({matched/total*100:.1f}%)")

# ── 5b. Ler Fee_WIP e UsageBased para calcular receita por projeto ─────────────
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
fw_agg = fw.groupby(["periodo","pep","nome_cliente","empresa"], as_index=False).agg(receita=("receita","sum"))
fw_agg["custo_rateado"] = 0.0
fw_agg["horas_total"]   = 0.0

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
ub_agg = ub.groupby(["periodo","pep","nome_cliente","empresa"], as_index=False).agg(receita=("receita","sum"))
ub_agg["custo_rateado"] = 0.0
ub_agg["horas_total"]   = 0.0

# Receita total por (periodo, pep) — usada para rateio por receita abaixo
proj_te_receita = te_pj.groupby(["periodo","pep"], as_index=False)["receita"].sum()
proj_fw_receita = fw_agg[["periodo","pep","receita"]].copy()
proj_ub_receita = ub_agg[["periodo","pep","receita"]].copy()
proj_receita_all = pd.concat([proj_te_receita, proj_fw_receita, proj_ub_receita], ignore_index=True)
proj_receita_all = proj_receita_all.groupby(["periodo","pep"], as_index=False)["receita"].sum()
proj_receita_all = proj_receita_all.rename(columns={"receita": "receita_proj"})

# ── 5c. Complementar rateio para pessoas sem horas (via worker_project) ────────
print("\nComplementando rateio via worker_project...")
wp = pd.read_excel(WP_PATH, sheet_name="Dados")
wp.columns = [c.strip() for c in wp.columns]
wp["periodo"] = wp["competencia"].apply(fmt_periodo)
wp = wp[wp["periodo"].notna()]
wp = wp[wp["periodo"].between("2025-10", "2025-12")]
wp["cpf"]     = wp["worker_id"].astype(str).str.strip()
wp["pep"]     = wp["wbs_element"].astype(str).str.strip()
wp["nome_wp"] = wp["worker_name"].astype(str).str.strip()
wp["nome_norm_wp"] = wp["nome_wp"].apply(norm_nome)
wp["empresa_wp"] = wp["Empresa"].astype(str).str.strip().map(COMPANY_NAMES).fillna(
    wp["Empresa"].astype(str).str.strip()
)
print(f"  worker_project: {len(wp)} registros, {wp['cpf'].nunique()} workers")

# Conjunto de (periodo, cpf) que JÁ têm custo rateado via horas
pessoas_com_horas = set(
    zip(te_pj[te_pj["horas"] > 0]["periodo"], te_pj[te_pj["horas"] > 0]["cpf"])
)

# ── PJ sem horas: identificados por CPF ───────────────────────────────────────
pj_sem_horas = custo_pj.rename(columns={"competencia":"periodo","numero_pessoal":"cpf"})[
    ["periodo","cpf","nome_norm","custo"]
].copy()
pj_sem_horas = pj_sem_horas[
    ~pj_sem_horas.apply(lambda r: (r["periodo"], r["cpf"]) in pessoas_com_horas, axis=1)
]
print(f"  PJ sem horas no RacFinancial: {len(pj_sem_horas)} registros pessoa/mês")

# Juntar PJ sem horas com worker_project por CPF
if len(pj_sem_horas) > 0:
    complement_pj = pj_sem_horas.merge(
        wp[["periodo","cpf","pep","empresa_wp","nome_wp"]].drop_duplicates(subset=["periodo","cpf","pep"]),
        on=["periodo","cpf"], how="inner"
    )
    complement_pj = complement_pj.rename(columns={"nome_norm":"nome_metas","empresa_wp":"empresa"})
    complement_pj["nome"] = complement_pj["nome_wp"]
else:
    complement_pj = pd.DataFrame(columns=["periodo","cpf","pep","empresa","nome","custo"])

# ── CLT sem horas: identificados por nome normalizado ─────────────────────────
# Conjunto de (periodo, nome_norm_join) com horas
pessoas_clt_com_horas = set(
    zip(te_pj[te_pj["horas"] > 0]["periodo"], te_pj[te_pj["horas"] > 0]["nome_norm_join"])
)

clt_sem_horas = custo_clt.rename(columns={"competencia":"periodo"})[
    ["periodo","nome_norm","custo"]
].copy()
clt_sem_horas = clt_sem_horas[
    ~clt_sem_horas.apply(lambda r: (r["periodo"], r["nome_norm"]) in pessoas_clt_com_horas, axis=1)
]
print(f"  CLT sem horas no RacFinancial: {len(clt_sem_horas)} registros pessoa/mês")

# Juntar CLT sem horas com worker_project por nome normalizado
if len(clt_sem_horas) > 0:
    complement_clt = clt_sem_horas.merge(
        wp[["periodo","nome_norm_wp","cpf","pep","empresa_wp","nome_wp"]].rename(
            columns={"nome_norm_wp":"nome_norm"}
        ).drop_duplicates(subset=["periodo","nome_norm","pep"]),
        on=["periodo","nome_norm"], how="inner"
    )
    complement_clt = complement_clt.rename(columns={"empresa_wp":"empresa"})
    complement_clt["nome"] = complement_clt["nome_wp"]
else:
    complement_clt = pd.DataFrame(columns=["periodo","cpf","pep","empresa","nome","custo"])

# Unir complementos PJ + CLT
complement_all = pd.concat([
    complement_pj[["periodo","cpf","pep","empresa","nome","custo"]],
    complement_clt[["periodo","cpf","pep","empresa","nome","custo"]],
], ignore_index=True).drop_duplicates(subset=["periodo","cpf","pep"])
print(f"  Complemento total: {len(complement_all)} registros pessoa/projeto")

# Ratear custo por receita do projeto
complement_all = complement_all.merge(proj_receita_all, on=["periodo","pep"], how="left")
complement_all["receita_proj"] = complement_all["receita_proj"].fillna(0)

# Receita total dos projetos onde cada pessoa está alocada naquele período
receita_total_pessoa = complement_all.groupby(["periodo","cpf"])["receita_proj"].sum().reset_index()
receita_total_pessoa = receita_total_pessoa.rename(columns={"receita_proj": "receita_total_pessoa"})
complement_all = complement_all.merge(receita_total_pessoa, on=["periodo","cpf"], how="left")

complement_all["fator_receita"] = complement_all.apply(
    lambda r: r["receita_proj"] / r["receita_total_pessoa"]
    if r["receita_total_pessoa"] > 0 else 1.0 / max(1, len(complement_all[
        (complement_all["periodo"] == r["periodo"]) & (complement_all["cpf"] == r["cpf"])
    ])),
    axis=1
)
complement_all["custo_rateado"] = complement_all["custo"] * complement_all["fator_receita"]
complement_all["receita"] = 0.0
complement_all["horas"]   = 0.0

n_matched = (complement_all["receita_proj"] > 0).sum()
print(f"  Complemento com receita de projeto: {n_matched}/{len(complement_all)}")

# ── 6. Agregar por projeto + período ──────────────────────────────────────────
proj = te_pj.groupby(["periodo","pep","nome_cliente","empresa"], as_index=False).agg(
    receita      = ("receita",       "sum"),
    custo_rateado= ("custo_rateado", "sum"),
    horas_total  = ("horas",         "sum"),
)

# Adicionar custo rateado do complemento por projeto (via nome_cliente lookup)
pep_info = te[["pep","nome_cliente","empresa"]].drop_duplicates(subset=["pep"]).copy()
complement_proj = complement_all.groupby(["periodo","pep"], as_index=False)["custo_rateado"].sum()
complement_proj = complement_proj.rename(columns={"custo_rateado": "custo_complement"})
complement_proj = complement_proj.merge(pep_info, on="pep", how="left")
# Para projetos sem nome no TE, buscar no fw/ub
fw_pep_info = fw[["pep","nome_cliente","empresa"]].drop_duplicates(subset=["pep"])
ub_pep_info = ub[["pep","nome_cliente","empresa"]].drop_duplicates(subset=["pep"])
all_pep_info = pd.concat([pep_info, fw_pep_info, ub_pep_info]).drop_duplicates(subset=["pep"])
complement_proj_with_info = complement_all.groupby(["periodo","pep"], as_index=False)["custo_rateado"].sum()
complement_proj_with_info = complement_proj_with_info.rename(columns={"custo_rateado": "custo_complement"})
complement_proj_with_info = complement_proj_with_info.merge(all_pep_info, on="pep", how="left")

proj_final = pd.concat([proj, fw_agg, ub_agg], ignore_index=True)
proj_final = proj_final.groupby(["periodo","pep","nome_cliente","empresa"], as_index=False).agg(
    receita      = ("receita",       "sum"),
    custo_rateado= ("custo_rateado", "sum"),
    horas_total  = ("horas_total",   "sum"),
)

# Somar custo do complemento ao proj_final
if len(complement_proj_with_info) > 0:
    proj_final = proj_final.merge(
        complement_proj_with_info[["periodo","pep","custo_complement"]],
        on=["periodo","pep"], how="left"
    )
    proj_final["custo_complement"] = proj_final["custo_complement"].fillna(0)
    proj_final["custo_rateado"] = proj_final["custo_rateado"] + proj_final["custo_complement"]
    proj_final = proj_final.drop(columns=["custo_complement"])

proj_final = proj_final.assign(
    receita_rac  = lambda d: d["receita"],   # guarda original para fator depois
    margem       = lambda d: d["receita"] + d["custo_rateado"],
    margem_pct   = lambda d: d.apply(lambda r: r["margem"]/r["receita"] if r["receita"]!=0 else None, axis=1),
)

# ── 6b. Substituir receita pelo MapaReceita (rac_projetos.csv) ─────────────────
# Agregar proj_final por pep_base para evitar dupla contagem (múltiplos sub-PEPs)
print("\nSubstituindo receita pelo MapaReceita (rac_projetos.csv)...")
RAC_PROJ_CSV = os.path.join(os.path.dirname(__file__), "rac_projetos.csv")
mapa = pd.read_csv(RAC_PROJ_CSV, dtype={"pep": str})
mapa["pep_base"] = mapa["pep"].str.split(".").str[0]
mapa_agg = mapa.groupby(["periodo","pep_base"], as_index=False)["valor_liquido"].sum()
mapa_agg = mapa_agg.rename(columns={"valor_liquido": "receita_mapa"})

# Normalizar PEPs de proj_final para pep_base e reagregar (elimina sub-PEPs duplicados)
proj_final["pep_base"] = proj_final["pep"].str.split(".").str[0]
pep_meta = (proj_final.sort_values("receita_rac", ascending=False)
            .drop_duplicates(subset=["periodo","pep_base"])[["periodo","pep_base","nome_cliente","empresa"]])
proj_base = proj_final.groupby(["periodo","pep_base"], as_index=False).agg(
    receita_rac  = ("receita_rac",   "sum"),
    custo_rateado= ("custo_rateado", "sum"),
    horas_total  = ("horas_total",   "sum"),
)
proj_base = proj_base.merge(pep_meta, on=["periodo","pep_base"], how="left")

# Outer join: inclui PEPs só no mapa (receita sem custo) e PEPs só no RAC (custo sem receita)
proj_base = proj_base.merge(mapa_agg, on=["periodo","pep_base"], how="outer")
mapa_info = mapa[["pep_base","nome_cliente","empresa"]].drop_duplicates("pep_base").rename(
    columns={"nome_cliente":"nc_m","empresa":"emp_m"}
)
proj_base = proj_base.merge(mapa_info, on="pep_base", how="left")
proj_base["nome_cliente"] = proj_base["nome_cliente"].fillna(proj_base["nc_m"])
proj_base["empresa"]      = proj_base["empresa"].fillna(proj_base["emp_m"])
proj_base = proj_base.drop(columns=["nc_m","emp_m"])

proj_base["custo_rateado"] = proj_base["custo_rateado"].fillna(0)
proj_base["horas_total"]   = proj_base["horas_total"].fillna(0)
proj_base["receita_rac"]   = proj_base["receita_rac"].fillna(0)
proj_base["receita"]       = proj_base["receita_mapa"].fillna(0)  # sem fallback: receita vem só do mapa
proj_base["fator_mapa"]    = proj_base.apply(
    lambda r: r["receita"] / r["receita_rac"] if r["receita_rac"] != 0 else 1.0, axis=1
)
proj_base["pep"] = proj_base["pep_base"]  # usar pep_base como chave

proj_final = proj_base.assign(
    margem    = lambda d: d["receita"] + d["custo_rateado"],
    margem_pct= lambda d: d.apply(lambda r: r["margem"]/r["receita"] if r["receita"]!=0 else None, axis=1),
)
print(f"  Receita MapaReceita total: R$ {proj_final['receita'].sum():,.0f}")
print(f"  PEPs com receita mapa: {proj_final['receita_mapa'].notna().sum()}")
print(f"  PEPs só com custo (sem receita mapa): {proj_final['receita_mapa'].isna().sum()}")

# ── 7. Agregar por pessoa/projeto/período ──────────────────────────────────────
pess_te = te_pj.groupby(["periodo","pep","cpf","nome_raw","empresa"], as_index=False).agg(
    receita      = ("receita",       "sum"),
    custo_rateado= ("custo_rateado", "sum"),
    horas        = ("horas",         "sum"),
).rename(columns={"nome_raw":"nome"})

# Adicionar pessoas do complemento
pess_complement = complement_all[["periodo","pep","cpf","nome","empresa","receita","custo_rateado","horas"]].copy()

pess_final = pd.concat([pess_te, pess_complement], ignore_index=True)
pess_final = pess_final.groupby(["periodo","pep","cpf","nome","empresa"], as_index=False).agg(
    receita      = ("receita",       "sum"),
    custo_rateado= ("custo_rateado", "sum"),
    horas        = ("horas",         "sum"),
)
pess_final["margem"] = pess_final["receita"] + pess_final["custo_rateado"]

# Escalar receita das pessoas pelo fator MapaReceita
fator_lookup = proj_final.set_index(["periodo","pep_base"])["fator_mapa"].to_dict()
pess_final["pep_base"] = pess_final["pep"].str.split(".").str[0]
pess_final["receita"] = pess_final.apply(
    lambda r: r["receita"] * fator_lookup.get((r["periodo"], r["pep_base"]), 1.0), axis=1
)
pess_final["margem"] = pess_final["receita"] + pess_final["custo_rateado"]
pess_final = pess_final.drop(columns=["pep_base"], errors="ignore")

# ── 8. Salvar ──────────────────────────────────────────────────────────────────
out_dir = os.path.dirname(__file__)

proj_cols = ["periodo","pep","nome_cliente","empresa","receita","custo_rateado","horas_total","margem","margem_pct"]
proj_path = os.path.join(out_dir, "margem_projetos.csv")
proj_final[proj_cols].to_csv(proj_path, index=False)
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
custo_complement_total = complement_all["custo_rateado"].sum()
print(f"Custo complementado (sem horas): R$ {custo_complement_total:,.0f} ({len(complement_all)} registros)")

"""
Gera rac_projetos.csv e rac_pessoas.csv a partir do RacFinancial_Consolidado.xlsx
Execute com: py gen_rac_csv.py
"""
import pathlib
import pandas as pd
import os

BASE = list(pathlib.Path("C:/Users/amanda.paula").glob("FCamara*"))[0]
RAC_PATH = (
    BASE
    / "FCamara Files - CONTROLADORIA"
    / "30. FP&A NOVO"
    / "06. Cockpit - Desenvolvimentos"
    / "NewDashboard"
    / "Dados para apuração de metas"
    / "RacFinancial_Consolidado.xlsx"
)

COMPANY_NAMES = {
    "BR01": "FCamara", "BR02": "FCamara", "BR03": "FCamara",
    "BR07": "Hyper",   "BR09": "NextGen",  "BR05": "SGA",
    "BR06": "Dojo",    "BR04": "Nação Digital", "BR08": "Omnik",
}

def fmt_periodo(ts):
    if pd.isna(ts):
        return None
    try:
        t = pd.Timestamp(ts)
        return f"{t.year}-{t.month:02d}"
    except Exception:
        return None

records_proj  = []
records_pess  = []

# ── TimeAndExpenses ────────────────────────────────────────────────────────────
print("Lendo TimeAndExpenses...")
te = pd.read_excel(RAC_PATH, sheet_name="TimeAndExpenses", header=1)
te.columns = [c.strip() for c in te.columns]
te = te.rename(columns={
    "Período": "periodo_raw", "EMPRESA": "empresa_cod", "PEP": "pep",
    "NOME CLIENTE": "nome_cliente", "BRCPF": "cpf",
    "PROFISSIONAL": "nome", "Valor Liquido :)": "valor_liquido",
})
te = te[["periodo_raw","empresa_cod","pep","nome_cliente","cpf","nome","valor_liquido"]].dropna(subset=["pep","valor_liquido"])
te = te[pd.to_numeric(te["valor_liquido"], errors="coerce").notna()]
te["valor_liquido"] = te["valor_liquido"].astype(float)
te["periodo"] = te["periodo_raw"].apply(fmt_periodo)
te["empresa"] = te["empresa_cod"].map(COMPANY_NAMES).fillna(te["empresa_cod"])
te["tipo"] = "TimeAndExpenses"
te = te.dropna(subset=["periodo"])

# projetos (nível PEP)
for _, row in te.iterrows():
    records_proj.append({
        "periodo": row["periodo"], "empresa": row["empresa"],
        "pep": row["pep"], "nome_cliente": row["nome_cliente"],
        "tipo": "TimeAndExpenses", "valor_liquido": row["valor_liquido"],
    })

# pessoas
for _, row in te.iterrows():
    records_pess.append({
        "periodo": row["periodo"], "empresa": row["empresa"],
        "pep": row["pep"], "cpf": str(row["cpf"]).strip() if pd.notna(row["cpf"]) else "",
        "nome": str(row["nome"]).strip() if pd.notna(row["nome"]) else "",
        "valor_liquido": row["valor_liquido"],
    })

print(f"  TimeAndExpenses: {len(te)} linhas")

# ── Fee_WIP ────────────────────────────────────────────────────────────────────
print("Lendo Fee_WIP...")
fw = pd.read_excel(RAC_PATH, sheet_name="Fee_WIP", header=1)
fw.columns = [c.strip() for c in fw.columns]
fw = fw.rename(columns={
    "Período": "periodo_raw", "EMPRESA": "empresa_cod", "PEP": "pep",
    "NOME CLIENTE": "nome_cliente", "Formula Líquido": "valor_liquido",
})
fw = fw[["periodo_raw","empresa_cod","pep","nome_cliente","valor_liquido"]].dropna(subset=["pep","valor_liquido"])
fw = fw[pd.to_numeric(fw["valor_liquido"], errors="coerce").notna()]
fw["valor_liquido"] = fw["valor_liquido"].astype(float)
fw["periodo"] = fw["periodo_raw"].apply(fmt_periodo)
fw["empresa"] = fw["empresa_cod"].map(COMPANY_NAMES).fillna(fw["empresa_cod"])
fw = fw.dropna(subset=["periodo"])

for _, row in fw.iterrows():
    records_proj.append({
        "periodo": row["periodo"], "empresa": row["empresa"],
        "pep": row["pep"], "nome_cliente": row["nome_cliente"],
        "tipo": "Fee_WIP", "valor_liquido": row["valor_liquido"],
    })

print(f"  Fee_WIP: {len(fw)} linhas")

# ── UsageBased ─────────────────────────────────────────────────────────────────
print("Lendo UsageBased...")
ub = pd.read_excel(RAC_PATH, sheet_name="UsageBased", header=1)
ub.columns = [c.strip() for c in ub.columns]
ub = ub.rename(columns={
    "Período": "periodo_raw", "EMPRESA": "empresa_cod", "PEP": "pep",
    "NOME CLIENTE": "nome_cliente", "Valor Liquido :)": "valor_liquido",
})
ub = ub[["periodo_raw","empresa_cod","pep","nome_cliente","valor_liquido"]].dropna(subset=["pep","valor_liquido"])
ub = ub[pd.to_numeric(ub["valor_liquido"], errors="coerce").notna()]
ub["valor_liquido"] = ub["valor_liquido"].astype(float)
ub["periodo"] = ub["periodo_raw"].apply(fmt_periodo)
ub["empresa"] = ub["empresa_cod"].map(COMPANY_NAMES).fillna(ub["empresa_cod"])
ub = ub.dropna(subset=["periodo"])

for _, row in ub.iterrows():
    records_proj.append({
        "periodo": row["periodo"], "empresa": row["empresa"],
        "pep": row["pep"], "nome_cliente": row["nome_cliente"],
        "tipo": "UsageBased", "valor_liquido": row["valor_liquido"],
    })

print(f"  UsageBased: {len(ub)} linhas")

# ── Salvar ─────────────────────────────────────────────────────────────────────
out_dir = os.path.dirname(__file__)

df_proj = pd.DataFrame(records_proj)
df_proj_agg = (
    df_proj.groupby(["periodo","empresa","pep","nome_cliente","tipo"], as_index=False)
    ["valor_liquido"].sum()
)
proj_path = os.path.join(out_dir, "rac_projetos.csv")
df_proj_agg.to_csv(proj_path, index=False)
print(f"\nSalvo: {proj_path} ({len(df_proj_agg)} linhas)")

df_pess = pd.DataFrame(records_pess)
df_pess_agg = (
    df_pess.groupby(["periodo","empresa","pep","cpf","nome"], as_index=False)
    ["valor_liquido"].sum()
)
pess_path = os.path.join(out_dir, "rac_pessoas.csv")
df_pess_agg.to_csv(pess_path, index=False)
print(f"Salvo: {pess_path} ({len(df_pess_agg)} linhas)")

print("\nPor período:")
print(df_proj_agg.groupby("periodo")["valor_liquido"].sum().apply(lambda x: f"R$ {x:,.0f}").to_string())

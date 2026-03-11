"""
Gera metas_custo.csv a partir das planilhas de CLT e PJ.
Execute com: py gen_metas_csv.py
"""
import pandas as pd
import os
import re
from glob import glob

CLT_PATH = "C:/Users/amanda.paula/FCamara Consultoria e Formação/FCamara Files - CONTROLADORIA/30. FP&A NOVO/06. Cockpit - Desenvolvimentos/NewDashboard/Dados para apuração de metas/CLTs/"
PJ_PATH  = "C:/Users/amanda.paula/FCamara Consultoria e Formação/FCamara Files - CONTROLADORIA/30. FP&A NOVO/06. Cockpit - Desenvolvimentos/NewDashboard/Dados para apuração de metas/PJ/"

COMPANY_NAMES = {
    "BR01": "FCamara", "BR02": "FCamara", "BR07": "Hyper", "BR09": "NextGen",
    "BR05": "SGA", "BR06": "Dojo", "BR04": "Nação Digital", "BR08": "Omnik",
}

records = []

# ── CLT ───────────────────────────────────────────────────────────────────────
print("Lendo CLT...")
for filepath in sorted(glob(CLT_PATH + "Custo Gerencial Grupo *.xlsx")):
    filename = os.path.basename(filepath)
    m = re.search(r'(\d{2})\.(\d{2})\.xlsx', filename)
    if not m:
        print(f"  Ignorado (sem mês): {filename}")
        continue
    mes_num, ano_num = m.group(1), m.group(2)
    competencia = f"20{ano_num}-{mes_num}"

    xl = pd.ExcelFile(filepath)
    sheet = next((s for s in xl.sheet_names if s.lower() == "consolidado"), None)
    if not sheet:
        print(f"  Ignorado (sem aba Consolidado): {filename}")
        continue

    df = pd.read_excel(filepath, sheet_name=sheet)

    id_col = next((c for c in df.columns
                   if "pessoal" in str(c).lower()
                   or ("id" in str(c).lower() and "sap" in str(c).lower())), None)
    custo_col = next((c for c in df.columns if "gerencial" in str(c).lower()), None)
    if not custo_col:
        custo_col = next((c for c in df.columns if "valor custo" in str(c).lower()), None)
    if not custo_col:
        custo_col = next((c for c in df.columns if "custo dp" in str(c).lower()), None)

    if not id_col or not custo_col:
        print(f"  Aviso: colunas não encontradas em {filename} — id={id_col}, custo={custo_col}")
        continue

    df_valid = df.dropna(subset=["Empresa", "Nome"])
    df_valid = df_valid[pd.to_numeric(df_valid[custo_col], errors="coerce").notna()]

    for _, row in df_valid.iterrows():
        records.append({
            "tipo":            "CLT",
            "competencia":     competencia,
            "numero_pessoal":  str(int(float(row[id_col]))) if pd.notna(row[id_col]) and str(row[id_col]).replace('.','').isdigit() else str(row[id_col]) if pd.notna(row[id_col]) else "",
            "nome":            str(row["Nome"]).strip(),
            "empresa":         COMPANY_NAMES.get(str(row["Empresa"]).strip(), str(row["Empresa"]).strip()),
            "custo":           float(row[custo_col]),
        })
    print(f"  {filename}: {len(df_valid)} registros, competencia={competencia}")

# ── PJ ────────────────────────────────────────────────────────────────────────
print("Lendo PJ...")
pj_csv = PJ_PATH + "vw_pagamento_pjs.csv"
df_pj = pd.read_csv(pj_csv, sep=";", encoding="latin1", dtype=str)
df_pj.columns = df_pj.columns.str.strip()

for _, row in df_pj.iterrows():
    try:
        comp = pd.to_datetime(row["competencia"].strip(), dayfirst=True)
        competencia = f"{comp.year}-{comp.month:02d}"
    except Exception:
        continue
    try:
        valor_str = str(row["valor_a_pagar"]).strip().replace(".", "").replace(",", ".")
        valor = -abs(float(valor_str))
    except Exception:
        continue
    sap = str(row.get("sap_code_company", "")).strip()
    name_company = str(row.get("name_company", "")).strip()
    records.append({
        "tipo":            "PJ",
        "competencia":     competencia,
        "numero_pessoal":  str(row["worker_id"]).strip(),
        "nome":            str(row["worker_name"]).strip(),
        "empresa":         COMPANY_NAMES.get(sap, name_company),
        "custo":           valor,
    })

print(f"PJ: {len([r for r in records if r['tipo'] == 'PJ'])} registros")

# ── Salvar ────────────────────────────────────────────────────────────────────
df_out = pd.DataFrame(records)
output_path = os.path.join(os.path.dirname(__file__), "metas_custo.csv")
df_out.to_csv(output_path, index=False)
print(f"\nSalvo: {output_path}")
print(f"Total: {len(df_out)} registros")
print(df_out.groupby(["competencia", "tipo"]).size().to_string())

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

# Mapeamento de nome da aba → empresa
SHEET_EMPRESA = {
    "HYPER":    "Hyper",
    "FCAMARA":  "FCamara",
    "NEXT":     "NextGen",
    "SGA":      "SGA",
    "DOJO":     "Dojo",
    "OMNIK":    "Omnik",
}
# NAÇÃO tem acento variável — match por prefixo
def sheet_to_empresa(sheet_name: str) -> str | None:
    key = sheet_name.upper().strip()
    if key in SHEET_EMPRESA:
        return SHEET_EMPRESA[key]
    if key.startswith("NA"):  # NAÇÃO / NA��O / NACAO
        return "Nação Digital"
    return None

def parse_id(val) -> str:
    """Retorna número pessoal como string se for numérico, senão vazio."""
    if pd.isna(val):
        return ""
    s = str(val).strip()
    try:
        return str(int(float(s)))
    except (ValueError, OverflowError):
        return ""  # textos como "não localizado no SAP"

records = []

# ── CLT ───────────────────────────────────────────────────────────────────────
# Para cada mês, pode haver múltiplas versões do arquivo (V2, V3...).
# Estratégia: agrupar por competência e usar o primeiro em ordem alfabética
# (ex: "11.25 - V2 - Email" vem antes de "11.25 - V2 - Envio email" e "11.25.xlsx").
_all_clt = sorted(glob(CLT_PATH + "Custo Gerencial Grupo *.xlsx"))
_clt_por_comp: dict = {}
for _fp in _all_clt:
    _fn = os.path.basename(_fp)
    _m = re.search(r'(\d{2})\.(\d{2})', _fn)
    if not _m:
        continue
    _comp = f"20{_m.group(2)}-{_m.group(1)}"
    if _comp not in _clt_por_comp:
        _clt_por_comp[_comp] = _fp   # primeiro alfabeticamente = preferido

print("Lendo CLT (abas por empresa)...")
for competencia, filepath in sorted(_clt_por_comp.items()):
    filename = os.path.basename(filepath)
    mes_num, ano_num = competencia[5:7], competencia[2:4]

    xl = pd.ExcelFile(filepath)
    total_file = 0

    for sheet_name in xl.sheet_names:
        empresa = sheet_to_empresa(sheet_name)
        if empresa is None:
            continue  # pula Consolidado e outras abas desconhecidas

        df = pd.read_excel(filepath, sheet_name=sheet_name)

        # Encontrar coluna de ID (número pessoal/SAP)
        id_col = next((c for c in df.columns
                       if "pessoal" in str(c).lower()
                       or ("id" in str(c).lower() and "sap" in str(c).lower())), None)

        # Coluna de custo total
        custo_col = next((c for c in df.columns
                          if "total" in str(c).lower() and "custo" in str(c).lower()), None)
        if not custo_col:
            custo_col = next((c for c in df.columns if "total" in str(c).lower()), None)

        nome_col = next((c for c in df.columns if str(c).strip().lower() == "nome"), None)

        if not custo_col or not nome_col:
            print(f"  Aviso: colunas não encontradas em {filename}/{sheet_name} — custo={custo_col}, nome={nome_col}")
            continue

        df = df.dropna(subset=[nome_col])
        df = df[pd.to_numeric(df[custo_col], errors="coerce").notna()]

        for _, row in df.iterrows():
            nome = str(row[nome_col]).strip()
            if not nome or nome.upper() in ("NOME", "TOTAL", ""):
                continue
            nr = parse_id(row[id_col]) if id_col else ""
            records.append({
                "tipo":           "CLT",
                "competencia":    competencia,
                "numero_pessoal": nr,
                "nome":           nome,
                "empresa":        empresa,
                "custo":          -abs(float(row[custo_col])),
                "categoria":      "CLT",
            })
            total_file += 1

    print(f"  {filename}: {total_file} registros, competencia={competencia}")

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
    if competencia < "2025-10":
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
        "categoria":       str(row.get("categoria", "")).strip(),
    })

print(f"PJ: {len([r for r in records if r['tipo'] == 'PJ'])} registros")

# ── Salvar ────────────────────────────────────────────────────────────────────
df_out = pd.DataFrame(records)
output_path = os.path.join(os.path.dirname(__file__), "metas_custo.csv")
df_out.to_csv(output_path, index=False)
print(f"\nSalvo: {output_path}")
print(f"Total: {len(df_out)} registros")
print(df_out.groupby(["competencia", "tipo"]).size().to_string())

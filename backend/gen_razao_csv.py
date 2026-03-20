"""
Gera razao_agg.csv a partir da planilha Razão P&L.
Execute com: py gen_razao_csv.py
"""
import pathlib
import pandas as pd
import os

BASE = list(pathlib.Path("C:/Users/amanda.paula").glob("FCamara*"))[0]
RAZAO_PATH = (
    BASE
    / "FCamara Files - CONTROLADORIA"
    / "30. FP&A NOVO"
    / "06. Cockpit - Desenvolvimentos"
    / "NewDashboard"
    / "Dados para apuração de metas"
)

COMPANY_NAMES = {
    "BR01": "FCamara", "BR02": "FCamara", "BR07": "Hyper", "BR09": "NextGen",
    "BR05": "SGA", "BR06": "Dojo", "BR04": "Nação Digital", "BR08": "Omnik",
    "BR03": "FCamara",
}

# Encontra o arquivo razao_pl mais recente na pasta
files = sorted(RAZAO_PATH.glob("*.xlsx"))
razao_file = next((f for f in reversed(files) if "razao_pl" in f.name.lower() or "razão" in f.name.lower() or "razao" in f.name.lower()), None)
if razao_file is None:
    razao_file = files[0]  # pega o primeiro se não encontrar pelo nome

print(f"Lendo: {razao_file.name}")

df = pd.read_excel(
    razao_file,
    sheet_name="Razão P&L",
    usecols=["CompanyCode", "agrupador_fpa", "FiscalYear", "FiscalPeriod", "AmountInCompanyCodeCurrency"],
)

print(f"Linhas brutas: {len(df)}")

df["empresa"] = df["CompanyCode"].map(COMPANY_NAMES).fillna(df["CompanyCode"])

agg = (
    df.groupby(["empresa", "agrupador_fpa", "FiscalYear", "FiscalPeriod"], as_index=False)
    ["AmountInCompanyCodeCurrency"]
    .sum()
)

output_path = os.path.join(os.path.dirname(__file__), "razao_agg.csv")
agg.to_csv(output_path, index=False)

print(f"Salvo: {output_path}")
print(f"Linhas agregadas: {len(agg)}")
print(agg.groupby(["FiscalYear", "FiscalPeriod"]).size().to_string())

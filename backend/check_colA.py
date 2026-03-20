import pathlib, pandas as pd

BASE = list(pathlib.Path("C:/Users/amanda.paula").glob("FCamara*"))[0]
RAC_PATH = (
    BASE / "FCamara Files - CONTROLADORIA" / "30. FP&A NOVO"
    / "06. Cockpit - Desenvolvimentos" / "NewDashboard"
    / "Dados para apuração de metas" / "RacFinancial_Consolidado.xlsx"
)

# Lê sem header pra ver as primeiras linhas brutas
raw = pd.read_excel(RAC_PATH, sheet_name="TimeAndExpenses", header=None, nrows=5)
print("=== Linhas brutas (header=None) ===")
print("Linha 0:", raw.iloc[0, :5].tolist())
print("Linha 1:", raw.iloc[1, :5].tolist())
print("Linha 2:", raw.iloc[2, :5].tolist())
print("Linha 3:", raw.iloc[3, :5].tolist())

print()
# Lê com header=1 (como usamos no código)
te = pd.read_excel(RAC_PATH, sheet_name="TimeAndExpenses", header=1, nrows=5)
te.columns = [c.strip() for c in te.columns]
print("=== Com header=1 ===")
print("Colunas:", te.columns[:6].tolist())
print("Coluna A (index 0):", te.iloc[:4, 0].tolist())
print("Coluna B (index 1):", te.iloc[:4, 1].tolist())
print()
print("Coluna 'Período' usada:", "Período" in te.columns or "Periodo" in te.columns)
print("Tipo da coluna Período:", te["Período"].dtype if "Período" in te.columns else "N/A")
print("Sample Período:", te["Período"].head(3).tolist() if "Período" in te.columns else "N/A")

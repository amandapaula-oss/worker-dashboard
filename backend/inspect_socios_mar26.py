"""Inspeciona aba Custo Socios do Mapa Mar26."""
import os, pandas as pd

DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(DIR, "2026 dados", "Mapa Pessoas - Mar26.xlsx")

xl = pd.ExcelFile(SRC)
print(f"Abas: {xl.sheet_names}")

aba = next((s for s in xl.sheet_names if "cio" in s.lower()), None)
print(f"Usando aba: {aba!r}")

df = pd.read_excel(SRC, sheet_name=aba, header=None)
print(f"Total rows: {len(df)}, cols: {len(df.columns)}")
print()
print("Primeiras 20 linhas (sem header):")
print(df.head(20).to_string())
print()
print("Linhas 5-15 com indices reais:")
for i in range(5, min(15, len(df))):
    print(f"row {i}: {list(df.iloc[i].fillna('').values)}")

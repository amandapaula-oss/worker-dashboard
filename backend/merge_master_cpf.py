"""Mescla o master CPF (Cadastro Pessoa - BRCPF e e-mail.xlsx) com o
pessoal_depara.csv, adicionando CPFs novos."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

MASTER = "2026 dados/Cadastro Pessoa - BRCPF e e-mail.xlsx"
DEPARA = "pessoal_depara.csv"

m = pd.read_excel(MASTER, sheet_name="monthly_hours_history")
m = m[["consultant_name", "email", "worker_id"]].dropna(subset=["worker_id"])
m = m.drop_duplicates(subset="worker_id")
m = m.rename(columns={"consultant_name": "nome", "worker_id": "cpf"})

d = pd.read_csv(DEPARA, dtype=str)
print(f"Depara antes: {len(d)} entries")

# CPFs ja no depara
existentes = set(d["cpf"].dropna())
novos = m[~m["cpf"].isin(existentes)].copy()
novos["id"] = ""
novos = novos[["id", "nome", "cpf"]]
print(f"CPFs novos do master a adicionar: {len(novos)}")

result = pd.concat([d, novos], ignore_index=True)
print(f"Depara depois: {len(result)} entries")

result.to_csv(DEPARA, index=False)
print(f"OK: {DEPARA} atualizado")

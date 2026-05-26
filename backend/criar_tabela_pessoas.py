"""Cria tabela `pessoas` no Supabase e popula com o master (Cadastro Pessoa)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import psycopg2
import httpx
from _supabase_creds import load_creds

HOST = "db.nzqxisoxodpxhvwksyam.supabase.co"
PORT = 5432
DBNAME = "postgres"
USER = "postgres"
PWD = "7tfOx8UmA81N2NfE"

MASTER = "2026 dados/Cadastro Pessoa - BRCPF e e-mail.xlsx"

DDL = """
CREATE TABLE IF NOT EXISTS pessoas (
    id BIGSERIAL PRIMARY KEY,
    cpf TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    email TEXT,
    contrato TEXT,
    razao_social TEXT,
    cnpj TEXT,
    fonte_dados TEXT,
    atualizado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE pessoas ADD COLUMN IF NOT EXISTS contrato TEXT;
ALTER TABLE pessoas ADD COLUMN IF NOT EXISTS razao_social TEXT;
ALTER TABLE pessoas ADD COLUMN IF NOT EXISTS cnpj TEXT;
CREATE INDEX IF NOT EXISTS idx_pessoas_nome ON pessoas (nome);
CREATE INDEX IF NOT EXISTS idx_pessoas_cpf ON pessoas (cpf);
"""


def main():
    # 1. DDL
    conn = psycopg2.connect(host=HOST, port=PORT, dbname=DBNAME, user=USER, password=PWD)
    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()
    cur.close()
    conn.close()
    print("OK: tabela pessoas criada")

    # 2. Carrega master
    m = pd.read_excel(MASTER, sheet_name="monthly_hours_history")
    cols = ["consultant_name", "email", "worker_id", "contrato", "razao_social", "cnpj"]
    m = m[cols].dropna(subset=["worker_id"])
    # Pra cada worker_id, pega o registro com mais info (razao_social preenchida ganha)
    m["_score"] = m["razao_social"].notna().astype(int) + m["cnpj"].notna().astype(int)
    m = m.sort_values("_score", ascending=False).drop_duplicates(subset="worker_id")
    m = m.drop(columns=["_score"])
    m = m.rename(columns={"consultant_name": "nome", "worker_id": "cpf"})
    m["fonte_dados"] = "Cadastro Pessoa - BRCPF e e-mail.xlsx"
    print(f"Master: {len(m)} pessoas a inserir")
    print(f"  com razao_social: {m['razao_social'].notna().sum()}")
    print(f"  contratos: {m['contrato'].value_counts().to_dict()}")

    # 3. Insert via REST com upsert por cpf
    url, key = load_creds()
    h = {
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    records = m[["cpf", "nome", "email", "contrato", "razao_social", "cnpj", "fonte_dados"]].to_dict(orient="records")
    # Remove NaN
    for r in records:
        for k in list(r.keys()):
            if pd.isna(r[k]):
                r[k] = None

    BATCH = 500
    done = 0
    with httpx.Client(timeout=60) as cli:
        for i in range(0, len(records), BATCH):
            chunk = records[i:i + BATCH]
            r = cli.post(f"{url}/rest/v1/pessoas?on_conflict=cpf", headers=h, json=chunk)
            if r.status_code >= 300:
                print(f"ERRO batch {i}: {r.status_code} {r.text[:300]}")
                return
            done += len(chunk)
            print(f"  {done}/{len(records)}")
    print(f"\nOK: {done} pessoas upserted")


if __name__ == "__main__":
    main()

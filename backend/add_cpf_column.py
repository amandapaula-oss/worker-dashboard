"""Adiciona coluna cpf em nova_base_calculada via psycopg2 (DDL)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import psycopg2

# Connection string Supabase (DB password fornecido pelo usuario)
HOST = "db.nzqxisoxodpxhvwksyam.supabase.co"
PORT = 5432
DBNAME = "postgres"
USER = "postgres"
PWD = "7tfOx8UmA81N2NfE"

try:
    conn = psycopg2.connect(host=HOST, port=PORT, dbname=DBNAME, user=USER, password=PWD)
    cur = conn.cursor()
    cur.execute("ALTER TABLE nova_base_calculada ADD COLUMN IF NOT EXISTS cpf text;")
    conn.commit()
    cur.close()
    conn.close()
    print("OK: coluna cpf adicionada (ou ja existia)")
except Exception as e:
    print(f"ERRO: {e}")

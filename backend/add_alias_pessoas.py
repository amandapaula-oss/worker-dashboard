"""Adiciona coluna alias em pessoas via psycopg2 (DDL)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import psycopg2

HOST = "db.nzqxisoxodpxhvwksyam.supabase.co"
PORT = 5432
DBNAME = "postgres"
USER = "postgres"
PWD = "7tfOx8UmA81N2NfE"

conn = psycopg2.connect(host=HOST, port=PORT, dbname=DBNAME, user=USER, password=PWD)
cur = conn.cursor()
cur.execute("ALTER TABLE pessoas ADD COLUMN IF NOT EXISTS alias text;")
conn.commit()
cur.close()
conn.close()
print("OK: coluna alias adicionada (ou ja existia)")

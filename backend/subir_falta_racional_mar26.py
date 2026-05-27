"""Sobe receitas 'Falta Racional' e 'Investidas fora do SAP' manualmente."""
import sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timezone
import httpx
from _supabase_creds import load_creds

URL, KEY = load_creds()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
     "Content-Type": "application/json", "Prefer": "return=minimal"}

UPLOAD_ID = str(uuid.uuid4())
AT = datetime.now(timezone.utc).isoformat()
BY = "amanda.paula@fcamara.com"

# Falta Racional: empresa=BR02 FCamara, vertical=BU Retail, DC002
FALTA = [
    ("STRADA PAY INSTITUICAO DE PAGAMENTO LTDA", "2026-01", 50590),
    ("STRADA PAY INSTITUICAO DE PAGAMENTO LTDA", "2026-02", 54873),
    ("STRADA PAY INSTITUICAO DE PAGAMENTO LTDA", "2026-03", 16123),
    ("GRUPO CASAS BAHIA S.A.", "2026-01", 73069),
    ("GRUPO CASAS BAHIA S.A.", "2026-02", 73069),
    ("LOJAS RENNER S.A.", "2026-01", 97883),
    ("LOJAS RENNER S.A.", "2026-02", 67143),
    ("LOJAS RENNER S.A.", "2026-03", 73349),
    ("GIMBA", "2026-01", 64456),
    ("GIMBA", "2026-02", 64456),
    ("GIMBA", "2026-03", 64456),
]

# Distrito (fora do SAP)
DISTRITO = [
    ("GRUPO CASAS BAHIA S.A.", "2026-03", 121376),
]

records = []
for cli, per, val in FALTA:
    records.append({
        "upload_id": UPLOAD_ID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "Falta Racional - Mar26 (manual)",
        "periodo": per,
        "empresa": "BR02 FCamara",
        "nome_cliente": cli,
        "vertical": "BU Retail",
        "no_hierarquia": "DC002 Dedicated Teams",
        "receita": float(val),
        "custo_rateado": 0,
        "margem": float(val),
        "valor_liquido": float(val),
        "horas": 0,
    })
for cli, per, val in DISTRITO:
    records.append({
        "upload_id": UPLOAD_ID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "Investidas fora do SAP - Mar26 (manual)",
        "periodo": per,
        "empresa": "Distrito",
        "nome_cliente": cli,
        "vertical": "DISTRITO",
        "no_hierarquia": "DISTRITO",
        "receita": float(val),
        "custo_rateado": 0,
        "margem": float(val),
        "valor_liquido": float(val),
        "horas": 0,
    })

print(f"Records: {len(records)}")
print(f"Total receita: R${sum(r['receita'] for r in records):,.0f}")

if "--apply" in sys.argv:
    with httpx.Client(timeout=60) as c:
        # delete existentes (caso re-rode)
        c.delete(f"{URL}/rest/v1/nova_base?fonte_dados=eq.Falta Racional - Mar26 (manual)", headers=H)
        c.delete(f"{URL}/rest/v1/nova_base?fonte_dados=eq.Investidas fora do SAP - Mar26 (manual)", headers=H)
        r = c.post(f"{URL}/rest/v1/nova_base", headers=H, json=records)
        print(f"INSERT status: {r.status_code}")
        if r.status_code >= 300:
            print(f"ERRO: {r.text[:400]}")
    print("OK")
else:
    print("[DRY-RUN] use --apply pra efetivar")
    for r in records:
        print(f"  {r['periodo']} {r['nome_cliente']:42s} {r['empresa']:14s} {r['vertical']:11s} R${r['receita']:>10,.0f}")

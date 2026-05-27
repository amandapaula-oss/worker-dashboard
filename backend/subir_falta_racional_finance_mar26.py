"""Sobe receitas Falta Racional + Investidas para BU Finance."""
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

# Falta Racional Finance (Ouribank)
FALTA = [
    ("BANCO OURINVEST S/A", "BR02 FCamara", "DC002 Dedicated Teams", "BU Finance", "2026-01", 69484),
    ("BANCO OURINVEST S/A", "BR02 FCamara", "DC002 Dedicated Teams", "BU Finance", "2026-02", 69484),
    ("BANCO OURINVEST S/A", "BR02 FCamara", "DC002 Dedicated Teams", "BU Finance", "2026-03", 69484),
]

# Investidas fora do SAP (Distrito) - BU Finance
INVEST = [
    ("BMG", "Distrito", "DISTRITO", "BU Finance", "2026-01", 113021),
    ("BMG", "Distrito", "DISTRITO", "BU Finance", "2026-02", 113021),
    ("BMG", "Distrito", "DISTRITO", "BU Finance", "2026-03", 113021),
]

records = []
for cli, emp, dc, vert, per, val in FALTA:
    records.append({
        "upload_id": UPLOAD_ID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "Falta Racional Finance - Mar26 (manual)",
        "periodo": per, "empresa": emp, "nome_cliente": cli,
        "vertical": vert, "no_hierarquia": dc,
        "receita": float(val), "custo_rateado": 0, "margem": float(val),
        "valor_liquido": float(val), "horas": 0,
    })
for cli, emp, dc, vert, per, val in INVEST:
    records.append({
        "upload_id": UPLOAD_ID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "Investidas fora do SAP Finance - Mar26 (manual)",
        "periodo": per, "empresa": emp, "nome_cliente": cli,
        "vertical": vert, "no_hierarquia": dc,
        "receita": float(val), "custo_rateado": 0, "margem": float(val),
        "valor_liquido": float(val), "horas": 0,
    })

print(f"Records: {len(records)}")
print(f"Total receita: R${sum(r['receita'] for r in records):,.0f}")

if "--apply" in sys.argv:
    with httpx.Client(timeout=60) as c:
        c.delete(f"{URL}/rest/v1/nova_base?fonte_dados=eq.Falta Racional Finance - Mar26 (manual)", headers=H)
        c.delete(f"{URL}/rest/v1/nova_base?fonte_dados=eq.Investidas fora do SAP Finance - Mar26 (manual)", headers=H)
        r = c.post(f"{URL}/rest/v1/nova_base", headers=H, json=records)
        print(f"INSERT: {r.status_code}")
        if r.status_code >= 300:
            print(f"ERRO: {r.text[:300]}")
    print("OK")
else:
    print("[DRY-RUN]")
    for r in records:
        print(f"  {r['periodo']} {r['nome_cliente']:22s} {r['empresa']:14s} {r['no_hierarquia']:25s} R${r['receita']:>10,.0f}")

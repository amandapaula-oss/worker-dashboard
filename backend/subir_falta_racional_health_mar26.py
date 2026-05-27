"""Sobe receitas Falta Racional + Investidas para BU Health."""
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

# Falta Racional (BU Health). Format: (cliente, empresa, no_hierarquia, periodo, valor)
FALTA = [
    ("UNIMED NACIONAL",       "BR07 Hyper",   "DC002 Dedicated Teams",      "2026-01", 138845),
    ("UNIMED NACIONAL",       "BR07 Hyper",   "DC002 Dedicated Teams",      "2026-02", 138845),
    ("ODONTOPREV S.A.",       "BR02 FCamara", "DC002 Dedicated Teams",      "2026-01", 86000),
    ("ODONTOPREV S.A.",       "BR02 FCamara", "DC002 Dedicated Teams",      "2026-02", 86000),
    ("ODONTOPREV S.A.",       "BR02 FCamara", "DC002 Dedicated Teams",      "2026-03", 86000),
    ("GRUPO ELFA",            "BR02 FCamara", "DC040 FC Consult. B. Sales", "2026-01", 3000),
    ("GRUPO ELFA",            "BR02 FCamara", "DC040 FC Consult. B. Sales", "2026-02", 3000),
    ("GRUPO ELFA",            "BR02 FCamara", "DC040 FC Consult. B. Sales", "2026-03", 3000),
    ("GRUPO ELFA",            "BR02 FCamara", "DC007 Imagine",              "2026-02", 141500),
]

# Investidas fora do SAP (BU Health)
INVEST = [
    ("ADCOS", "Avanti", "Avanti", "2026-01", 102912),
    ("ADCOS", "Avanti", "Avanti", "2026-02", 102912),
    ("ADCOS", "Avanti", "Avanti", "2026-03", 102912),
]

records = []
for cli, emp, dc, per, val in FALTA:
    records.append({
        "upload_id": UPLOAD_ID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "Falta Racional Health - Mar26 (manual)",
        "periodo": per, "empresa": emp, "nome_cliente": cli,
        "vertical": "BU Health", "no_hierarquia": dc,
        "receita": float(val), "custo_rateado": 0, "margem": float(val),
        "valor_liquido": float(val), "horas": 0,
    })
for cli, emp, dc, per, val in INVEST:
    records.append({
        "upload_id": UPLOAD_ID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "Investidas fora do SAP Health - Mar26 (manual)",
        "periodo": per, "empresa": emp, "nome_cliente": cli,
        "vertical": "BU Health", "no_hierarquia": dc,
        "receita": float(val), "custo_rateado": 0, "margem": float(val),
        "valor_liquido": float(val), "horas": 0,
    })

print(f"Records: {len(records)}")
print(f"Total receita: R${sum(r['receita'] for r in records):,.0f}")

if "--apply" in sys.argv:
    with httpx.Client(timeout=60) as c:
        c.delete(f"{URL}/rest/v1/nova_base?fonte_dados=eq.Falta Racional Health - Mar26 (manual)", headers=H)
        c.delete(f"{URL}/rest/v1/nova_base?fonte_dados=eq.Investidas fora do SAP Health - Mar26 (manual)", headers=H)
        r = c.post(f"{URL}/rest/v1/nova_base", headers=H, json=records)
        print(f"INSERT status: {r.status_code}")
        if r.status_code >= 300:
            print(f"ERRO: {r.text[:300]}")
    print("OK")
else:
    print("[DRY-RUN] use --apply pra efetivar")
    for r in records:
        print(f"  {r['periodo']} {r['nome_cliente']:18s} {r['empresa']:14s} {r['no_hierarquia']:30s} R${r['receita']:>10,.0f}")

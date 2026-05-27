"""Sobe Falta Racional Multisector."""
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

# (cliente, empresa, no_hierarquia, periodo, valor)
DADOS = [
    # ASGROUP - DC002
    ("ASGROUP", "BR02 FCamara", "DC002 Dedicated Teams", "2026-01", 43922),
    ("ASGROUP", "BR02 FCamara", "DC002 Dedicated Teams", "2026-02", 43922),
    ("ASGROUP", "BR02 FCamara", "DC002 Dedicated Teams", "2026-03", 43922),
    # FUTEBOLCARD - DC002
    ("FUTEBOLCARD SISTEMAS LTDA", "BR02 FCamara", "DC002 Dedicated Teams", "2026-01", 442392),
    ("FUTEBOLCARD SISTEMAS LTDA", "BR02 FCamara", "DC002 Dedicated Teams", "2026-02", 292872),
    ("FUTEBOLCARD SISTEMAS LTDA", "BR02 FCamara", "DC002 Dedicated Teams", "2026-03", 421833),
    # DURATEX - DC040 (Imagine no label do user, mas codigo canonico DC040 = FC Consult. B. Sales)
    ("DURATEX", "BR02 FCamara", "DC040 FC Consult. B. Sales", "2026-01", 2658),
    ("DURATEX", "BR02 FCamara", "DC040 FC Consult. B. Sales", "2026-02", 2658),
    ("DURATEX", "BR02 FCamara", "DC040 FC Consult. B. Sales", "2026-03", 2658),
    # KLABIN - DC002 (so Fev e Mar)
    ("KLABIN", "BR02 FCamara", "DC002 Dedicated Teams", "2026-02", 17654),
    ("KLABIN", "BR02 FCamara", "DC002 Dedicated Teams", "2026-03", 17654),
]

records = []
for cli, emp, dc, per, val in DADOS:
    records.append({
        "upload_id": UPLOAD_ID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "Falta Racional Multisector - Mar26 (manual)",
        "periodo": per, "empresa": emp, "nome_cliente": cli,
        "vertical": "BU Multisector", "no_hierarquia": dc,
        "receita": float(val), "custo_rateado": 0, "margem": float(val),
        "valor_liquido": float(val), "horas": 0,
    })

print(f"Records: {len(records)}")
print(f"Total receita: R${sum(r['receita'] for r in records):,.0f}")

if "--apply" in sys.argv:
    with httpx.Client(timeout=60) as c:
        c.delete(f"{URL}/rest/v1/nova_base?fonte_dados=eq.Falta Racional Multisector - Mar26 (manual)", headers=H)
        r = c.post(f"{URL}/rest/v1/nova_base", headers=H, json=records)
        print(f"INSERT: {r.status_code}")
        if r.status_code >= 300: print(r.text[:300])
    print("OK")
else:
    print("[DRY-RUN]")
    for r in records:
        print(f"  {r['periodo']} {r['nome_cliente']:28s} {r['no_hierarquia']:30s} R${r['receita']:>10,.0f}")

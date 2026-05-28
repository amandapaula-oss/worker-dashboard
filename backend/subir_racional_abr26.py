"""Substitui o Racional Março.xlsx (com bug de dups) pelas abas T&E Mar26
e <> T&E Mar26 do FCamara - P&L Gerencial - abr26.xlsx."""
import os, uuid, math, re
from datetime import datetime, timezone
import pandas as pd
import httpx
from _supabase_creds import load_creds

DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(DIR, "2026 dados", "FCamara - P&L Gerencial - abr26.xlsx")

url, key = load_creds()
H = {"apikey": key, "Authorization": f"Bearer {key}"}
H_DEL = {**H, "Prefer": "return=minimal"}
H_INS = {**H, "Content-Type": "application/json", "Prefer": "return=minimal"}

UID = str(uuid.uuid4())
AT = datetime.now(timezone.utc).isoformat()
BY = "amanda.paula@fcamara.com"

COMPANY_NAMES = {
    "BR02": "BR02 FCamara", "BR03": "BR03 Omnik", "BR04": "BR04 Nação Digital",
    "BR05": "BR05 SGA", "BR07": "BR07 Hyper", "BR0C": "BR07 Hyper",
    "BR08": "BR08 Dojo", "BR09": "BR09 NextGen",
}


def clean(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none"): return None
    return s


def num(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    try: return float(v)
    except: return None


def cpf_brcpf(v):
    if v is None: return None
    s = re.sub(r"\D", "", str(v))
    return f"BRCPF{s}" if len(s) >= 11 else None


# ========== T&E Mar26 ==========
print("Carregando T&E Mar26...")
df = pd.read_excel(SRC, sheet_name="T&E Mar26")
df.columns = [str(c).strip() for c in df.columns]
df["_per"] = df["Competência"].astype(str).str[:7]
df = df[df["_per"].str.startswith("2026") & df["PROFISSIONAL"].notna()]
print(f"  {len(df)} rows, por periodo: {dict(df['_per'].value_counts())}")

rows_te = []
for _, r in df.iterrows():
    pep = clean(r.get("PEP"))
    pep_base = pep.split(".")[0] if pep else None
    empresa_sap = clean(r.get("EMPRESA"))
    empresa = COMPANY_NAMES.get(empresa_sap, empresa_sap) if empresa_sap else None
    # Receita = Valor Liquido (realizada/liquida). Fallback pra VALOR TOTAL
    # quando liquido nao existir.
    liquido = num(r.get("Valor Liquido :)"))
    bruto = num(r.get("VALOR TOTAL"))
    receita = liquido if liquido is not None else (bruto or 0)
    horas_v = num(r.get("HRS APROVADAS")) or 0
    rows_te.append({
        "upload_id": UID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "T&E Mar26 (P&L Abr26)",
        "periodo": r["_per"], "empresa": empresa,
        "nome_pessoa": clean(r.get("PROFISSIONAL")),
        "cpf": cpf_brcpf(r.get("BRCPF")),
        "nome_cliente": clean(r.get("NOME CLIENTE")),
        "pep": pep, "pep_base": pep_base,
        "vertical": clean(r.get("Vertical")),
        "no_hierarquia": clean(r.get("Profit Center")),
        "tipos": clean(r.get("OBSERVAÇÃO")),
        "receita": receita,
        "horas": horas_v,
        "custo_rateado": 0,
        "margem": receita,
        "valor_liquido": receita,
    })

# ========== <> T&E Mar26 ==========
print("Carregando <> T&E Mar26...")
df2 = pd.read_excel(SRC, sheet_name="<> T&E Mar26")
df2.columns = [str(c).strip() for c in df2.columns]
df2["_per"] = df2["Competência"].astype(str).str[:7]
df2 = df2[df2["_per"].str.startswith("2026") & df2["NOME CLIENTE"].notna()]
print(f"  {len(df2)} rows, por periodo: {dict(df2['_per'].value_counts())}")

rows_out = []
for _, r in df2.iterrows():
    pep = clean(r.get("PEP"))
    pep_base = pep.split(".")[0] if pep else None
    empresa_sap = clean(r.get("EMPRESA"))
    empresa = COMPANY_NAMES.get(empresa_sap, empresa_sap) if empresa_sap else None
    # Receita = SOMENTE Formula Liquido. Sem fallback pra RECEITA PLANEJADA
    # (sao colunas mutuamente exclusivas; somar as duas inflaria a receita).
    receita = num(r.get("Formula Líquido")) or 0
    rows_out.append({
        "upload_id": UID, "uploaded_at": AT, "uploaded_by": BY,
        "fonte": "racionais", "fonte_dados": "<> T&E Mar26 (P&L Abr26)",
        "periodo": r["_per"], "empresa": empresa,
        "nome_cliente": clean(r.get("NOME CLIENTE")),
        "pep": pep, "pep_base": pep_base,
        "vertical": clean(r.get("Vertical")),
        "no_hierarquia": clean(r.get("Profit Center")),
        "tipos": clean(r.get("Projeto")) or clean(r.get("OBSERVAÇÃO")),
        "receita": receita,
        "horas": 0,
        "custo_rateado": 0,
        "margem": receita,
        "valor_liquido": receita,
    })

# Normaliza schema
all_keys = set()
for r in rows_te + rows_out: all_keys.update(r.keys())
for r in rows_te + rows_out:
    for k in all_keys: r.setdefault(k, None)
    r.pop("cpf", None)  # cpf nao existe na tabela raw

total = rows_te + rows_out
print(f"\nTotal a inserir: {len(total)} ({len(rows_te)} T&E + {len(rows_out)} <>T&E)")

if "--apply" not in __import__("sys").argv:
    print("[DRY-RUN] use --apply")
    raise SystemExit(0)

# DELETE old
print()
print("DELETE Racional Março.xlsx + Outras Receitas Mar26.xlsx + qualquer outro T&E Mar26 ...")
for fd in ["Racional Março.xlsx", "Outras Receitas Mar26.xlsx", "T&E Mar26 (P&L Abr26)", "<> T&E Mar26 (P&L Abr26)"]:
    import urllib.parse
    fdq = urllib.parse.quote(fd, safe="")
    r = httpx.delete(f"{url}/rest/v1/nova_base?fonte_dados=eq.{fdq}", headers=H_DEL, timeout=60)
    print(f"  {fd}: {r.status_code}")

# INSERT
print()
print("INSERT em batches de 200...")
BATCH = 200
done = 0
for i in range(0, len(total), BATCH):
    batch = total[i:i+BATCH]
    r = httpx.post(f"{url}/rest/v1/nova_base", headers=H_INS, json=batch, timeout=120)
    if r.status_code not in (200, 201, 204):
        print(f"  ERRO batch {i}: {r.status_code} | {r.text[:500]}"); break
    done += len(batch)
    print(f"  {done}/{len(total)}")

print(f"\nOK: {done} linhas inseridas. upload_id={UID}")

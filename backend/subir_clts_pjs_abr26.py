"""Atualiza CLTs e PJs (Jan-Abr 2026) na nova_base a partir do
FCamara - P&L Gerencial - abr26.xlsx (sheets CLTs e PJs).

Substitui completamente as linhas existentes nesses periodos.
"""
import os, uuid, math, re
from datetime import datetime, timezone
import pandas as pd
import httpx
from _supabase_creds import load_creds

DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(DIR, "2026 dados", "FCamara - P&L Gerencial - abr26.xlsx")
FD = "FCamara - P&L Gerencial - abr26.xlsx"
PERIODOS = ("2026-01", "2026-02", "2026-03", "2026-04")

url, key = load_creds()
H = {"apikey": key, "Authorization": f"Bearer {key}"}
H_DEL = {**H, "Prefer": "return=minimal"}
H_INS = {**H, "Content-Type": "application/json", "Prefer": "return=minimal"}

UPLOAD_ID = str(uuid.uuid4())
UPLOADED_AT = datetime.now(timezone.utc).isoformat()
UPLOADED_BY = "amanda.paula@fcamara.com"

COMPANY_NAMES = {
    "BR02": "BR02 FCamara", "BR03": "BR03 Omnik", "BR04": "BR04 Nação Digital",
    "BR05": "BR05 SGA", "BR07": "BR07 Hyper", "BR0C": "BR07 Hyper",
    "BR08": "BR08 Dojo", "BR09": "BR09 NextGen",
}


def clean(v, sentinel_zero=False):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none"): return None
    if sentinel_zero and s == "0": return None
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


# ========== CLTs ==========
print("=" * 60)
print("Carregando CLTs...")
df_clt = pd.read_excel(SRC, sheet_name="CLTs")
df_clt.columns = [str(c).strip() for c in df_clt.columns]
ma_col = next((c for c in df_clt.columns if c.startswith("Macro") and "rea" in c), None)
comp_col = next((c for c in df_clt.columns if c.startswith("Compet")), None)
print(f"  ma={ma_col!r}, comp={comp_col!r}")

df_clt["_periodo"] = df_clt[comp_col].astype(str).str[:7]
df_clt = df_clt[df_clt["_periodo"].isin(PERIODOS) & df_clt["Nome"].notna()]
print(f"  CLTs validos: {len(df_clt)}")
print(f"  por periodo: {dict(df_clt['_periodo'].value_counts())}")

rows_clt = []
for _, r in df_clt.iterrows():
    empresa_sap = clean(r.get("Empresa"))
    empresa = COMPANY_NAMES.get(empresa_sap, empresa_sap) if empresa_sap else None
    rec = num(r.get("Totalizador")) or 0
    rec_sap = num(r.get("Custo Gerencial SAP")) or 0
    horas_v = num(r.get("Horas totais")) or 0
    rows_clt.append({
        "upload_id": UPLOAD_ID, "uploaded_at": UPLOADED_AT, "uploaded_by": UPLOADED_BY,
        "fonte": "CLTs", "fonte_dados": FD,
        "periodo": r["_periodo"],
        "empresa": empresa,
        "nome_pessoa": clean(r.get("Nome")),
        "cpf": cpf_brcpf(r.get("CPF")),
        "nome_cliente": clean(r.get("Cliente"), sentinel_zero=True),
        "tipos": clean(r.get("Projeto")),
        "vertical": clean(r.get("BU"), sentinel_zero=True),
        "area": clean(r.get("Centro de Custo"), sentinel_zero=True),
        "macro_area": clean(r.get(ma_col), sentinel_zero=True),
        "no_hierarquia": clean(r.get("Profit Center"), sentinel_zero=True),
        "billable_category": clean(r.get("Billability")),
        "tipo_contrato": "CLT",
        "custo_gerencial_sap": rec_sap,
        "horas": horas_v,
        "valor_liquido": rec,
        "custo_rateado": -rec if rec else 0,
        "margem": -rec if rec else 0,
    })

# ========== PJs ==========
print()
print("Carregando PJs...")
df_pj = pd.read_excel(SRC, sheet_name="PJs")
df_pj.columns = [str(c).strip() for c in df_pj.columns]
ma_col_pj = next((c for c in df_pj.columns if c.startswith("Macro") and "rea" in c), None)
comp_col_pj = next((c for c in df_pj.columns if c.startswith("Compet") and not c.endswith("encia")), None) or "Competência"
print(f"  ma={ma_col_pj!r}, comp={comp_col_pj!r}")

df_pj["_periodo"] = df_pj[comp_col_pj].astype(str).str[:7]
df_pj = df_pj[df_pj["_periodo"].isin(PERIODOS) & df_pj["worker_name"].notna()]
print(f"  PJs validos: {len(df_pj)}")
print(f"  por periodo: {dict(df_pj['_periodo'].value_counts())}")

rows_pj = []
for _, r in df_pj.iterrows():
    empresa_sap = clean(r.get("Empresa"))
    empresa = COMPANY_NAMES.get(empresa_sap, empresa_sap) if empresa_sap else None
    valor = num(r.get("valor_a_pagar")) or 0
    rows_pj.append({
        "upload_id": UPLOAD_ID, "uploaded_at": UPLOADED_AT, "uploaded_by": UPLOADED_BY,
        "fonte": "PJs", "fonte_dados": FD,
        "periodo": r["_periodo"],
        "empresa": empresa,
        "nome_pessoa": clean(r.get("worker_name")),
        "cpf": cpf_brcpf(r.get("worker_id")),
        "nome_cliente": clean(r.get("Cliente"), sentinel_zero=True),
        "tipos": clean(r.get("Projeto")),
        "vertical": clean(r.get("BU"), sentinel_zero=True),
        "area": clean(r.get("Centro de Custo"), sentinel_zero=True),
        "macro_area": clean(r.get(ma_col_pj), sentinel_zero=True),
        "no_hierarquia": clean(r.get("Profit Center"), sentinel_zero=True),
        "billable_category": clean(r.get("Billability")) or clean(r.get("billable_category")),
        "tipo_contrato": clean(r.get("contract_employment")) or "PJ",
        "valor_liquido": valor,
        "custo_rateado": -valor,
        "margem": -valor,
    })

# Normaliza schema (campos comuns)
all_keys = set()
for r in rows_clt + rows_pj: all_keys.update(r.keys())
for r in rows_clt + rows_pj:
    for k in all_keys: r.setdefault(k, None)

# Verifica se cpf eh column real ou nao precisa enviar
# (cpf nao existe em nova_base raw; vamos remover dos records antes do POST)
for r in rows_clt + rows_pj:
    r.pop("cpf", None)

print()
print(f"Total a inserir: {len(rows_clt)} CLT + {len(rows_pj)} PJ = {len(rows_clt) + len(rows_pj)}")

if "--dry" in __import__("sys").argv:
    print("[DRY-RUN] sem --apply, nao faz delete/insert")
    raise SystemExit(0)

if "--apply" not in __import__("sys").argv:
    print("[DRY-RUN] use --apply pra efetivar")
    raise SystemExit(0)

# DELETE
print()
print(f"DELETE existentes em {PERIODOS}...")
for fonte in ("CLTs", "PJs"):
    del_url = f"{url}/rest/v1/nova_base?fonte=eq.{fonte}&periodo=in.({','.join(PERIODOS)})"
    dr = httpx.delete(del_url, headers=H_DEL, timeout=60)
    print(f"  {fonte}: {dr.status_code}")
    if dr.status_code not in (200, 204):
        print(f"  ERRO: {dr.text[:300]}"); raise SystemExit(1)

# INSERT
print()
print("INSERT em batches de 200...")
ins_url = f"{url}/rest/v1/nova_base"
all_rows = rows_clt + rows_pj
BATCH = 200
inserted = 0
for i in range(0, len(all_rows), BATCH):
    batch = all_rows[i:i+BATCH]
    r = httpx.post(ins_url, headers=H_INS, json=batch, timeout=120)
    if r.status_code not in (200, 201, 204):
        print(f"  ERRO batch {i}: {r.status_code} | {r.text[:500]}"); break
    inserted += len(batch)
    print(f"  {inserted}/{len(all_rows)}")

print()
print(f"OK: {inserted} linhas inseridas. upload_id={UPLOAD_ID}")
print()
print("PROXIMO PASSO: rode 'python re_aplicar_ajustes.py --apply' pra restaurar os ajustes manuais.")

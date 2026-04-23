"""Seed Supabase nova_base table from base_2026.csv (one-time migration)."""
import os, sys, uuid, math
import pandas as pd
import numpy as np
import httpx

DIR = os.path.dirname(__file__)
sys.path.insert(0, DIR)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
REST_URL = f"{SUPABASE_URL}/rest/v1/nova_base"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

COMPANY_NAMES = {
    "BR02": "BR02 FCamara", "BRO2": "BR02 FCamara", "FCamara": "BR02 FCamara",
    "BR03": "BR03 Omnik", "Omnik": "BR03 Omnik",
    "BR04": "BR04 Nação Digital", "Nação Digital": "BR04 Nação Digital",
    "BR05": "BR05 SGA", "SGA": "BR05 SGA",
    "BR07": "BR07 Hyper", "BR0C": "BR0C Hyper", "Hyper": "BR07 Hyper",
    "BR08": "BR08 Dojo", "Dojo": "BR08 Dojo",
    "BR09": "BR09 NextGen", "NextGen": "BR09 NextGen",
}

NEEDED_COLS = [
    "fonte", "fonte_dados", "periodo", "empresa", "pep", "pep_base",
    "nome_pessoa", "nome_cliente", "tipos", "categoria_bu", "no_hierarquia",
    "vertical", "stream", "agrupador", "area", "macro_area",
    "classificacao", "tipo_contrato", "billable_category",
    "receita", "custo_rateado", "horas", "margem", "valor_liquido",
    "valor", "taxa_hora", "hour_price", "gross_revenue",
    "custo_gerencial_sap", "custo_h_hora_extra", "custo_h_sobreaviso",
]

NUM_COLS = [
    "receita", "custo_rateado", "horas", "margem", "valor_liquido",
    "valor", "taxa_hora", "hour_price", "gross_revenue",
    "custo_gerencial_sap", "custo_h_hora_extra", "custo_h_sobreaviso",
]


def load_and_transform():
    csv_path = os.path.join(DIR, "base_2026.csv")
    print(f"[seed] Reading {csv_path}...")
    use_cols = [c for c in NEEDED_COLS]
    df = pd.read_csv(csv_path, usecols=lambda c: c in use_cols, low_memory=False)
    print(f"[seed] {len(df)} rows, {len(df.columns)} cols")

    # Add missing cols
    for c in NEEDED_COLS:
        if c not in df.columns:
            df[c] = None

    # Numeric coercion
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Cost derivation (same as _get_nova_base in main.py)
    mask_pj = pd.Series(False, index=df.index)
    if "custo_gerencial_sap" in df.columns:
        custo_ger = df["custo_gerencial_sap"].fillna(0)
        custo_ext = df.get("custo_h_hora_extra", pd.Series(0, index=df.index)).fillna(0)
        custo_sob = df.get("custo_h_sobreaviso", pd.Series(0, index=df.index)).fillna(0)
        mask_clt = (df["custo_rateado"] == 0) & (custo_ger != 0)
        df["custo_rateado"] = np.where(mask_clt, -(custo_ger + custo_ext + custo_sob), df["custo_rateado"])
    else:
        mask_clt = pd.Series(False, index=df.index)

    if "valor_liquido" in df.columns and "fonte" in df.columns:
        vl = df["valor_liquido"].fillna(0)
        mask_pj = (df["custo_rateado"] == 0) & (df["fonte"].astype(str) == "PJs") & (vl > 0)
        df["custo_rateado"] = np.where(mask_pj, -vl, df["custo_rateado"])

    if "valor_liquido" in df.columns:
        rec = df["receita"].fillna(0)
        cr = df["custo_rateado"].fillna(0)
        df["valor_liquido"] = np.where(mask_clt | mask_pj, rec + cr, df["valor_liquido"])
        vl_zero = df["valor_liquido"] == 0
        has_val = (rec != 0) | (cr != 0)
        df["valor_liquido"] = np.where(vl_zero & has_val, rec + cr, df["valor_liquido"])

    # Margem
    df["margem"] = df["receita"] + df["custo_rateado"]

    # Empresa mapping
    if "empresa" in df.columns:
        df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])

    return df[NEEDED_COLS]


def clean_for_json(df):
    """Replace NaN/inf with None for JSON serialization."""
    df = df.where(pd.notnull(df), None)
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = df[c].apply(lambda v: None if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else round(float(v), 2))
    for c in df.columns:
        if c not in NUM_COLS:
            df[c] = df[c].apply(lambda v: str(v).strip() if v is not None else None)
    return df


def main():
    df = load_and_transform()
    df = clean_for_json(df)

    upload_id = str(uuid.uuid4())
    print(f"[seed] Upload ID: {upload_id}")
    print(f"[seed] Inserting {len(df)} rows in batches of 500...")

    client = httpx.Client(timeout=30)
    batch_size = 500
    total = len(df)
    inserted = 0

    for i in range(0, total, batch_size):
        batch = df.iloc[i:i+batch_size].to_dict(orient="records")
        for row in batch:
            row["upload_id"] = upload_id
            row["uploaded_by"] = "seed"
        r = client.post(REST_URL, headers=HEADERS, json=batch)
        if r.status_code not in (200, 201):
            print(f"[seed] ERROR batch {i//batch_size}: {r.status_code} {r.text[:300]}")
            return
        inserted += len(batch)
        print(f"  {inserted}/{total} ({inserted*100//total}%)")

    print(f"[seed] Done! {inserted} rows inserted.")

    # Verify
    r = client.get(REST_URL + "?select=id", headers={**HEADERS, "Prefer": "count=exact"})
    count = r.headers.get("content-range", "").split("/")[-1]
    print(f"[seed] Verify: {count} rows in Supabase")


if __name__ == "__main__":
    main()

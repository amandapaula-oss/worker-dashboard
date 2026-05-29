"""Sobe apontamentos da Base Orange (Jan-Abr 2026) na nova_base com fonte='base Orange'.

Regras (definidas pela usuaria):
- Para periodos 1-2 (Jan/Fev) usa Base Orange - Jan a Abr.xlsx
- Para periodos 3-4 (Mar/Abr) usa Base Orange - Mar e Abr.xlsx
- horas = total_horas_orange (coluna oficial; inclui aprovadas + outros estados)
- Filtro por (pessoa, periodo, pep): pula Orange row se ja tem racional nesse PEP

Rodar com --apply pra efetivar (sem flag = dry-run).
"""
from __future__ import annotations
import sys, io, uuid, math, unicodedata, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timezone
import pandas as pd
import httpx
from _supabase_creds import load_creds

SUPABASE_URL, SUPABASE_KEY = load_creds()
DIR = "2026 dados/Custos pessoal"
F1 = f"{DIR}/Base Orange - Jan a Abr.xlsx"
F2 = f"{DIR}/Base Orange - Mar e Abr.xlsx"

COMPANY_NAMES = {
    "BR02": "BR02 FCamara", "BR03": "BR03 Omnik", "BR04": "BR04 Nação Digital",
    "BR05": "BR05 SGA", "BR07": "BR07 Hyper", "BR0C": "BR07 Hyper",
    "BR08": "BR08 Dojo", "BR09": "BR09 NextGen",
}


def _norm(s):
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().upper()


def _periodo_str(p) -> str:
    try:
        return f"2026-{int(p):02d}"
    except Exception:
        return ""


def _empresa_from_pep(pep: str) -> str:
    if not pep or len(pep) < 4:
        return ""
    pref = pep[:4].upper()
    return COMPANY_NAMES.get(pref, pref)


def _load_orange():
    j = pd.read_excel(F1, sheet_name="monthly_hours_history")
    m = pd.read_excel(F2, sheet_name="monthly_hours_history")
    # Jan-Abr: usa apenas periodos 1-2
    j = j[j["period"].isin([1, 2])].copy()
    j["_source_file"] = "Base Orange - Jan a Abr.xlsx"
    # Mar-Abr: usa periodos 3-4
    m = m[m["period"].isin([3, 4])].copy()
    m["_source_file"] = "Base Orange - Mar e Abr.xlsx"
    df = pd.concat([j, m], ignore_index=True)
    df["periodo"] = df["period"].apply(_periodo_str)
    df["horas"] = pd.to_numeric(df["total_horas_orange"], errors="coerce").fillna(0)
    df["_pessoa_key"] = df["consultant_name"].apply(_norm)
    return df


def _load_racionais_people():
    """Retorna set de (pessoa_norm, periodo, pep_base) que tem racional na nova_base.

    Granularidade por-PEP: se pessoa apontou no racional no PEP X em Jan, NAO
    importamos Orange dela pra PEP X em Jan — mas importamos Orange dela pra
    outros PEPs no mesmo mes (ela pode ter trabalhado em varios projetos).
    """
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    allr = []
    off = 0
    while True:
        r = httpx.get(
            f"{SUPABASE_URL}/rest/v1/nova_base?select=nome_pessoa,periodo,pep_base,horas&fonte=eq.racionais&offset={off}&limit=1000",
            headers=h, timeout=60,
        )
        d = r.json()
        if not isinstance(d, list):
            print("ERR", d); return set()
        allr += d
        if len(d) < 1000:
            break
        off += 1000
    print(f"racionais: {len(allr)} linhas carregadas")
    trios = set()
    for x in allr:
        nm = _norm(x.get("nome_pessoa"))
        per = str(x.get("periodo") or "").strip()
        pb = str(x.get("pep_base") or "").strip()
        if nm and per and pb:
            trios.add((nm, per, pb))
    return trios


def main():
    apply = "--apply" in sys.argv

    df = _load_orange()
    print(f"Orange total (pre-filtros): {len(df)}")
    print("  por periodo:")
    print(df.groupby("periodo").size().to_dict())

    # so linhas com horas > 0
    df = df[df["horas"] > 0].copy()
    print(f"Orange com horas>0: {len(df)}")

    # carrega trios (pessoa, periodo, pep_base) que ja tem racional
    rac_trios = _load_racionais_people()
    print(f"Racional: {len(rac_trios)} trios (pessoa, periodo, pep) distintos")

    # filtra: pula APENAS Orange row de (pessoa, periodo, PEP) que ja tem racional.
    # Se a pessoa apontou racional em PEP X mas tem horas Orange em PEP Y no
    # mesmo mes, mantemos as horas Y (PEPs distintos = projetos distintos).
    pep_base_col = df["work_package"].astype(str).str.split(".").str[0].fillna("")
    mask_sem_rac = ~pd.Series(
        [(p, per, pb) in rac_trios for p, per, pb in zip(df["_pessoa_key"], df["periodo"], pep_base_col)],
        index=df.index,
    )
    df_novo = df[mask_sem_rac].copy()
    print(f"Orange sem racional no mesmo (pessoa, periodo, PEP): {len(df_novo)}")
    print("  por periodo:")
    print(df_novo.groupby("periodo").size().to_dict())
    print("  pessoas distintas:", df_novo["_pessoa_key"].nunique())
    print("  total horas:", round(df_novo["horas"].sum(), 1))

    # monta records
    UPLOAD_ID = str(uuid.uuid4())
    UPLOADED_AT = datetime.now(timezone.utc).isoformat()
    UPLOADED_BY = "amanda.paula@fcamara.com"

    records = []
    for _, r in df_novo.iterrows():
        pep = str(r.get("work_package") or "").strip() or None
        pep_base = pep.split(".")[0] if pep else None
        empresa = _empresa_from_pep(pep_base or "")
        records.append({
            "upload_id": UPLOAD_ID, "uploaded_at": UPLOADED_AT, "uploaded_by": UPLOADED_BY,
            "fonte": "base Orange",
            "fonte_dados": r["_source_file"],
            "periodo": r["periodo"],
            "empresa": empresa or None,
            "nome_pessoa": str(r.get("consultant_name") or "").strip() or None,
            "pep": pep,
            "pep_base": pep_base,
            "tipos": str(r.get("project_name") or "").strip() or None,
            "area": str(r.get("cost_center") or "").strip() or None,
            "tipo_contrato": str(r.get("contrato") or "").strip() or None,
            "horas": round(float(r["horas"]), 4),
            "receita": 0,
            "custo_rateado": 0,
            "valor_liquido": 0,
            "margem": 0,
        })

    print(f"\nRecords prontos: {len(records)}")
    if records:
        print("Amostra:")
        for x in records[:3]:
            print(f"  {x['periodo']} {x['nome_pessoa']!r} pep={x['pep']} h={x['horas']}")

    if not apply:
        print("\n[DRY-RUN] use --apply pra efetivar")
        return

    # delete antigos (caso re-rode)
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "return=minimal"}
    with httpx.Client(timeout=120) as c:
        r = c.delete(f"{SUPABASE_URL}/rest/v1/nova_base?fonte=eq.base Orange", headers=h)
        print(f"DELETE existentes: {r.status_code}")
        BATCH = 300
        done = 0
        for i in range(0, len(records), BATCH):
            chunk = records[i:i + BATCH]
            r = c.post(f"{SUPABASE_URL}/rest/v1/nova_base", headers=h, json=chunk)
            if r.status_code >= 300:
                print(f"ERRO batch {i}: {r.status_code} {r.text[:300]}")
                return
            done += len(chunk)
            print(f"  {done}/{len(records)}")
    print(f"\nOK: {done} linhas inseridas com fonte='base Orange'")


if __name__ == "__main__":
    main()

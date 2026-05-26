"""Adiciona CPFs faltantes na pessoas table extraindo de:
- Mapa Pessoas - Mar26.xlsx aba CLTs (coluna CPF)
- Mapa Pessoas - Mar26.xlsx aba PJs (coluna worker_id)
"""
import sys, io, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
import httpx
from _supabase_creds import load_creds

MAPA = "2026 dados/Mapa Pessoas - Mar26.xlsx"
url, key = load_creds()
HP = {"apikey": key, "Authorization": f"Bearer {key}",
      "Content-Type": "application/json",
      "Prefer": "resolution=merge-duplicates,return=minimal"}


def norm(s):
    if not s or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().upper()


def existing_cpfs():
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    out = set()
    off = 0
    while True:
        r = httpx.get(f"{url}/rest/v1/pessoas?select=cpf&offset={off}&limit=1000", headers=h, timeout=30)
        d = r.json()
        if not isinstance(d, list): break
        for x in d:
            cpf_d = re.sub(r"\D", "", str(x.get("cpf") or ""))
            if len(cpf_d) >= 11:
                out.add(cpf_d)
        if len(d) < 1000: break
        off += 1000
    return out


def main():
    apply = "--apply" in sys.argv
    existing = existing_cpfs()
    print(f"Pessoas existentes: {len(existing)}")

    # PJs
    pj = pd.read_excel(MAPA, sheet_name="PJs")
    pj["cpf_d"] = pj["worker_id"].astype(str).str.replace(r"\D", "", regex=True)
    pj = pj[pj["cpf_d"].str.len() >= 11].drop_duplicates("cpf_d")
    pj_new = pj[~pj["cpf_d"].isin(existing)].copy()
    print(f"PJs.xlsx: {len(pj_new)} CPFs novos")

    # CLTs
    clt = pd.read_excel(MAPA, sheet_name="CLTs")
    clt.columns = [str(c).strip() for c in clt.columns]
    clt["cpf_d"] = clt["CPF"].astype(str).str.replace(r"\D", "", regex=True)
    clt = clt[clt["cpf_d"].str.len() >= 11].drop_duplicates("cpf_d")
    clt_new = clt[~clt["cpf_d"].isin(existing)].copy()
    print(f"CLTs.xlsx: {len(clt_new)} CPFs novos")

    # Construir records
    records = []
    for _, r in pj_new.iterrows():
        records.append({
            "cpf": f"BRCPF{r['cpf_d']}",
            "nome": str(r["worker_name"]).strip(),
            "contrato": "PJ",
            "fonte_dados": "Mapa Pessoas - Mar26.xlsx (PJs)",
        })
    for _, r in clt_new.iterrows():
        records.append({
            "cpf": f"BRCPF{r['cpf_d']}",
            "nome": str(r["Nome"]).strip(),
            "contrato": "CLT",
            "fonte_dados": "Mapa Pessoas - Mar26.xlsx (CLTs)",
        })

    print(f"\nTotal a upsertar: {len(records)}")
    if not records:
        return
    print("Amostra:")
    for x in records[:5]:
        print(f"  {x['contrato']:3s} {x['cpf']} {x['nome']!r}")

    if not apply:
        print("\n[DRY-RUN] use --apply pra efetivar")
        return

    done = 0
    with httpx.Client(timeout=60) as c:
        BATCH = 200
        for i in range(0, len(records), BATCH):
            chunk = records[i:i+BATCH]
            r = c.post(f"{url}/rest/v1/pessoas?on_conflict=cpf", headers=HP, json=chunk)
            if r.status_code >= 300:
                print(f"ERRO: {r.status_code} {r.text[:300]}")
                return
            done += len(chunk)
            print(f"  {done}/{len(records)}")
    print(f"\nOK: {done} pessoas upserted")


if __name__ == "__main__":
    main()

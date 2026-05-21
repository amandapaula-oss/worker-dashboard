"""Parse Budget 2026 xlsx (abas nextGen + Ecossistema) e sobe para Supabase
nova_base com fonte='Budget'. Cada linha = (cliente, vertical, mes) com
receita, custo (= receita-LB) e LB.
"""
from __future__ import annotations
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import httpx
from datetime import datetime, timezone

from _supabase_creds import load_creds
SUPABASE_URL, SUPABASE_KEY = load_creds()

XLSX = r"2026 dados/Budget/Cópia de Proposta Meta 2026 comparativo por AE  A x B v2.xlsx"

VERT_MAP = {
    "Finance": "BU Finance",
    "Finance & Insurance": "BU Finance",
    "Insurance": "BU Finance",
    "Retail": "BU Retail",
    "Health": "BU Health",
    "Multisector": "BU Multisector",
    "Logistics": "BU Logistics",
    "Grupo Mult": "BU Logistics",
}

# colunas dos meses 2026 dentro de cada aba (zero-based)
SHEETS = [
    {"name": "Budget Clientes nextGen",     "tipo_col": 7, "vert_col": 8, "cli_col": 10, "m_start": 33},
    {"name": "Budget Clientes Ecossistema", "tipo_col": 7, "vert_col": 8, "cli_col": 10, "m_start": 32},
]


def _parse_sheet(cfg: dict) -> list[dict]:
    df = pd.read_excel(XLSX, sheet_name=cfg["name"], header=None)
    out: dict[tuple[str, str, str], dict] = {}
    start = cfg["m_start"]
    months = [f"2026-{m:02d}" for m in range(1, 13)]
    for i in range(7, len(df)):
        tipo = str(df.iat[i, cfg["tipo_col"]]).strip() if not pd.isna(df.iat[i, cfg["tipo_col"]]) else ""
        if tipo not in ("Receita", "LB"):
            continue
        vert_raw = str(df.iat[i, cfg["vert_col"]]).strip() if not pd.isna(df.iat[i, cfg["vert_col"]]) else ""
        cli = str(df.iat[i, cfg["cli_col"]]).strip() if not pd.isna(df.iat[i, cfg["cli_col"]]) else ""
        if not cli or cli.lower() in ("nan", "total", ""):
            continue
        vert = VERT_MAP.get(vert_raw, vert_raw or "BU Others")
        for k, mes in enumerate(months):
            col = start + k
            if col >= df.shape[1]:
                break
            val = df.iat[i, col]
            if pd.isna(val):
                val = 0.0
            try:
                val = float(val)
            except Exception:
                val = 0.0
            key = (vert, cli, mes)
            if key not in out:
                out[key] = {"vertical": vert, "nome_cliente": cli, "periodo": mes,
                            "receita": 0.0, "lb": 0.0}
            if tipo == "Receita":
                out[key]["receita"] += val
            else:
                out[key]["lb"] += val
    return list(out.values())


def main():
    all_rows: list[dict] = []
    for cfg in SHEETS:
        rows = _parse_sheet(cfg)
        print(f"{cfg['name']}: {len(rows)} (cliente,mes)")
        all_rows.extend(rows)

    # consolida duplicatas inter-aba (raro mas seguro)
    cons: dict[tuple, dict] = {}
    for r in all_rows:
        k = (r["vertical"], r["nome_cliente"], r["periodo"])
        if k not in cons:
            cons[k] = r
        else:
            cons[k]["receita"] += r["receita"]
            cons[k]["lb"] += r["lb"]

    records = []
    agora = datetime.now(timezone.utc).isoformat()
    tot_r = tot_lb = tot_c = 0.0
    for r in cons.values():
        # custo = -(receita - LB) — armazena como NEGATIVO (mesma convencao da nova_base)
        receita = round(r["receita"], 2)
        lb = round(r["lb"], 2)
        custo = round(-(receita - lb), 2)  # custo é negativo
        if receita == 0 and lb == 0:
            continue
        records.append({
            "periodo": r["periodo"],
            "vertical": r["vertical"],
            "nome_cliente": r["nome_cliente"],
            "fonte": "Budget",
            "receita": receita,
            "custo_rateado": custo,
            "valor_liquido": lb,
            "empresa": "Budget 2026",
        })
        tot_r += receita
        tot_lb += lb
        tot_c += custo

    print(f"\nTotal linhas: {len(records)}")
    print(f"Receita: R$ {tot_r:,.0f}")
    print(f"Custo:   R$ {tot_c:,.0f}")
    print(f"LB:      R$ {tot_lb:,.0f}")

    if "--dry" in sys.argv:
        # mostra top 10 clientes por receita
        df = pd.DataFrame(records)
        top = df.groupby("nome_cliente")["receita"].sum().sort_values(ascending=False).head(15)
        print("\nTop 15 clientes (Receita 2026):")
        for n, v in top.items():
            print(f"  {n[:40]:40s} R$ {v:>15,.0f}")
        print("\nBUs:")
        for n, v in df.groupby("vertical")["receita"].sum().sort_values(ascending=False).items():
            print(f"  {n[:25]:25s} R$ {v:>15,.0f}")
        return

    # 1. deleta budget anterior
    headers = {
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=minimal",
    }
    url = f"{SUPABASE_URL}/rest/v1/nova_base"
    with httpx.Client(timeout=120) as cli:
        r = cli.delete(f"{url}?fonte=eq.Budget", headers=headers)
        print(f"Delete budget antigo: {r.status_code}")

        BATCH = 500
        for i in range(0, len(records), BATCH):
            chunk = records[i:i + BATCH]
            r = cli.post(url, headers=headers, json=chunk)
            if r.status_code not in (200, 201, 204):
                print(f"ERRO batch {i}: {r.status_code} {r.text[:300]}")
                return
            print(f"  inseridas {i + len(chunk)}/{len(records)}")
    print("\nOK budget upload concluído.")


if __name__ == "__main__":
    main()

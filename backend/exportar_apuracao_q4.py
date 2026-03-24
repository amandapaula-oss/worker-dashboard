"""
Gera Excel com apuração Q4 por pessoa / WS / categoria.
Colunas: Nome | Posicao | WS | Categoria | Valor_Q4

Uso:
    cd backend
    python exportar_apuracao_q4.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from apuracao_engine import (
    _load_all, calc_bonus_ae, calc_bonus_diretor, norm,
    WS_PESOS_Q4,
)

OUTPUT = os.path.join(os.path.dirname(__file__), "apuracao_q4_exportado.xlsx")

POSICOES_AE   = {"AE", "AE2", "HUNTER", "ESTRATEGISTAS", "CS"}
POSICOES_DIR  = {"DIRETOR"}


def linhas_ae(res: dict) -> list[dict]:
    nome    = res["nome"]
    posicao = res["posicao"]
    rows    = []
    for w in res.get("detalhe_ws", []):
        ws        = w["ws"].upper()
        real_rec  = w["real_rec"]
        real_mb   = w.get("real_lb_financeiro") if w.get("real_lb_financeiro") is not None else round(real_rec * w["real_mb_pct"] / 100, 2)
        real_custo= round(real_rec - real_mb, 2)
        for cat, val in [("Receita", real_rec), ("Custo", -real_custo), ("LB", real_mb)]:
            rows.append({"Nome": nome, "Posicao": posicao, "WS": ws,
                         "Categoria": cat, "Valor_Q4": val})
    # totais
    tot_rec = res.get("real_rec_total", 0)
    tot_lb  = res.get("real_lb_total",  0)  # LB benchmark total
    lb_real = res.get("real_lb_financeiro", tot_lb)  # LB SAP (gatilho)
    mb_val  = tot_lb
    custo_v = round(tot_rec - mb_val, 2)
    for cat, val in [
        ("Receita", tot_rec),
        ("Custo",  -custo_v),
        ("MB",      mb_val),
        ("LB",      lb_real),
    ]:
        rows.append({"Nome": nome, "Posicao": posicao, "WS": "TOTAL",
                     "Categoria": cat, "Valor_Q4": val})
    return rows


def linhas_diretor(res: dict) -> list[dict]:
    nome    = res["nome"]
    posicao = res["posicao"]
    rows    = []

    # ── por WS (SAP/RAC-based) ──────────────────────────────────────────────
    for w in res.get("detalhe_ws", []):
        ws       = w["ws"].upper()
        real_rec = w["real_rec"]
        real_lb  = w.get("real_lb_ws", round(real_rec * w["real_mb_pct"] / 100, 2))
        custo_v  = round(real_rec - real_lb, 2)
        for cat, val in [("Receita", real_rec), ("Custo", -custo_v), ("LB", real_lb)]:
            rows.append({"Nome": nome, "Posicao": posicao, "WS": ws,
                         "Categoria": cat, "Valor_Q4": val})

    # ── totais WS (soma) ────────────────────────────────────────────────────
    tot_rec_ws = sum(w["real_rec"] for w in res.get("detalhe_ws", []))
    tot_lb_ws  = sum(w.get("real_lb_ws", 0) for w in res.get("detalhe_ws", []))
    tot_cu_ws  = round(tot_rec_ws - tot_lb_ws, 2)
    for cat, val in [("Receita", tot_rec_ws), ("Custo", -tot_cu_ws), ("LB", tot_lb_ws)]:
        rows.append({"Nome": nome, "Posicao": posicao, "WS": "TOTAL",
                     "Categoria": cat, "Valor_Q4": val})

    # ── Nexus: custos, despesas, MB e MC ────────────────────────────────────
    gross_rev   = res.get("real_gross_rev", 0) or 0
    custo_nexus = (res.get("real_payroll", 0) or 0) \
                + (res.get("real_third_party", 0) or 0) \
                + (res.get("real_other_costs", 0) or 0)   # valores negativos
    despesas    = (res.get("real_payroll_exp", 0) or 0) \
                + (res.get("real_deductions", 0) or 0)     # valores negativos
    mb_nexus    = gross_rev + custo_nexus                  # Receita - |Custo|
    mc_nexus    = mb_nexus + despesas                      # MB - |Despesas|

    for cat, val in [
        ("Receita",  gross_rev),
        ("Custo",    custo_nexus),      # negativo
        ("MB",       mb_nexus),
        ("Despesas", despesas),         # negativo
        ("MC",       mc_nexus),
    ]:
        rows.append({"Nome": nome, "Posicao": posicao, "WS": "NEXUS",
                     "Categoria": cat, "Valor_Q4": round(val, 2)})
    return rows


def main():
    d = _load_all()
    pessoas = d["pessoas"]

    todas: list[dict] = []
    erros: list[str]  = []

    for _, p in pessoas.iterrows():
        nome   = p["Nome"]
        pos    = str(p["Posicao"]).upper().strip()
        sal    = float(p["Sal_Q4"] or 0)
        if sal == 0:
            continue

        try:
            if pos in POSICOES_DIR:
                res  = calc_bonus_diretor(nome)
                rows = linhas_diretor(res)
            elif pos in POSICOES_AE:
                res  = calc_bonus_ae(nome)
                rows = linhas_ae(res)
            else:
                continue
            todas.extend(rows)
        except Exception as e:
            erros.append(f"{nome}: {e}")

    df = pd.DataFrame(todas, columns=["Nome", "Posicao", "WS", "Categoria", "Valor_Q4"])

    # ordena
    ws_order  = {ws.upper(): i for i, ws in enumerate(list(WS_PESOS_Q4.keys()) + ["TOTAL", "NEXUS"])}
    cat_order = {"Receita": 0, "Custo": 1, "LB": 2, "MB": 3, "Despesas": 4, "MC": 5}
    df["_ws_ord"]  = df["WS"].map(lambda x: ws_order.get(x, 99))
    df["_cat_ord"] = df["Categoria"].map(lambda x: cat_order.get(x, 99))
    df = df.sort_values(["Nome", "_ws_ord", "_cat_ord"]).drop(columns=["_ws_ord", "_cat_ord"])

    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Apuracao_Q4")
        ws_sheet = writer.sheets["Apuracao_Q4"]

        # formata coluna de valor como número
        from openpyxl.styles import numbers as xl_numbers
        for row in ws_sheet.iter_rows(min_row=2, min_col=5, max_col=5):
            for cell in row:
                cell.number_format = '#,##0.00'

        # auto-largura
        for col in ws_sheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws_sheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    print(f"OK Arquivo gerado: {OUTPUT}")
    print(f"  {len(df)} linhas | {df['Nome'].nunique()} pessoas")
    if erros:
        print(f"\nErros ({len(erros)}):")
        for e in erros:
            print(f"  - {e}")


if __name__ == "__main__":
    main()

"""
Gera os arquivos consolidados a partir dos arquivos de entrada.

Arquivos de entrada (legados):
  rac_projetos.csv    +  margem_projetos.csv    →  operacional.xlsx / projetos
  tcv_realizado.csv   +  q3_realizados_gm.csv   →  parametros.xlsx / realizados_manual
  sap_agg.csv         +  nexus_agg.csv (raw)
                      +  razao_agg.csv           →  operacional.xlsx / financeiro
  nexus_agg.csv (raw)                            →  operacional.xlsx / nexus_agg

Uso:
    cd backend
    python criar_arquivos_consolidados.py
"""
import os
import pandas as pd

DIR = os.path.dirname(__file__)

def p(name):
    return os.path.join(DIR, name)


# ─────────────────────────────────────────────────────────────────────────────
# 1. projetos.csv
#    Consolida rac_projetos + margem_projetos
#    Schema: periodo, empresa, pep, nome_cliente, tipos, centro_lucro,
#            no_hierarquia, categoria_bu, receita, custo_rateado, horas
# ─────────────────────────────────────────────────────────────────────────────

def build_projetos():
    rac  = pd.read_csv(p("rac_projetos.csv"),  encoding="utf-8-sig", dtype={"pep": str})
    marg = pd.read_csv(p("margem_projetos.csv"), encoding="utf-8-sig", dtype={"pep": str})

    # normaliza pep para a base (BR02CLP00050.0.1 → BR02CLP00050)
    rac["pep_base"]  = rac["pep"].str.split(".").str[0].str.strip()
    marg["pep_base"] = marg["pep"].str.split(".").str[0].str.strip()

    # agrega rac por periodo+pep_base+nome_cliente → receita_rac + tipos (csv)
    rac_agg = (
        rac.groupby(["periodo", "pep_base", "nome_cliente", "empresa"])
        .agg(
            receita_rac=("valor_liquido", "sum"),
            tipos=("tipo", lambda x: ",".join(sorted(set(x.dropna().astype(str))))),
        )
        .reset_index()
    )

    # merge outer: começa por marg (tem custo/horas), traz rac por cima
    merged = marg.merge(
        rac_agg[["periodo", "pep_base", "nome_cliente", "receita_rac", "tipos"]],
        on=["periodo", "pep_base", "nome_cliente"],
        how="outer",
    )

    # para linhas só do rac (sem dados no marg), preenche empresa a partir do rac
    rac_only_mask = merged["receita"].isna()
    if rac_only_mask.any():
        rac_emp = rac_agg.set_index(["periodo", "pep_base", "nome_cliente"])["empresa"]
        for idx in merged[rac_only_mask].index:
            key = (merged.at[idx, "periodo"],
                   merged.at[idx, "pep_base"],
                   merged.at[idx, "nome_cliente"])
            if key in rac_emp.index:
                merged.at[idx, "empresa"] = rac_emp[key]

    # receita final: preferência ao rac; fallback ao sap
    # Threshold de R$1 para ignorar floating-point lixo do SAP (ex: 8.14e-10)
    rac_valido = merged["receita_rac"].notna() & (merged["receita_rac"].abs() >= 1)
    merged["receita"] = merged["receita_rac"].where(rac_valido, merged["receita"])

    # usa pep_base como pep no csv final (forma canônica)
    merged["pep"] = merged["pep_base"].where(
        merged["pep_base"].notna(), merged["pep"]
    )

    cols = [
        "periodo", "empresa", "pep", "nome_cliente",
        "tipos", "centro_lucro", "no_hierarquia", "categoria_bu",
        "receita", "custo_rateado", "horas_total",
    ]
    # garante que todas as colunas existam
    for c in cols:
        if c not in merged.columns:
            merged[c] = None

    out = merged[cols].rename(columns={"horas_total": "horas"})
    out = out.sort_values(["periodo", "empresa", "pep", "nome_cliente"])
    with pd.ExcelWriter(p("operacional.xlsx"), engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        out.to_excel(w, sheet_name="projetos", index=False)
    print(f"operacional.xlsx/projetos gerado: {len(out)} linhas")
    print(f"  com receita_rac: {out['receita'].notna().sum()}")
    print(f"  com custo:       {out['custo_rateado'].notna().sum()}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 2. realizados_manual.csv
#    Consolida tcv_realizado + q3_realizados_gm
#    Schema: tipo, ae_ou_vertical, cliente, receita, lb
# ─────────────────────────────────────────────────────────────────────────────

def build_realizados():
    tcv = pd.read_csv(p("tcv_realizado.csv"),     encoding="utf-8-sig")
    q3  = pd.read_csv(p("q3_realizados_gm.csv"),  encoding="utf-8-sig")

    rows = []

    # TCV Q4 e Q3 por vertical
    for _, row in tcv.iterrows():
        rows.append({
            "tipo":          "TCV_Q4",
            "ae_ou_vertical": row["vertical"],
            "cliente":        "",
            "receita":        float(row.get("tcv_realizado", 0) or 0),
            "lb":             None,
        })
        if "tcv_q3" in tcv.columns:
            rows.append({
                "tipo":          "TCV_Q3",
                "ae_ou_vertical": row["vertical"],
                "cliente":        "",
                "receita":        float(row.get("tcv_q3", 0) or 0),
                "lb":             None,
            })

    # Realizados Q3 Grupo Mult (por cliente)
    for _, row in q3.iterrows():
        rows.append({
            "tipo":          "Q3_GM",
            "ae_ou_vertical": row["farmer"],
            "cliente":        row["cliente"],
            "receita":        float(row.get("receita", 0) or 0),
            "lb":             float(row.get("lb", 0) or 0),
        })

    out = pd.DataFrame(rows, columns=["tipo", "ae_ou_vertical", "cliente", "receita", "lb"])
    with pd.ExcelWriter(p("parametros.xlsx"), engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        out.to_excel(w, sheet_name="realizados_manual", index=False)
    print(f"parametros.xlsx/realizados_manual gerado: {len(out)} linhas")
    print(f"  TCV_Q4: {len(out[out['tipo']=='TCV_Q4'])}")
    print(f"  TCV_Q3: {len(out[out['tipo']=='TCV_Q3'])}")
    print(f"  Q3_GM:  {len(out[out['tipo']=='Q3_GM'])}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 3. financeiro.csv
#    Consolida sap_agg + nexus_agg + razao_agg
#    Schema: periodo, fonte, empresa, vertical, agrupador, valor,
#            profit_center, tipo_financeiro, moeda, stream, ano
# ─────────────────────────────────────────────────────────────────────────────

def build_financeiro(sap_ano: int = 2025):
    sap = pd.read_csv(p("sap_agg.csv"),   encoding="utf-8-sig")
    nex = pd.read_csv(p("nexus_agg.csv"), encoding="utf-8-sig")  # arquivo raw de entrada
    raz = pd.read_csv(p("razao_agg.csv"), encoding="utf-8-sig")

    # ── SAP ──────────────────────────────────────────────────────────────────
    sap_rows = pd.DataFrame({
        "periodo":        sap["FiscalPeriod"].apply(lambda m: f"{sap_ano}-{int(m):02d}"),
        "fonte":          "SAP",
        "empresa":        sap["CompanyCode"],
        "vertical":       sap["vertical"],
        "agrupador":      sap["agrupador_fpa"],
        "valor":          sap["AmountInCompanyCodeCurrency"],
        "profit_center":  sap["ProfitCenter"],
        "tipo_financeiro": None,
        "moeda":          None,
        "stream":         None,
        "ano":            sap_ano,
    })

    # ── Nexus ─────────────────────────────────────────────────────────────────
    nex_rows = pd.DataFrame({
        "periodo":        nex["Periodo"],
        "fonte":          "Nexus",
        "empresa":        nex["[Empresa]"],
        "vertical":       nex["[Vertical]"],
        "agrupador":      nex["Agrupador"],
        "valor":          nex["[Valor]"],
        "profit_center":  None,
        "tipo_financeiro": nex["[Tipo]"],
        "moeda":          nex["[Moeda]"],
        "stream":         nex["[Stream]"],
        "ano":            nex["Ano"],
    })

    # ── Razão ─────────────────────────────────────────────────────────────────
    raz_rows = pd.DataFrame({
        "periodo":        raz.apply(lambda r: f"{int(r['FiscalYear'])}-{int(r['FiscalPeriod']):02d}", axis=1),
        "fonte":          "Razao",
        "empresa":        raz["empresa"],
        "vertical":       None,
        "agrupador":      raz["agrupador_fpa"],
        "valor":          raz["AmountInCompanyCodeCurrency"],
        "profit_center":  None,
        "tipo_financeiro": None,
        "moeda":          None,
        "stream":         None,
        "ano":            raz["FiscalYear"],
    })

    out = pd.concat([sap_rows, nex_rows, raz_rows], ignore_index=True)
    out = out.sort_values(["fonte", "periodo", "empresa"])
    with pd.ExcelWriter(p("operacional.xlsx"), engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        out.to_excel(w, sheet_name="financeiro", index=False)
        nex.to_excel(w, sheet_name="nexus_agg", index=False)
    print(f"operacional.xlsx/financeiro gerado: {len(out)} linhas")
    print(f"  SAP:   {len(sap_rows)}")
    print(f"  Nexus: {len(nex_rows)}")
    print(f"  Razão: {len(raz_rows)}")
    return out


if __name__ == "__main__":
    print("=== Atualizando arquivos consolidados ===\n")
    build_projetos()
    print()
    build_realizados()
    print()
    build_financeiro()
    print("\nConcluído.")

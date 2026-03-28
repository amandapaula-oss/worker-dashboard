"""
Exporta base completa Q4 Grupo Mult:
  Sheet 1 - Projetos_Receita_Custo: periodo, pep, nome_cliente, receita, custo_rateado, margem
  Sheet 2 - Pessoas_por_PEP: periodo, pep, nome_cliente, nome_pessoa, receita, custo_rateado, horas

Uso:
    cd backend
    python exportar_grupo_mult_q4.py
"""
import os
import pandas as pd

DIR = os.path.dirname(__file__)

def p(name):
    return os.path.join(DIR, name)


def main():
    # ── Clientes Grupo Mult ──────────────────────────────────────────────────
    clientes_df = pd.read_excel(p("parametros.xlsx"), sheet_name="clientes", dtype=str)
    gm = clientes_df[clientes_df["bu"].str.strip() == "Grupo Mult"].copy()

    # nomes canônicos + aliases SAP
    nomes_gm = set(gm["nome_cliente"].dropna().str.strip())
    nomes_base = set(gm["nome_base"].dropna().str.strip())
    todos_nomes = nomes_gm | nomes_base

    # mapa nome_base → nome_cliente (para normalizar)
    base_to_canonical = {}
    for _, row in gm.iterrows():
        nb = str(row["nome_base"]).strip() if pd.notna(row["nome_base"]) else ""
        nc = str(row["nome_cliente"]).strip()
        if nb:
            base_to_canonical[nb] = nc

    # ── Projetos Q4 ─────────────────────────────────────────────────────────
    proj = pd.read_excel(p("operacional.xlsx"), sheet_name="projetos", dtype={"pep": str})
    proj["periodo"] = proj["periodo"].astype(str).str.strip()
    proj["nome_cliente"] = proj["nome_cliente"].astype(str).str.strip()

    # filtra Q4 2025
    q4 = proj[proj["periodo"].isin(["2025-10", "2025-11", "2025-12"])].copy()

    # marca quais são Grupo Mult
    q4_gm = q4[q4["nome_cliente"].isin(todos_nomes)].copy()

    # normaliza para nome canônico
    q4_gm["nome_cliente"] = q4_gm["nome_cliente"].map(
        lambda x: base_to_canonical.get(x, x)
    )

    # adiciona ae do clientes
    ae_map = gm.drop_duplicates("nome_cliente").set_index("nome_cliente")["ae"]
    q4_gm["ae"] = q4_gm["nome_cliente"].map(ae_map)

    sheet1 = q4_gm[[
        "periodo", "empresa", "pep", "nome_cliente", "ae",
        "tipos", "categoria_bu", "centro_lucro", "no_hierarquia",
        "receita", "custo_rateado", "horas",
    ]].copy()
    sheet1["receita"]       = pd.to_numeric(sheet1["receita"],       errors="coerce").fillna(0)
    sheet1["custo_rateado"] = pd.to_numeric(sheet1["custo_rateado"], errors="coerce").fillna(0)
    sheet1["horas"]         = pd.to_numeric(sheet1["horas"],         errors="coerce").fillna(0)
    sheet1["margem"]        = sheet1["receita"] + sheet1["custo_rateado"]
    sheet1 = sheet1.sort_values(["nome_cliente", "pep", "periodo"])

    # ── Pessoas por PEP (margem_pessoas) ────────────────────────────────────
    pess = pd.read_excel(p("operacional.xlsx"), sheet_name="margem_pessoas", dtype={"pep": str})
    pess["periodo"]      = pess["periodo"].astype(str).str.strip()
    pess["pep"]          = pess["pep"].astype(str).str.strip()
    pess["pep_base"]     = pess["pep"].str.split(".").str[0].str.strip()

    # peps Grupo Mult Q4
    peps_gm = set(q4_gm["pep"].dropna().astype(str).str.strip())

    pess_q4 = pess[
        pess["periodo"].isin(["2025-10", "2025-11", "2025-12"]) &
        pess["pep_base"].isin(peps_gm)
    ].copy()

    # junta nome_cliente + ae a partir dos projetos
    proj_ref = q4_gm[["pep", "nome_cliente", "ae"]].drop_duplicates("pep")
    pess_q4 = pess_q4.merge(proj_ref, left_on="pep_base", right_on="pep", how="left", suffixes=("", "_proj"))

    pess_q4["receita"]       = pd.to_numeric(pess_q4["receita"],       errors="coerce").fillna(0)
    pess_q4["custo_rateado"] = pd.to_numeric(pess_q4["custo_rateado"], errors="coerce").fillna(0)
    pess_q4["horas"]         = pd.to_numeric(pess_q4["horas"],         errors="coerce").fillna(0)

    sheet2 = pess_q4[[
        "periodo", "empresa", "pep_base", "nome_cliente", "ae",
        "nome", "receita", "custo_rateado", "horas",
    ]].rename(columns={"pep_base": "pep", "nome": "nome_pessoa"})
    sheet2 = sheet2.sort_values(["nome_cliente", "pep", "periodo", "nome_pessoa"])

    # ── Excel ────────────────────────────────────────────────────────────────
    output = p("grupo_mult_q4.xlsx")
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sheet1.to_excel(writer, index=False, sheet_name="Projetos_Receita_Custo")
        sheet2.to_excel(writer, index=False, sheet_name="Pessoas_por_PEP")

        for sheet_name in ["Projetos_Receita_Custo", "Pessoas_por_PEP"]:
            ws = writer.sheets[sheet_name]
            # auto-largura
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)
            # formato numérico para colunas de valor
            num_cols = {c.value: c.column for c in ws[1] if c.value in (
                "receita", "custo_rateado", "horas", "margem"
            )}
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    if cell.column in num_cols.values():
                        cell.number_format = '#,##0.00'

    print(f"OK: {output}")
    print(f"  Projetos Q4 Grupo Mult : {len(sheet1)} linhas | {sheet1['pep'].nunique()} PEPs | {sheet1['nome_cliente'].nunique()} clientes")
    print(f"  Pessoas por PEP        : {len(sheet2)} linhas | {sheet2['nome_pessoa'].nunique()} pessoas")

    # resumo por cliente
    print("\nReceita Q4 por cliente:")
    resumo = sheet1.groupby("nome_cliente")[["receita", "custo_rateado", "margem"]].sum()
    resumo = resumo.sort_values("receita", ascending=False)
    print(resumo.to_string())


if __name__ == "__main__":
    main()

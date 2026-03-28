"""
Verificação de integridade dos dados financeiros.

Compara os totais atuais contra uma baseline salva.
Deve ser rodado ANTES e DEPOIS de qualquer modificação nas bases.

Uso:
    python verificar_integridade.py          # mostra totais atuais
    python verificar_integridade.py --salvar # atualiza a baseline
    python verificar_integridade.py --checar # compara com baseline e alerta divergências
"""
import os, sys, json
import pandas as pd

DIR      = os.path.dirname(__file__)
BASELINE = os.path.join(DIR, "integridade_baseline.json")
Q4       = ["2025-10", "2025-11", "2025-12"]
TOLERANCIA = 1.0   # R$ 1,00 — diferenças menores que isso são arredondamento


def calcular_totais() -> dict:
    totais = {}

    # ── projetos.csv ─────────────────────────────────────────────────────────
    proj = pd.read_excel(os.path.join(DIR, "operacional.xlsx"), sheet_name="projetos", dtype={"pep": str})
    proj["receita"]       = pd.to_numeric(proj["receita"],       errors="coerce").fillna(0)
    proj["custo_rateado"] = pd.to_numeric(proj["custo_rateado"], errors="coerce").fillna(0)

    proj_q4 = proj[proj["periodo"].isin(Q4)]
    totais["projetos_receita_q4"]       = round(proj_q4["receita"].sum(), 2)
    totais["projetos_custo_q4"]         = round(proj_q4["custo_rateado"].sum(), 2)
    totais["projetos_receita_total"]    = round(proj["receita"].sum(), 2)
    totais["projetos_custo_total"]      = round(proj["custo_rateado"].sum(), 2)
    totais["projetos_linhas_q4"]        = int(len(proj_q4))

    # ── financeiro.csv (Nexus Q4) ─────────────────────────────────────────────
    fin = pd.read_excel(os.path.join(DIR, "operacional.xlsx"), sheet_name="financeiro")
    fin["valor"] = pd.to_numeric(fin["valor"], errors="coerce").fillna(0)

    nexus_q4 = fin[(fin["fonte"] == "Nexus") & (fin["periodo"].str.startswith("2025-1"))]
    for agrup, val in nexus_q4.groupby("agrupador")["valor"].sum().items():
        key = "nexus_" + agrup.lower().replace(" ", "_").replace("(", "").replace(")", "")
        totais[key] = round(val, 2)

    sap_q4 = fin[(fin["fonte"] == "SAP") & (fin["periodo"].str.startswith("2025-1"))]
    totais["sap_total_q4"] = round(sap_q4["valor"].sum(), 2)

    return totais


def fmt(v: float) -> str:
    return f"R$ {v:>18,.2f}"


def mostrar(totais: dict):
    print("\n=== Totais atuais ===")
    print(f"\n  projetos Q4  receita :  {fmt(totais['projetos_receita_q4'])}")
    print(f"  projetos Q4  custo   :  {fmt(totais['projetos_custo_q4'])}")
    print(f"  projetos ALL receita :  {fmt(totais['projetos_receita_total'])}")
    print(f"  projetos ALL custo   :  {fmt(totais['projetos_custo_total'])}")
    print(f"  projetos Q4  linhas  :  {totais['projetos_linhas_q4']}")
    print(f"\n  SAP Q4 total         :  {fmt(totais['sap_total_q4'])}")
    nexus_keys = [k for k in totais if k.startswith("nexus_")]
    for k in sorted(nexus_keys):
        label = k.replace("nexus_", "").replace("_", " ").title()
        print(f"  Nexus {label:<30}: {fmt(totais[k])}")


def checar(totais: dict):
    if not os.path.exists(BASELINE):
        print("Baseline nao encontrada. Rode com --salvar primeiro.")
        sys.exit(1)

    with open(BASELINE) as f:
        base = json.load(f)

    alertas = []
    for k, v_atual in totais.items():
        v_base = base.get(k)
        if v_base is None:
            alertas.append(f"  NOVO   {k}: {fmt(v_atual)}")
            continue
        diff = v_atual - v_base
        if abs(diff) > TOLERANCIA:
            alertas.append(
                f"  MUDOU  {k}:\n"
                f"         antes : {fmt(v_base)}\n"
                f"         agora : {fmt(v_atual)}\n"
                f"         diff  : {fmt(diff)}"
            )

    for k in base:
        if k not in totais:
            alertas.append(f"  SUMIU  {k}: era {fmt(base[k])}")

    if alertas:
        print("\n⚠️  DIVERGÊNCIAS DETECTADAS:\n")
        for a in alertas:
            print(a)
        print(f"\nTotal de divergências: {len(alertas)}")
        sys.exit(1)
    else:
        print("\n✓ Todos os totais batem com a baseline.")


def salvar(totais: dict):
    with open(BASELINE, "w") as f:
        json.dump(totais, f, indent=2, ensure_ascii=False)
    print(f"Baseline salva em {BASELINE}")


if __name__ == "__main__":
    totais = calcular_totais()
    modo = sys.argv[1] if len(sys.argv) > 1 else ""

    if modo == "--salvar":
        mostrar(totais)
        salvar(totais)
    elif modo == "--checar":
        checar(totais)
        mostrar(totais)
    else:
        mostrar(totais)

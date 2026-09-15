# -*- coding: utf-8 -*-
"""Extrai o CADASTRO DE PEPs direto do SAP — a fonte, sem inferência.

Por que existe: até agora o PEP das receitas era descoberto por inferência
(cliente único na base, casamento por cliente+competência no razão, evidência de
valor recorrente...). O SAP tem o master de projetos, e ele responde de forma
autoritativa "este PEP é de qual cliente".

Cadeia de dados:
    A_EnterpriseProjectElement   → o PEP (ProjectElement) + descrição + empresa
      ↓ ProjectUUID
    A_EnterpriseProject          → CustomerUUID do projeto
      ↓ BusinessPartnerUUID
    A_BusinessPartner            → número e nome do cliente

Saída: backend/pep_master_sap.xlsx
    aba 'PEPs'     — uma linha por elemento de projeto (o que casa com a receita)
    aba 'Projetos' — uma linha por projeto (cabeçalho, com o cliente)
    aba 'Resumo'   — cobertura por empresa

Uso:
    python extrair_pep_master_sap.py
    python extrair_pep_master_sap.py --xlsx caminho/saida.xlsx
"""
import argparse
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

AQUI = Path(__file__).resolve().parent
# As credenciais SAP vivem no .env do extract_pl (mesmo tenant).
load_dotenv(AQUI.parent / "handoff_extract_pl" / ".env")

BASE = os.getenv("SAP_BASE_URL", "").rstrip("/")
USER = os.getenv("SAP_USER", "")
PWD = os.getenv("SAP_PASSWORD", "")

EP = "/sap/opu/odata/sap/API_ENTERPRISE_PROJECT_SRV;v=0002"
BP = "/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner"
PAGINA = 1000
LOTE_BP = 40          # $filter com muitos 'or' estoura o tamanho da URL
TIMEOUT = 300
UUID_ZERO = "00000000-0000-0000-0000-000000000000"


def sessao():
    if not all([BASE, USER, PWD]):
        sys.exit("ERRO: SAP_BASE_URL / SAP_USER / SAP_PASSWORD não configurados "
                 "(esperado em handoff_extract_pl/.env)")
    s = requests.Session()
    s.auth = HTTPBasicAuth(USER, PWD)
    s.headers.update({"Accept": "application/json"})
    return s


def data_sap(v):
    """'/Date(1748736000000)/' -> date. Devolve None no que não é data."""
    if not v:
        return None
    m = re.search(r"/Date\((-?\d+)", str(v))
    if not m:
        return None
    try:
        return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).date()
    except (ValueError, OverflowError, OSError):
        return None


def puxar_tudo(s, entidade, select):
    """Pagina a entidade inteira. Falha ALTO: lista parcial silenciosa já nos
    custou uma carga errada no billing (ver project-extract-billing-carga-parcial)."""
    out, skip = [], 0
    while True:
        r = s.get(f"{BASE}{EP}/{entidade}",
                  params={"$select": select, "$top": str(PAGINA),
                          "$skip": str(skip), "$format": "json"},
                  timeout=TIMEOUT)
        if not r.ok:
            raise RuntimeError(
                f"{entidade}: HTTP {r.status_code} em skip={skip} — "
                f"abortando com {len(out)} registros baixados. {r.text[:200]}")
        res = r.json().get("d", {}).get("results", [])
        out.extend(res)
        print(f"   {entidade}: {len(out)} ...")
        if len(res) < PAGINA:
            return out
        skip += PAGINA


def nomes_de_cliente(s, uuids):
    """BusinessPartnerUUID -> (número, nome). O UUID do projeto é o do BP."""
    uuids = sorted({u for u in uuids if u and u != UUID_ZERO})
    mapa = {}
    print(f"   resolvendo {len(uuids)} cliente(s) no Business Partner ...")
    for i in range(0, len(uuids), LOTE_BP):
        lote = uuids[i:i + LOTE_BP]
        filtro = " or ".join(f"BusinessPartnerUUID eq guid'{u}'" for u in lote)
        r = s.get(f"{BASE}{BP}",
                  params={"$filter": filtro,
                          "$select": "BusinessPartner,BusinessPartnerUUID,"
                                     "BusinessPartnerFullName,OrganizationBPName1",
                          "$top": str(LOTE_BP * 2), "$format": "json"},
                  timeout=TIMEOUT)
        if not r.ok:
            raise RuntimeError(f"BusinessPartner: HTTP {r.status_code} — {r.text[:200]}")
        for x in r.json().get("d", {}).get("results", []):
            u = str(x.get("BusinessPartnerUUID", "")).lower()
            nome = (str(x.get("OrganizationBPName1") or "").strip()
                    or str(x.get("BusinessPartnerFullName") or "").strip())
            mapa[u] = (str(x.get("BusinessPartner") or "").strip(), nome)
    print(f"   resolvidos: {len(mapa)}/{len(uuids)}")
    return mapa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(AQUI / "pep_master_sap.xlsx"))
    args = ap.parse_args()

    s = sessao()

    print("Baixando cabeçalhos de projeto ...")
    projs = puxar_tudo(s, "A_EnterpriseProject",
                       "Project,ProjectDescription,CompanyCode,CustomerUUID,"
                       "ProfitCenter,ResponsibleCostCenter,ProcessingStatus,"
                       "ProjectStartDate,ProjectEndDate,ProjectUUID,ProjectCurrency")

    print("Baixando elementos de projeto (os PEPs) ...")
    els = puxar_tudo(s, "A_EnterpriseProjectElement",
                     "ProjectElement,ProjectElementDescription,CompanyCode,"
                     "ProfitCenter,CostCenter,ResponsibleCostCenter,ProcessingStatus,"
                     "PlannedStartDate,PlannedEndDate,ProjectUUID,WBSElementInternalID")

    clientes = nomes_de_cliente(s, [p.get("CustomerUUID") for p in projs])

    # projeto -> cliente, para herdar no elemento
    por_uuid = {}
    for p in projs:
        u = str(p.get("CustomerUUID") or "").lower()
        num, nome = clientes.get(u, ("", ""))
        por_uuid[p.get("ProjectUUID")] = {
            "projeto": p.get("Project"),
            "projeto_desc": p.get("ProjectDescription"),
            "cliente_id": num,
            "cliente_nome": nome,
        }

    dfp = pd.DataFrame([{
        "projeto": p.get("Project"),
        "descricao": p.get("ProjectDescription"),
        "empresa": p.get("CompanyCode"),
        "cliente_id": por_uuid[p["ProjectUUID"]]["cliente_id"],
        "cliente_nome": por_uuid[p["ProjectUUID"]]["cliente_nome"],
        "profit_center": p.get("ProfitCenter"),
        "centro_custo_resp": p.get("ResponsibleCostCenter"),
        "status": p.get("ProcessingStatus"),
        "moeda": p.get("ProjectCurrency"),
        "inicio": data_sap(p.get("ProjectStartDate")),
        "fim": data_sap(p.get("ProjectEndDate")),
    } for p in projs])

    dfe = pd.DataFrame([{
        "pep": e.get("ProjectElement"),
        # o journal entry grava '.1.' onde o master traz '.0.' — ver extract_pl.py
        "pep_normalizado": str(e.get("ProjectElement") or "").replace(".0.", ".1."),
        "descricao": e.get("ProjectElementDescription"),
        "empresa": e.get("CompanyCode"),
        "projeto": por_uuid.get(e.get("ProjectUUID"), {}).get("projeto"),
        "projeto_desc": por_uuid.get(e.get("ProjectUUID"), {}).get("projeto_desc"),
        "cliente_id": por_uuid.get(e.get("ProjectUUID"), {}).get("cliente_id", ""),
        "cliente_nome": por_uuid.get(e.get("ProjectUUID"), {}).get("cliente_nome", ""),
        "profit_center": e.get("ProfitCenter"),
        "centro_custo": e.get("CostCenter"),
        "status": e.get("ProcessingStatus"),
        "inicio": data_sap(e.get("PlannedStartDate")),
        "fim": data_sap(e.get("PlannedEndDate")),
        "nivel": str(e.get("ProjectElement") or "").count("."),
        "wbs_internal_id": e.get("WBSElementInternalID"),
    } for e in els]).sort_values(["empresa", "pep"])

    resumo = (dfe.assign(com_cliente=dfe["cliente_id"].astype(bool))
                 .groupby("empresa")
                 .agg(peps=("pep", "count"),
                      com_cliente=("com_cliente", "sum"),
                      com_descricao=("descricao", lambda x: int(x.astype(str).str.strip().ne("").sum())))
                 .reset_index())
    resumo["%_com_cliente"] = (100 * resumo["com_cliente"] / resumo["peps"]).round(1)

    saida = Path(args.xlsx)
    with pd.ExcelWriter(saida, engine="openpyxl") as w:
        dfe.to_excel(w, sheet_name="PEPs", index=False)
        dfp.to_excel(w, sheet_name="Projetos", index=False)
        resumo.to_excel(w, sheet_name="Resumo", index=False)

    print(f"\n{len(dfe)} PEPs | {len(dfp)} projetos")
    print(f"PEPs com cliente : {int(dfe['cliente_id'].astype(bool).sum())} "
          f"({100*dfe['cliente_id'].astype(bool).mean():.1f}%)")
    print(f"PEPs sem cliente : {int((~dfe['cliente_id'].astype(bool)).sum())}")
    print(f"níveis: {dict(Counter(dfe['nivel']))}")
    print(f"\nArquivo: {saida}")


if __name__ == "__main__":
    main()

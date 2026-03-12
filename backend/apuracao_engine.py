"""
Engine de Apuração de Metas Q4 2025
Calcula bônus para AEs, Hunters e Diretores com base nas regras de negócio.
"""
import pandas as pd
import unicodedata
import re
import os
from functools import lru_cache

DIR = os.path.dirname(__file__)

Q4_PERIODOS = ["2025-10", "2025-11", "2025-12"]
Q4_QTDE = 1  # 1 quarter

# ─── Normalização de nomes ────────────────────────────────────────────────────

def norm(s: str) -> str:
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s)


# ─── Carregamento de dados ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_all():
    pessoas   = pd.read_csv(os.path.join(DIR, "premissas_pessoas.csv"),   encoding="utf-8-sig")
    pesos_m   = pd.read_csv(os.path.join(DIR, "premissas_pesos_meta.csv"),encoding="utf-8-sig")
    pesos_ws  = pd.read_csv(os.path.join(DIR, "premissas_pesos_ws.csv"),  encoding="utf-8-sig")
    triggers  = pd.read_csv(os.path.join(DIR, "premissas_triggers.csv"),  encoding="utf-8-sig")
    bgt_rec   = pd.read_csv(os.path.join(DIR, "budget_receita.csv"),      encoding="utf-8-sig")
    bgt_lb    = pd.read_csv(os.path.join(DIR, "budget_lb.csv"),           encoding="utf-8-sig")
    bgt_tcv   = pd.read_csv(os.path.join(DIR, "budget_tcv.csv"),          encoding="utf-8-sig")
    rac       = pd.read_csv(os.path.join(DIR, "rac_projetos.csv"),        encoding="utf-8-sig")
    margem    = pd.read_csv(os.path.join(DIR, "margem_projetos.csv"),     encoding="utf-8-sig")
    nexus     = pd.read_csv(os.path.join(DIR, "nexus_agg.csv"),           encoding="utf-8-sig")

    pessoas["nome_norm"] = pessoas["Nome"].apply(norm)
    bgt_rec["cliente_norm"] = bgt_rec["cliente"].apply(norm)
    bgt_lb["cliente_norm"]  = bgt_lb["cliente"].apply(norm)

    rac_q4   = rac[rac["periodo"].isin(Q4_PERIODOS)].copy()
    marg_q4  = margem[margem["periodo"].isin(Q4_PERIODOS)].copy()

    rac_q4["nome_norm"]  = rac_q4["nome_cliente"].apply(norm)
    marg_q4["nome_norm"] = marg_q4["nome_cliente"].apply(norm)

    # Lookup: cliente_norm → realizado receita e margem (Q4)
    rac_by_client  = rac_q4.groupby("nome_norm")["valor_liquido"].sum().to_dict()
    marg_by_client = marg_q4.groupby("nome_norm")["margem"].sum().to_dict()
    rec_by_client  = marg_q4.groupby("nome_norm")["receita"].sum().to_dict()

    return {
        "pessoas":  pessoas,
        "pesos_m":  pesos_m,
        "pesos_ws": pesos_ws,
        "triggers": triggers,
        "bgt_rec":  bgt_rec,
        "bgt_lb":   bgt_lb,
        "bgt_tcv":  bgt_tcv,
        "rac_by_client":  rac_by_client,
        "marg_by_client": marg_by_client,
        "rec_by_client":  rec_by_client,
        "nexus":    nexus,
    }


# ─── Helpers de trigger/atingimento ──────────────────────────────────────────

TRIGGER_REC_Q4 = 0.85   # Receita/TCV/MC
TRIGGER_MB_Q4  = 0.985  # MB%

WS_PESOS_Q4 = {
    "apps":       0.70,
    "cloud":      0.04,
    "cyber":      0.04,
    "dados":      0.08,
    "hyper":      0.08,
    "demais":     0.06,
}

WS_MAP = {
    # Normaliza nomes de WS do budget para chaves internas
    "apps":       "apps",
    "cloud":      "cloud",
    "cyber":      "cyber",
    "cloud/cyber":"cloud",
    "cloudcyber": "cloud",
    "dados":      "dados",
    "data":       "dados",
    "hyper":      "hyper",
    "demais":     "demais",
    "others":     "demais",
    "total":      "total",
}

def _norm_ws(ws: str) -> str:
    return WS_MAP.get(str(ws).strip().lower(), "demais")


def calc_atingimento(realizado: float, meta: float, trigger: float = 0.85) -> float:
    """Escala linear: 0 abaixo do trigger, 50%-100% entre trigger e meta, 100% acima."""
    if meta <= 0:
        return 0.0
    if realizado >= meta:
        return 1.0
    if realizado < meta * trigger:
        return 0.0
    return (realizado - meta * trigger) / (meta - meta * trigger) * 0.5 + 0.5


def _match_cliente(budget_norm: str, lookup: dict) -> float:
    """Tenta match exato ou prefixo entre budget_norm e chaves do lookup."""
    if budget_norm in lookup:
        return lookup[budget_norm]
    # Procura se budget_norm está contido no nome do cliente real ou vice-versa
    for k, v in lookup.items():
        if budget_norm in k or k.startswith(budget_norm[:8]):
            return v
    return 0.0


# ─── Cálculo AE ──────────────────────────────────────────────────────────────

def calc_bonus_ae(nome: str) -> dict:
    d = _load_all()
    pessoas = d["pessoas"]
    bgt_rec = d["bgt_rec"]
    bgt_lb  = d["bgt_lb"]

    nome_n = norm(nome)
    pessoa = pessoas[pessoas["nome_norm"] == nome_n]
    if pessoa.empty:
        # Try partial match
        pessoa = pessoas[pessoas["nome_norm"].str.contains(nome_n.split()[0])]
    if pessoa.empty:
        raise ValueError(f"Pessoa não encontrada: {nome}")
    pessoa = pessoa.iloc[0]

    salario   = float(pessoa["Sal_Q4"] or 0)
    posicao   = str(pessoa["Posicao"]).upper().strip()

    # Pesos de meta para AE/AE2/HUNTER (quarter)
    pesos_row = d["pesos_m"][
        (d["pesos_m"]["Periodo"] == "Quarter") &
        (d["pesos_m"]["Posicao"].str.upper() == posicao)
    ]
    if pesos_row.empty:
        pesos_row = d["pesos_m"][(d["pesos_m"]["Periodo"] == "Quarter") & (d["pesos_m"]["Posicao"] == "AE")]
    pesos_row = pesos_row.iloc[0]
    peso_rec = float(pesos_row["Receita"] or 0)
    peso_mb  = float(pesos_row["MB_pct"] or 0)

    # Budget Q4 por cliente/WS para este AE
    rec_ae  = bgt_rec[bgt_rec["ae_q4"].apply(norm) == nome_n].copy()
    lb_ae   = bgt_lb[bgt_lb["ae_q4"].apply(norm) == nome_n].copy()

    # Agrupa budget por WS
    rec_ae["ws_key"] = rec_ae["ws"].apply(_norm_ws)
    lb_ae["ws_key"]  = lb_ae["ws"].apply(_norm_ws)

    bgt_rec_ws = rec_ae.groupby("ws_key")["q4"].sum().to_dict()
    bgt_lb_ws  = lb_ae.groupby("ws_key")["q4"].sum().to_dict()
    bgt_rec_ws["total"] = rec_ae["q4"].sum()
    bgt_lb_ws["total"]  = lb_ae["q4"].sum()

    # Realizado por cliente, alocado por WS proporcionalmente ao budget
    # Para cada cliente no budget, busca realizado e aloca por WS via proporção
    realized_rec_ws: dict[str, float] = {}
    realized_lb_ws:  dict[str, float] = {}

    for ws_key in set(rec_ae["ws_key"]):
        realized_rec_ws[ws_key] = 0.0
    for ws_key in set(lb_ae["ws_key"]):
        realized_lb_ws[ws_key] = 0.0

    clientes_ae = rec_ae["cliente_norm"].dropna().unique()
    for cli_n in clientes_ae:
        real_rec = _match_cliente(cli_n, d["rac_by_client"])
        real_lb  = _match_cliente(cli_n, d["marg_by_client"])
        real_rec_base = _match_cliente(cli_n, d["rec_by_client"])  # receita do margem (para mb%)

        # Budget por WS para este cliente
        cli_rec_ws = rec_ae[rec_ae["cliente_norm"] == cli_n].groupby("ws_key")["q4"].sum()
        cli_rec_total = cli_rec_ws.sum()
        cli_lb_ws  = lb_ae[lb_ae["cliente_norm"] == cli_n].groupby("ws_key")["q4"].sum() if not lb_ae.empty else pd.Series(dtype=float)
        cli_lb_total = cli_lb_ws.sum() if len(cli_lb_ws) else 1

        for ws_k, bv in cli_rec_ws.items():
            prop = bv / cli_rec_total if cli_rec_total > 0 else 0
            realized_rec_ws[ws_k] = realized_rec_ws.get(ws_k, 0) + real_rec * prop

        for ws_k, bv in cli_lb_ws.items():
            prop = bv / cli_lb_total if cli_lb_total > 0 else 0
            realized_lb_ws[ws_k] = realized_lb_ws.get(ws_k, 0) + real_lb * prop

    realized_rec_ws["total"] = sum(v for k, v in realized_rec_ws.items() if k != "total")
    realized_lb_ws["total"]  = sum(v for k, v in realized_lb_ws.items() if k != "total")

    # Calcular MB% realizado vs budget
    bgt_rec_total  = bgt_rec_ws.get("total", 1) or 1
    bgt_lb_total   = bgt_lb_ws.get("total", 0)
    real_rec_total = realized_rec_ws.get("total", 0)
    real_lb_total  = realized_lb_ws.get("total", 0)

    bgt_mb_pct  = bgt_lb_total / bgt_rec_total if bgt_rec_total else 0
    real_mb_pct = real_lb_total / real_rec_total if real_rec_total else 0

    # ─ Atingimento por WS ─
    detalhe_ws = []
    bonus_total = 0.0
    all_ws_keys = set(list(bgt_rec_ws.keys()) + list(bgt_lb_ws.keys())) - {"total"}

    for ws_k in sorted(all_ws_keys):
        peso_ws = WS_PESOS_Q4.get(ws_k, 0.06)
        bgt_r   = bgt_rec_ws.get(ws_k, 0)
        real_r  = realized_rec_ws.get(ws_k, 0)
        bgt_lb_ = bgt_lb_ws.get(ws_k, 0)
        real_lb_ = realized_lb_ws.get(ws_k, 0)

        ating_rec = calc_atingimento(real_r, bgt_r, TRIGGER_REC_Q4)

        # MB% por WS (proporção)
        bgt_mb_pct_ws  = bgt_lb_ / bgt_r if bgt_r > 0 else 0
        real_mb_pct_ws = real_lb_ / real_r if real_r > 0 else 0

        # Trigger MB: só trava em Apps
        if ws_k == "apps":
            ating_mb = calc_atingimento(real_mb_pct_ws, bgt_mb_pct_ws, TRIGGER_MB_Q4)
            mb_gate  = 1.0 if ating_mb > 0 else 0.0
        else:
            # Demais: trigger sempre atingido, mas ainda calcula o atingimento proporcional
            ating_mb = calc_atingimento(real_mb_pct_ws, bgt_mb_pct_ws, TRIGGER_MB_Q4) if bgt_mb_pct_ws > 0 else 1.0
            mb_gate  = 1.0

        bonus_rec = Q4_QTDE * peso_ws * ating_rec * salario * peso_rec
        bonus_mb  = Q4_QTDE * peso_ws * ating_mb * mb_gate * salario * peso_mb

        bonus_total += bonus_rec + bonus_mb

        detalhe_ws.append({
            "ws":            ws_k,
            "peso_ws":       peso_ws,
            "budget_rec":    round(bgt_r, 2),
            "real_rec":      round(real_r, 2),
            "ating_rec":     round(ating_rec, 4),
            "budget_mb_pct": round(bgt_mb_pct_ws * 100, 2),
            "real_mb_pct":   round(real_mb_pct_ws * 100, 2),
            "ating_mb":      round(ating_mb, 4),
            "mb_gate":       mb_gate,
            "bonus_rec":     round(bonus_rec, 2),
            "bonus_mb":      round(bonus_mb, 2),
            "bonus_ws":      round(bonus_rec + bonus_mb, 2),
        })

    # Atingimento total (para display)
    ating_rec_total = calc_atingimento(real_rec_total, bgt_rec_total, TRIGGER_REC_Q4)
    ating_mb_total  = calc_atingimento(real_mb_pct, bgt_mb_pct, TRIGGER_MB_Q4)

    return {
        "nome":          pessoa["Nome"],
        "posicao":       posicao,
        "contrato":      str(pessoa.get("Contrato", "")),
        "salario_q4":    salario,
        "periodo":       "Q4 2025",
        "peso_receita":  peso_rec,
        "peso_mb":       peso_mb,
        "budget_rec_total":  round(bgt_rec_total, 2),
        "real_rec_total":    round(real_rec_total, 2),
        "ating_rec_total":   round(ating_rec_total, 4),
        "budget_mb_pct":     round(bgt_mb_pct * 100, 2),
        "real_mb_pct":       round(real_mb_pct * 100, 2),
        "ating_mb_total":    round(ating_mb_total, 4),
        "bonus_total":       round(bonus_total, 2),
        "detalhe_ws":        detalhe_ws,
    }


# ─── Cálculo Diretor ─────────────────────────────────────────────────────────

# Mapeamento manual Diretor → vertical no nexus/budget
DIRETOR_VERTICAL = {
    norm("Marcos"):       "Health",
    norm("Zanini"):       "Finance & Insurance",  # PREMISSAS col W = Finance
    norm("Artea"):        "Multisector",           # PREMISSAS col W = Multisector
    norm("Henrique"):     "Logistics",
    norm("Alexsandro"):   "Retail",
}

# Chave no budget_tcv para cada vertical de Diretor
DIRETOR_TCV_KEY = {
    "Health":              "Health",
    "Multisector":         "Multisector",
    "Finance & Insurance": "Wagner",   # budget_tcv chave para Finance
    "Logistics":           "Felipe",   # budget_tcv chave para Logistics
    "Retail":              "Retail",
}

# Verticais Nexus correspondentes para MC%
NEXUS_VERTICAL_MAP = {
    "Health":              ["Health"],
    "Multisector":         ["Multisector"],
    "Finance & Insurance": ["Finance & Insurance"],
    "Logistics":           ["Logistics"],
    "Retail":              ["Retail"],
}

# Mapeamento vertical → bs no budget_receita/lb
VERTICAL_BS_MAP = {
    "Health":              "Health",
    "Multisector":         "Multisector",
    "Finance & Insurance": "Finance",
    "Logistics":           "Logistics",
    "Retail":              "Retail",
}

NEXUS_VERTICAL_MAP = {
    "Finance & Insurance": ["Finance & Insurance"],
    "Health":              ["Health"],
    "Logistics":           ["Logistics"],
    "Multisector":         ["Multisector"],
    "Retail":              ["Retail"],
}


def calc_bonus_diretor(nome: str) -> dict:
    d = _load_all()
    pessoas = d["pessoas"]
    bgt_tcv = d["bgt_tcv"]
    nexus   = d["nexus"]

    nome_n = norm(nome)
    pessoa = pessoas[pessoas["nome_norm"] == nome_n]
    if pessoa.empty:
        pessoa = pessoas[pessoas["nome_norm"].str.contains(nome_n.split()[0])]
    if pessoa.empty:
        raise ValueError(f"Diretor não encontrado: {nome}")
    pessoa = pessoa.iloc[0]

    salario   = float(pessoa["Sal_Q4"] or 0)
    posicao   = "DIRETOR"

    pesos_row = d["pesos_m"][
        (d["pesos_m"]["Periodo"] == "Quarter") &
        (d["pesos_m"]["Posicao"].str.upper() == "DIRETOR")
    ].iloc[0]
    peso_tcv = float(pesos_row["TCV"] or 0)
    peso_rec = float(pesos_row["Receita"] or 0)
    peso_mc  = float(pesos_row["MC_pct"] or 0)

    # Vertical do diretor
    vertical = DIRETOR_VERTICAL.get(nome_n, None)

    # ─ TCV ─
    # budget_tcv tem AE como chave (Eduardo, Mirella, etc.)
    # Para Diretores, usamos a coluna que corresponde à sua vertical
    # O budget_tcv.csv tem: ae (nome curto), descricao, q1, q2, q3, q4
    # Filtra por ae = nome do diretor (nome curto)
    nome_curto = nome.split()[0]
    tcv_key = DIRETOR_TCV_KEY.get(vertical, nome_curto) if vertical else nome_curto
    tcv_rows = bgt_tcv[bgt_tcv["ae"].apply(lambda x: str(x).strip() if pd.notna(x) else "") == tcv_key]
    bgt_tcv_q4 = float(tcv_rows[tcv_rows["descricao"].apply(lambda x: "receita" in str(x).lower())]["q4"].sum())
    # TCV realizado: sem fonte Salesforce, usar RAC como proxy
    rac_by_client = d["rac_by_client"]
    real_tcv_q4 = 0.0  # Placeholder – requer base Salesforce

    ating_tcv = calc_atingimento(real_tcv_q4, bgt_tcv_q4, TRIGGER_REC_Q4)

    # ─ Receita ─
    bgt_rec = d["bgt_rec"]
    # Budget receita da vertical do diretor (bs = vertical)
    if vertical:
        bs_key = VERTICAL_BS_MAP.get(vertical, vertical)
        rec_dir = bgt_rec[bgt_rec["bs"].str.lower() == bs_key.lower()]
    else:
        bs_key = ""
        rec_dir = pd.DataFrame()

    bgt_rec_q4  = float(rec_dir["q4"].sum()) if not rec_dir.empty else 0.0
    # Realizado receita: soma de RAC dos clientes da vertical
    real_rec_q4 = 0.0
    if not rec_dir.empty:
        for cli_n in rec_dir["cliente_norm"].dropna().unique():
            real_rec_q4 += _match_cliente(cli_n, rac_by_client)

    ating_rec = calc_atingimento(real_rec_q4, bgt_rec_q4, TRIGGER_REC_Q4)

    # ─ MC% ─
    # Nexus: Margem de Contribuição = Gross Revenue - Direct costs (Payroll + Third-party + Other)
    nexus_q4 = nexus[nexus["Periodo"].isin(Q4_PERIODOS)]
    if vertical and vertical in NEXUS_VERTICAL_MAP:
        nexus_verticals = NEXUS_VERTICAL_MAP[vertical]
        nq4 = nexus_q4[nexus_q4["[Vertical]"].isin(nexus_verticals)]
    else:
        nq4 = pd.DataFrame()

    if not nq4.empty:
        gross_rev = nq4[nq4["Agrupador"] == "Gross revenue"]["[Valor]"].sum()
        direct_costs = nq4[nq4["Agrupador"].isin([
            "Payroll costs", "Third-party costs", "Other costs"
        ])]["[Valor]"].sum()
        real_mc_pct = (gross_rev + direct_costs) / gross_rev if gross_rev else 0.0
    else:
        gross_rev = 0.0
        real_mc_pct = 0.0

    # Budget MC%: bgt_lb / bgt_rec para a vertical
    bgt_lb  = d["bgt_lb"]
    lb_dir  = bgt_lb[bgt_lb["bs"].str.lower() == bs_key.lower()] if (vertical and bs_key) else pd.DataFrame()
    bgt_lb_q4  = float(lb_dir["q4"].sum()) if not lb_dir.empty else 0.0
    bgt_mc_pct = bgt_lb_q4 / bgt_rec_q4 if bgt_rec_q4 else 0.0

    # Trigger MC%: -1.5pp para Q4
    trigger_mc_pct_val = max(0, bgt_mc_pct - 0.015)
    mc_gate = 1.0 if real_mc_pct >= trigger_mc_pct_val else 0.0

    ating_mc = calc_atingimento(real_mc_pct, bgt_mc_pct, 0.0) if bgt_mc_pct > 0 else 0.0

    # ─ Bônus ─
    if mc_gate == 0:
        # Gatilho mestre: sem MC, sem apuração das demais
        bonus_tcv = 0.0
        bonus_rec = 0.0
        bonus_mc  = 0.0
    else:
        bonus_tcv = Q4_QTDE * 1.0 * ating_tcv * salario * peso_tcv
        bonus_rec = Q4_QTDE * 1.0 * ating_rec * salario * peso_rec
        bonus_mc  = Q4_QTDE * 1.0 * ating_mc  * salario * peso_mc

    bonus_total = bonus_tcv + bonus_rec + bonus_mc

    return {
        "nome":          pessoa["Nome"],
        "posicao":       posicao,
        "contrato":      str(pessoa.get("Contrato", "")),
        "salario_q4":    salario,
        "vertical":      vertical or "N/D",
        "periodo":       "Q4 2025",
        "mc_gate":       mc_gate,
        "peso_tcv":      peso_tcv,
        "peso_receita":  peso_rec,
        "peso_mc":       peso_mc,
        "budget_tcv_q4":     round(bgt_tcv_q4, 2),
        "real_tcv_q4":       round(real_tcv_q4, 2),
        "ating_tcv":         round(ating_tcv, 4),
        "budget_rec_q4":     round(bgt_rec_q4, 2),
        "real_rec_q4":       round(real_rec_q4, 2),
        "ating_rec":         round(ating_rec, 4),
        "budget_mc_pct":     round(bgt_mc_pct * 100, 2),
        "real_mc_pct":       round(real_mc_pct * 100, 2),
        "ating_mc":          round(ating_mc, 4),
        "bonus_tcv":         round(bonus_tcv, 2),
        "bonus_rec":         round(bonus_rec, 2),
        "bonus_mc":          round(bonus_mc, 2),
        "bonus_total":       round(bonus_total, 2),
    }


# ─── Visão Master ────────────────────────────────────────────────────────────

def get_visao_master() -> list[dict]:
    d = _load_all()
    pessoas = d["pessoas"]
    resultados = []

    for _, p in pessoas.iterrows():
        nome = p["Nome"]
        pos  = str(p["Posicao"]).upper().strip()
        sal  = float(p["Sal_Q4"] or 0)
        if sal == 0 or pd.isna(sal):
            continue
        try:
            if pos == "DIRETOR":
                res = calc_bonus_diretor(nome)
                resultados.append({
                    "nome":     res["nome"],
                    "posicao":  res["posicao"],
                    "contrato": res["contrato"],
                    "vertical": res.get("vertical", ""),
                    "salario":  res["salario_q4"],
                    "bonus":    res["bonus_total"],
                    "ating_principal": res["ating_mc"],
                    "mc_gate":  res["mc_gate"],
                    "tipo_calc": "Diretor",
                })
            elif pos in ("AE", "AE2", "HUNTER", "ESTRATEGISTAS", "CS"):
                res = calc_bonus_ae(nome)
                resultados.append({
                    "nome":     res["nome"],
                    "posicao":  res["posicao"],
                    "contrato": res["contrato"],
                    "vertical": "",
                    "salario":  res["salario_q4"],
                    "bonus":    res["bonus_total"],
                    "ating_principal": res["ating_rec_total"],
                    "mc_gate":  None,
                    "tipo_calc": "Comercial",
                })
        except Exception as e:
            resultados.append({
                "nome":     nome,
                "posicao":  pos,
                "contrato": str(p.get("Contrato", "")),
                "vertical": "",
                "salario":  sal,
                "bonus":    0.0,
                "ating_principal": 0.0,
                "mc_gate":  None,
                "tipo_calc": "Erro",
                "erro":     str(e),
            })
    return resultados


# ─── CLI rápido para testar ──────────────────────────────────────────────────

if __name__ == "__main__":
    import json, sys
    nome = sys.argv[1] if len(sys.argv) > 1 else "RICARDO SALLES HENRIQUE"
    pos  = sys.argv[2] if len(sys.argv) > 2 else "AE"

    if pos.upper() == "DIRETOR":
        result = calc_bonus_diretor(nome)
    elif nome.upper() == "MASTER":
        result = get_visao_master()
    else:
        result = calc_bonus_ae(nome)

    print(json.dumps(result, ensure_ascii=False, indent=2))

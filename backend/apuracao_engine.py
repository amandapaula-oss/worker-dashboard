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
    lb_trigger_df = pd.read_csv(os.path.join(DIR, "premissas_lb_trigger.csv"), encoding="utf-8-sig")
    lb_trigger_df["nome_norm"] = lb_trigger_df["nome"].apply(norm)
    # dict: nome_norm → {meta_lb, trigger_lb}
    lb_trigger_map = {
        row["nome_norm"]: {"meta_lb": float(row["meta_lb"] or 0), "trigger_lb": float(row["trigger_lb"] or 0)}
        for _, row in lb_trigger_df.iterrows()
    }

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

    # Add aliases: nome_cliente → nome_base (e.g. "C6 BANK" → "BANCO C6 S.A.")
    # so budget entries keyed by friendly name can find the SAP name in the lookup
    clientes_path = os.path.join(DIR, "clientes.csv")
    if os.path.exists(clientes_path):
        try:
            clientes_df = pd.read_csv(clientes_path, encoding="utf-8-sig")
            if "nome_base" in clientes_df.columns:
                for _, row in clientes_df.iterrows():
                    nc = str(row.get("nome_cliente", "") or "").strip()
                    nb = str(row.get("nome_base", "") or "").strip()
                    if nc and nb:
                        nc_n, nb_n = norm(nc), norm(nb)
                        for lookup in [rac_by_client, marg_by_client, rec_by_client]:
                            if nb_n in lookup and nc_n not in lookup:
                                lookup[nc_n] = lookup[nb_n]
        except Exception:
            pass

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
        "nexus":       nexus,
        "lb_trigger":  lb_trigger_map,
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


MB_TRIGGER_DELTA = 0.015  # 1.5 pontos percentuais abaixo da meta


def calc_atingimento_mb(real_pct: float, meta_pct: float, delta: float = MB_TRIGGER_DELTA) -> float:
    """Atingimento de MB%: trigger é delta pp abaixo da meta (ex: meta 40% → trigger 38.5%)."""
    trigger_abs = meta_pct - delta
    if meta_pct <= 0:
        return 0.0
    if real_pct >= meta_pct:
        return 1.0
    if real_pct < trigger_abs:
        return 0.0
    return (real_pct - trigger_abs) / (meta_pct - trigger_abs) * 0.5 + 0.5


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
        pessoa = pessoas[pessoas["nome_norm"].str.contains(nome_n.split()[0])]
    if pessoa.empty:
        raise ValueError(f"Pessoa não encontrada: {nome}")
    pessoa = pessoa.iloc[0]
    # Usa o nome completo normalizado da pessoa para todos os filtros
    pessoa_nome_n = norm(str(pessoa["Nome"]))

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

    # Budget Q4 por cliente/WS para este AE (usa nome completo)
    rec_ae  = bgt_rec[bgt_rec["ae_q4"].apply(norm) == pessoa_nome_n].copy()
    lb_ae   = bgt_lb[bgt_lb["ae_q4"].apply(norm) == pessoa_nome_n].copy()

    # Filtra pelo BS predominante (evita misturar verticais diferentes)
    if not rec_ae.empty and "bs" in rec_ae.columns:
        primary_bs = rec_ae["bs"].value_counts().idxmax()
        rec_ae = rec_ae[rec_ae["bs"] == primary_bs].copy()
        if not lb_ae.empty and "bs" in lb_ae.columns:
            lb_ae = lb_ae[lb_ae["bs"] == primary_bs].copy()

    # Agrupa budget por WS
    rec_ae["ws_key"] = rec_ae["ws"].apply(_norm_ws)
    lb_ae["ws_key"]  = lb_ae["ws"].apply(_norm_ws)

    bgt_rec_ws = rec_ae.groupby("ws_key")["q4"].sum().to_dict()
    bgt_lb_ws  = lb_ae.groupby("ws_key")["q4"].sum().to_dict()
    bgt_rec_ws["total"] = rec_ae["q4"].sum()
    bgt_lb_ws["total"]  = lb_ae["q4"].sum()

    # Pesos por WS derivados do budget da pessoa (em vez de global fixo)
    total_bgt_for_weights = sum(v for k, v in bgt_rec_ws.items() if k != "total")
    if total_bgt_for_weights > 0:
        person_ws_weights = {
            k: bgt_rec_ws.get(k, 0.0) / total_bgt_for_weights
            for k in WS_PESOS_Q4
        }
    else:
        person_ws_weights = dict(WS_PESOS_Q4)

    # Realizado por cliente, alocado por WS proporcionalmente ao budget
    realized_rec_ws: dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_lb_ws:  dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}

    clientes_ae = rec_ae["cliente_norm"].dropna().unique()
    clientes_detalhe = []
    cli_contrib: dict[str, list] = {}  # {ws_k: [{cliente, budget_rec, real_rec}]}

    for cli_n in clientes_ae:
        real_rec = _match_cliente(cli_n, d["rac_by_client"])
        real_lb  = _match_cliente(cli_n, d["marg_by_client"])
        cli_rows = rec_ae[rec_ae["cliente_norm"] == cli_n]
        cli_bgt  = float(cli_rows["q4"].sum())
        cli_display = cli_rows["cliente"].iloc[0] if not cli_rows.empty else cli_n
        margem_pct = real_lb / real_rec if real_rec > 0 else None
        clientes_detalhe.append({
            "cliente":    cli_display,
            "budget_rec": round(cli_bgt, 2),
            "real_rec":   round(real_rec, 2),
            "diferenca":  round(real_rec - cli_bgt, 2),
            "real_lb":    round(real_lb, 2),
            "margem_pct": round(margem_pct * 100, 1) if margem_pct is not None else None,
        })

        cli_rec_ws    = cli_rows.groupby("ws_key")["q4"].sum()
        cli_rec_total = float(cli_rec_ws.sum())
        cli_lb_ws     = (
            lb_ae[lb_ae["cliente_norm"] == cli_n].groupby("ws_key")["q4"].sum()
            if not lb_ae.empty else pd.Series(dtype=float)
        )
        cli_lb_total = float(cli_lb_ws.sum()) if len(cli_lb_ws) else 1.0

        for ws_k, bv in cli_rec_ws.items():
            prop = float(bv) / cli_rec_total if cli_rec_total > 0 else 0.0
            cli_real_ws = real_rec * prop
            realized_rec_ws[ws_k] = realized_rec_ws.get(ws_k, 0.0) + cli_real_ws
            cli_contrib.setdefault(ws_k, []).append({
                "cliente":    cli_display,
                "budget_rec": round(float(bv), 2),
                "real_rec":   round(cli_real_ws, 2),
            })

        for ws_k, bv in cli_lb_ws.items():
            prop = float(bv) / cli_lb_total if cli_lb_total > 0 else 0.0
            realized_lb_ws[ws_k] = realized_lb_ws.get(ws_k, 0.0) + real_lb * prop

    realized_rec_ws["total"] = sum(v for k, v in realized_rec_ws.items() if k != "total")
    realized_lb_ws["total"]  = sum(v for k, v in realized_lb_ws.items() if k != "total")

    # Calcular MB% realizado vs budget
    bgt_rec_total  = bgt_rec_ws.get("total", 1) or 1
    bgt_lb_total   = bgt_lb_ws.get("total", 0)
    real_rec_total = realized_rec_ws.get("total", 0)
    real_lb_total  = realized_lb_ws.get("total", 0)

    bgt_mb_pct  = bgt_lb_total / bgt_rec_total if bgt_rec_total else 0
    real_mb_pct = real_lb_total / real_rec_total if real_rec_total else 0

    # ─ Atingimento por WS (todas as 6 WS, mesmo sem budget) ─
    detalhe_ws = []
    bonus_total = 0.0

    for ws_k in WS_PESOS_Q4:  # sempre todas as 6 WS
        peso_ws  = person_ws_weights.get(ws_k, 0.0)
        bgt_r    = bgt_rec_ws.get(ws_k, 0.0)
        real_r   = realized_rec_ws.get(ws_k, 0.0)
        bgt_lb_  = bgt_lb_ws.get(ws_k, 0.0)
        real_lb_ = realized_lb_ws.get(ws_k, 0.0)

        ating_rec = calc_atingimento(real_r, bgt_r, TRIGGER_REC_Q4)

        # MB% por WS
        bgt_mb_pct_ws  = bgt_lb_ / bgt_r if bgt_r > 0 else 0.0
        real_mb_pct_ws = real_lb_ / real_r if real_r > 0 else 0.0

        # Trigger MB: meta - 1.5pp (absoluto)
        trigger_mb_value = round(max(0.0, bgt_mb_pct_ws * 100 - 1.5), 2)

        # Gate MB: só trava em Apps
        if ws_k == "apps":
            ating_mb = calc_atingimento_mb(real_mb_pct_ws, bgt_mb_pct_ws)
            mb_gate  = 1.0 if ating_mb > 0 else 0.0
        else:
            ating_mb = calc_atingimento_mb(real_mb_pct_ws, bgt_mb_pct_ws) if bgt_mb_pct_ws > 0 else 1.0
            mb_gate  = 1.0

        bonus_rec = Q4_QTDE * peso_ws * ating_rec * salario * peso_rec
        bonus_mb  = Q4_QTDE * peso_ws * ating_mb * mb_gate * salario * peso_mb

        bonus_total += bonus_rec + bonus_mb

        trigger_amount = round(bgt_r * TRIGGER_REC_Q4, 2)
        detalhe_ws.append({
            "ws":                  ws_k,
            "peso_ws":             round(peso_ws, 4),
            # Receita
            "budget_rec":          round(bgt_r, 2),
            "trigger_rec_amount":  trigger_amount,
            "real_rec":            round(real_r, 2),
            "receita_faltante":    round(max(0.0, trigger_amount - real_r), 2),
            "ating_rec":           round(ating_rec, 4),
            # MB%
            "budget_mb_pct":       round(bgt_mb_pct_ws * 100, 2),
            "trigger_mb_pct":      trigger_mb_value,
            "real_mb_pct":         round(real_mb_pct_ws * 100, 2),
            "mb_faltante":         round(max(0.0, trigger_mb_value - real_mb_pct_ws * 100), 2),
            "ating_mb":            round(ating_mb, 4),
            "mb_gate":             mb_gate,
            "aplica_gate_mb":      ws_k == "apps",
            # Bônus
            "bonus_rec":           round(bonus_rec, 2),
            "bonus_mb":            round(bonus_mb, 2),
            "bonus_ws":            round(bonus_rec + bonus_mb, 2),
            # Clientes nesta WS
            "clientes_ws":         cli_contrib.get(ws_k, []),
        })

    # Atingimento total
    ating_rec_total = calc_atingimento(real_rec_total, bgt_rec_total, TRIGGER_REC_Q4)
    ating_mb_total  = calc_atingimento_mb(real_mb_pct, bgt_mb_pct)

    # Gatilho Mestre: Lucro Bruto R$ (absoluto), lido da planilha de apuração
    lb_trigger_info = d["lb_trigger"].get(pessoa_nome_n, {})
    if not lb_trigger_info:  # fallback: busca por primeiro token
        primeiro = pessoa_nome_n.split()[0]
        lb_trigger_info = next(
            (v for k, v in d["lb_trigger"].items() if k.startswith(primeiro)), {}
        )
    meta_lb_q4    = lb_trigger_info.get("meta_lb", 0.0)
    trigger_lb_q4 = lb_trigger_info.get("trigger_lb", 0.0)
    lb_gate = 1 if (trigger_lb_q4 <= 0 or real_lb_total >= trigger_lb_q4) else 0

    trigger_mb_pct_total = round(max(0.0, bgt_mb_pct * 100 - 1.5), 2)

    clientes_detalhe.sort(key=lambda x: x["budget_rec"], reverse=True)
    return {
        "nome":          pessoa["Nome"],
        "posicao":       posicao,
        "contrato":      str(pessoa.get("Contrato", "")),
        "salario_q4":    salario,
        "periodo":       "Q4 2025",
        "peso_receita":  peso_rec,
        "peso_mb":       peso_mb,
        "trigger_rec":   TRIGGER_REC_Q4,
        "trigger_mb_pct_total": trigger_mb_pct_total,
        "lb_gate":       lb_gate,
        "meta_lb_q4":    round(meta_lb_q4, 2),
        "trigger_lb_q4": round(trigger_lb_q4, 2),
        "real_lb_total": round(real_lb_total, 2),
        "budget_rec_total":  round(bgt_rec_total, 2),
        "real_rec_total":    round(real_rec_total, 2),
        "ating_rec_total":   round(ating_rec_total, 4),
        "budget_mb_pct":     round(bgt_mb_pct * 100, 2),
        "real_mb_pct":       round(real_mb_pct * 100, 2),
        "ating_mb_total":    round(ating_mb_total, 4),
        "bonus_total":       round(bonus_total, 2),
        "detalhe_ws":        detalhe_ws,
        "clientes_detalhe":  clientes_detalhe,
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
        "trigger_mc_pct":    round(trigger_mc_pct_val * 100, 2),
        "real_mc_pct":       round(real_mc_pct * 100, 2),
        "ating_mc":          round(ating_mc, 4),
        "bonus_tcv":         round(bonus_tcv, 2),
        "bonus_rec":         round(bonus_rec, 2),
        "bonus_mc":          round(bonus_mc, 2),
        "bonus_total":       round(bonus_total, 2),
    }


# ─── AE → Vertical lookup via clientes.csv ────────────────────────────────────

def _ae_vertical_lookup() -> dict:
    """
    Builds {norm(ae_name): 'vertical1/vertical2'} from clientes.csv.
    Also indexes by first word (nickname) for partial matching.
    """
    path = os.path.join(DIR, "clientes.csv")
    if not os.path.exists(path):
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
        lookup: dict[str, set] = {}
        for _, row in df.iterrows():
            ae  = str(row.get("ae", "")).strip()
            bu  = str(row.get("bu", "")).strip()
            if not ae or not bu:
                continue
            key_full  = norm(ae)
            key_first = norm(ae).split()[0]  # first name / nickname
            for key in (key_full, key_first):
                lookup.setdefault(key, set()).add(bu)
        return {k: "/".join(sorted(v)) for k, v in lookup.items()}
    except Exception:
        return {}

def _resolve_vertical_for_ae(nome: str, lookup: dict) -> str:
    n = norm(nome)
    # try full name
    if n in lookup:
        return lookup[n]
    # try first word
    first = n.split()[0]
    if first in lookup:
        return lookup[first]
    # try if any key is contained in nome or vice-versa
    for key, val in lookup.items():
        if key in n or n in key:
            return val
    return ""


# ─── Visão Master ────────────────────────────────────────────────────────────

def get_visao_master() -> list[dict]:
    d = _load_all()
    pessoas = d["pessoas"]
    resultados = []
    ae_vert = _ae_vertical_lookup()

    for _, p in pessoas.iterrows():
        nome = p["Nome"]
        pos  = str(p["Posicao"]).upper().strip()
        sal  = float(p["Sal_Q4"] or 0)
        if sal == 0 or pd.isna(sal):
            continue
        try:
            if pos == "DIRETOR":
                res = calc_bonus_diretor(nome)
                bgt_r = res["budget_rec_q4"] or 1
                bgt_t = res["budget_tcv_q4"] or 1
                bgt_m = res["budget_mc_pct"] or 1
                resultados.append({
                    "nome":     res["nome"],
                    "posicao":  res["posicao"],
                    "contrato": res["contrato"],
                    "vertical": res.get("vertical", ""),
                    "salario":  res["salario_q4"],
                    "bonus":    res["bonus_total"],
                    "ating_principal": res["ating_mc"],
                    "ating_rec": res["ating_rec"],
                    "ating_mb":  None,
                    "ating_tcv": res["ating_tcv"],
                    "ating_mc":  res["ating_mc"],
                    "pct_rec":  round(res["real_rec_q4"] / bgt_r, 4),
                    "pct_mb":   None,
                    "pct_tcv":  round(res["real_tcv_q4"] / bgt_t, 4) if bgt_t else 0,
                    "pct_mc":   round(res["real_mc_pct"] / bgt_m, 4) if bgt_m else 0,
                    "mc_gate":   res["mc_gate"],
                    "gate_ok":   res["mc_gate"] == 1.0,
                    "tipo_calc": "Diretor",
                })
            elif pos in ("AE", "AE2", "HUNTER", "ESTRATEGISTAS", "CS"):
                res = calc_bonus_ae(nome)
                bgt_r = res["budget_rec_total"] or 1
                bgt_m = res["budget_mb_pct"] or 1
                resultados.append({
                    "nome":     res["nome"],
                    "posicao":  res["posicao"],
                    "contrato": res["contrato"],
                    "vertical": _resolve_vertical_for_ae(nome, ae_vert),
                    "salario":  res["salario_q4"],
                    "bonus":    res["bonus_total"],
                    "ating_principal": res["ating_rec_total"],
                    "ating_rec":  res["ating_rec_total"],
                    "ating_mb":   res["ating_mb_total"],
                    "ating_tcv":  None,
                    "ating_mc":   None,
                    "pct_rec":  round(res["real_rec_total"] / bgt_r, 4),
                    "pct_mb":   round(res["real_mb_pct"] / bgt_m, 4) if bgt_m else 0,
                    "pct_tcv":  None,
                    "pct_mc":   None,
                    "mc_gate":    None,
                    "gate_ok":    bool(res.get("lb_gate", 1)),
                    "tipo_calc":  "Comercial",
                })
        except Exception as e:
            resultados.append({
                "nome":     nome,
                "posicao":  pos,
                "contrato": str(p.get("Contrato", "")),
                "vertical": _resolve_vertical_for_ae(nome, ae_vert),
                "salario":  sal,
                "bonus":    0.0,
                "ating_principal": 0.0,
                "ating_rec":  0.0,
                "ating_mb":   None,
                "ating_tcv":  None,
                "ating_mc":   None,
                "pct_rec":  None,
                "pct_mb":   None,
                "pct_tcv":  None,
                "pct_mc":   None,
                "mc_gate":    None,
                "gate_ok":    False,
                "tipo_calc":  "Erro",
                "erro":       str(e),
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

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

Q3_PERIODOS = ["2025-07", "2025-08", "2025-09"]
Q3_QTDE = 1  # 1 quarter
TRIGGER_REC_Q3    = 0.90   # trigger receita/TCV Q3
MB_TRIGGER_DELTA_Q3 = 0.010  # 1.0pp abaixo da meta MB para Q3

# ─── Normalização de nomes ────────────────────────────────────────────────────

def norm(s: str) -> str:
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s)


# ─── Carregamento de dados ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_all():
    _param    = pd.ExcelFile(os.path.join(DIR, "parametros.xlsx"))
    pessoas   = _param.parse("pessoas")
    pesos_m   = _param.parse("pesos_meta")
    pesos_ws  = _param.parse("pesos_ws")
    triggers  = _param.parse("triggers")
    _budget   = _param.parse("budget")
    bgt_rec   = _budget[_budget["tipo"] == "Receita"].copy()
    bgt_lb    = _budget[_budget["tipo"] == "Margem"].copy()
    bgt_tcv   = _param.parse("budget_tcv")
    _real_df  = _param.parse("realizados_manual")
    tcv_real_map    = dict(zip(_real_df[_real_df["tipo"] == "TCV_Q4"]["ae_ou_vertical"],
                               _real_df[_real_df["tipo"] == "TCV_Q4"]["receita"].astype(float)))
    tcv_real_q3_map = dict(zip(_real_df[_real_df["tipo"] == "TCV_Q3"]["ae_ou_vertical"],
                               _real_df[_real_df["tipo"] == "TCV_Q3"]["receita"].astype(float)))
    pesos_ws_df = _param.parse("pesos_ws_pessoa")
    pesos_ws_df["nome_norm"] = pesos_ws_df["nome"].apply(norm)
    # dict: nome_norm → {ws_key: peso}  (Q4)
    pesos_ws_pessoa = {
        row["nome_norm"]: {
            ws_k: float(row.get(ws_k, 0.0) or 0.0)
            for ws_k in WS_PESOS_Q4
        }
        for _, row in pesos_ws_df.iterrows()
    }
    # dict: nome_norm → {ws_key: peso}  (Q3 — usa colunas _q3 se existirem, senão herda Q4)
    def _ws_peso_q3(row, ws_k):
        v = row.get(f"{ws_k}_q3")
        if v is not None and v == v and str(v).strip() != "":  # not NaN, not empty
            return float(v)
        return float(row.get(ws_k, 0.0) or 0.0)
    pesos_ws_pessoa_q3 = {
        row["nome_norm"]: {ws_k: _ws_peso_q3(row, ws_k) for ws_k in WS_PESOS_Q4}
        for _, row in pesos_ws_df.iterrows()
    }
    # operacional.xlsx/projetos consolida rac_projetos + margem_projetos
    _oper     = pd.ExcelFile(os.path.join(DIR, "operacional.xlsx"))
    _proj     = _oper.parse("projetos")
    # monta rac (explodindo tipos) e margem a partir do arquivo unificado
    _proj_rac  = _proj[_proj["tipos"].notna() & (_proj["tipos"] != "")].copy()
    _proj_rac  = _proj_rac.assign(tipo=_proj_rac["tipos"].str.split(",")).explode("tipo")
    _proj_rac["tipo"] = _proj_rac["tipo"].str.strip()
    _proj_rac  = _proj_rac.rename(columns={"receita": "valor_liquido"})
    rac        = _proj_rac
    margem     = _proj.rename(columns={"horas": "horas_total"})
    nexus     = _oper.parse("nexus_agg")
    # Pessoas — para custos reais de projetos Apps e para despesas (Opção C)
    _pess_xl  = pd.ExcelFile(os.path.join(DIR, "pessoas.xlsx"))
    margem_pess = _oper.parse("margem_pessoas").astype({"cpf": str})
    class_pess  = _pess_xl.parse("relacao_pessoas").astype({"CPF / Worker ID": str}).rename(columns={"CPF / Worker ID": "cpf_brcpf"})
    lb_trigger_df = _param.parse("lb_trigger")
    lb_trigger_df["nome_norm"] = lb_trigger_df["nome"].apply(norm)
    # dict: nome_norm → {meta_lb, trigger_lb}
    lb_trigger_map = {
        row["nome_norm"]: {"meta_lb": float(row["meta_lb"] or 0), "trigger_lb": float(row["trigger_lb"] or 0)}
        for _, row in lb_trigger_df.iterrows()
    }
    mc_metas_dir: dict = {}
    _mc_df = _param.parse("mc_dir")
    for _, _row in _mc_df.iterrows():
        mc_metas_dir[norm(str(_row["nome"]))] = float(_row["meta_mc_abs"])

    pessoas["nome_norm"] = pessoas["Nome"].apply(norm)
    bgt_rec["cliente_norm"] = bgt_rec["cliente"].apply(norm)
    bgt_lb["cliente_norm"]  = bgt_lb["cliente"].apply(norm)

    rac_q4   = rac[rac["periodo"].isin(Q4_PERIODOS)].copy()
    marg_q4  = margem[margem["periodo"].isin(Q4_PERIODOS)].copy()

    # Substitui receita SAP por RAC onde há match (periodo+pep_base+nome_cliente)
    # Espelha exatamente a lógica de get_margem_proj() em main.py
    if "pep" in rac_q4.columns:
        _rac_receita = (
            rac_q4.assign(pep_base=rac_q4["pep"].astype(str).str.split(".").str[0].str.strip())
            .groupby(["periodo", "pep_base", "nome_cliente"])["valor_liquido"].sum()
            .reset_index().rename(columns={"valor_liquido": "receita_rac", "pep_base": "_pep_rac"})
        )
        marg_q4["_pep_base_tmp"] = marg_q4["pep"].astype(str).str.split(".").str[0].str.strip()
        marg_q4 = marg_q4.merge(
            _rac_receita,
            left_on=["periodo", "_pep_base_tmp", "nome_cliente"],
            right_on=["periodo", "_pep_rac", "nome_cliente"],
            how="left"
        )
        marg_q4["receita"] = marg_q4["receita_rac"].where(
            marg_q4["receita_rac"].notna(), marg_q4["receita"]
        )
        marg_q4 = marg_q4.drop(columns=["receita_rac", "_pep_rac", "_pep_base_tmp"], errors="ignore")

    # Aplica benchmark de MB% por WS — mesma lógica de main.py get_margem_proj().
    # Para categorias com benchmark definido (Demais/Cloud/Dados/Hyper), substitui
    # custo_rateado e margem pelo benchmark em vez de usar os dados brutos do SAP
    # (que frequentemente chegam com custo_rateado=0, gerando MB%=100%).
    if "categoria_bu" in marg_q4.columns:
        _ws_k_col = marg_q4["categoria_bu"].apply(
            lambda x: _norm_ws(str(x)) if pd.notna(x) and str(x).strip() else "demais"
        )
        for _ws_k, _bench in WS_MB_BENCHMARK_Q4.items():
            _mask = (_ws_k_col == _ws_k) & marg_q4["receita"].notna() & (marg_q4["receita"] != 0)
            marg_q4.loc[_mask, "margem"]        = marg_q4.loc[_mask, "receita"] * _bench
            marg_q4.loc[_mask, "custo_rateado"] = marg_q4.loc[_mask, "receita"] * -( 1 - _bench)
            marg_q4.loc[_mask, "margem_pct"]    = _bench
        # Apps: quando custo_rateado=0, usa custo real de margem_pessoas (por PEP+período)
        # Fallback: benchmark 35% para PEPs sem dados de pessoas
        if not margem_pess.empty and not class_pess.empty:
            _cpf_custo = set(class_pess[class_pess["classificacao"] == "custo"]["cpf_brcpf"].str.strip())
            _mp_custo = margem_pess[margem_pess["cpf"].str.strip().isin(_cpf_custo)].copy()
            _mp_custo["pep_base"] = _mp_custo["pep"].astype(str).str.split(".").str[0]
            _pep_period_custo = (
                _mp_custo.groupby(["pep_base", "periodo"])["custo_rateado"].sum().to_dict()
            )
        else:
            _pep_period_custo = {}
        _apps_zero_mask = (
            (_ws_k_col == "apps") &
            marg_q4["receita"].notna() & (marg_q4["receita"] != 0) &
            (marg_q4["custo_rateado"].fillna(0) == 0)
        )
        if _apps_zero_mask.any():
            _apps_zero_idx = marg_q4[_apps_zero_mask].index
            for _idx in _apps_zero_idx:
                _pep_b = str(marg_q4.at[_idx, "pep"]).split(".")[0]
                _per   = str(marg_q4.at[_idx, "periodo"])
                _rec   = float(marg_q4.at[_idx, "receita"])
                _custo = _pep_period_custo.get((_pep_b, _per), None)
                if _custo is not None and _custo != 0:
                    marg_q4.at[_idx, "custo_rateado"] = _custo
                    marg_q4.at[_idx, "margem"]         = _rec + _custo
                    marg_q4.at[_idx, "margem_pct"]     = (_rec + _custo) / _rec if _rec else 0.0
                else:
                    # Fallback: benchmark 35% para PEPs sem dados de pessoas
                    marg_q4.at[_idx, "custo_rateado"] = _rec * -0.65
                    marg_q4.at[_idx, "margem"]         = _rec * 0.35
                    marg_q4.at[_idx, "margem_pct"]     = 0.35

    # Override de margem para projetos OpenX: assume MB% = 45%
    if "no_hierarquia" in marg_q4.columns:
        openx_mask = marg_q4["no_hierarquia"].str.upper().str.strip() == "OPENX"
        marg_q4.loc[openx_mask, "margem"]       = marg_q4.loc[openx_mask, "receita"] * 0.45
        marg_q4.loc[openx_mask, "custo_rateado"]= marg_q4.loc[openx_mask, "receita"] * -0.55
        marg_q4.loc[openx_mask, "margem_pct"]   = marg_q4.loc[openx_mask, "receita"].apply(
            lambda r: 0.45 if r != 0 else 0.0
        )

    rac_q4["nome_norm"]  = rac_q4["nome_cliente"].apply(norm)
    marg_q4["nome_norm"] = marg_q4["nome_cliente"].apply(norm)

    # Limpa nomes do tipo "Recorrência Cliente (BR03CLP00043)" → "CLIENTE"
    # Ocorre quando o SAP embute o código do PEP no nome do cliente para itens de recorrência.
    _recorr_pat = re.compile(r'\([A-Z0-9]+\)\s*$')
    def _clean_nome_norm(n: str) -> str:
        n = _recorr_pat.sub('', n).strip()
        n = re.sub(r'^RECORRENCIA\s+', '', n).strip()
        n = re.sub(r'\s+RECORRENCIA\s*$', '', n).strip()
        return n
    marg_q4["nome_norm"] = marg_q4["nome_norm"].apply(_clean_nome_norm)

    # Pre-normalize SAP variant names → canonical budget names using clientes.csv aliases.
    # Rows with nome_base set define: canonical=nome_cliente, SAP-variant=nome_base.
    # Renaming SAP-variant → canonical BEFORE groupby merges all entries for that client.
    _cli_path = os.path.join(DIR, "parametros.xlsx")
    if os.path.exists(_cli_path):
        try:
            _cli_df = pd.read_excel(_cli_path, sheet_name="clientes")
            if "nome_base" in _cli_df.columns:
                _alias_pre: dict[str, str] = {}
                for _, _row in _cli_df.iterrows():
                    _nc = str(_row.get("nome_cliente", "") or "").strip()
                    _nb = str(_row.get("nome_base", "") or "").strip()
                    if _nc and _nb:
                        _nc_n = norm(_nc)
                        for _alias in [a.strip() for a in _nb.split("|") if a.strip()]:
                            _alias_pre[norm(_alias)] = _nc_n  # each SAP alias → canonical
                if _alias_pre:
                    rac_q4["nome_norm"]  = rac_q4["nome_norm"].map(
                        lambda x: _alias_pre.get(x, x))
                    marg_q4["nome_norm"] = marg_q4["nome_norm"].map(
                        lambda x: _alias_pre.get(x, x))
        except Exception:
            pass

    # Lookup: cliente_norm → realizado receita, margem e custo (Q4)
    rac_by_client   = rac_q4.groupby("nome_norm")["valor_liquido"].sum().to_dict()
    marg_by_client  = marg_q4.groupby("nome_norm")["margem"].sum().to_dict()
    rec_by_client   = marg_q4.groupby("nome_norm")["receita"].sum().to_dict()
    custo_by_client = marg_q4.groupby("nome_norm")["custo_rateado"].sum().to_dict()

    # Lookup: (cliente_norm, ws_key) → receita e margem reais por WS
    # Usa categoria_bu dos projetos reais, não o budget
    if "categoria_bu" in marg_q4.columns:
        marg_q4["ws_key"] = marg_q4["categoria_bu"].apply(
            lambda x: _norm_ws(str(x)) if pd.notna(x) and str(x).strip() else "demais"
        )
        rec_by_client_ws  = marg_q4.groupby(["nome_norm", "ws_key"])["receita"].sum().to_dict()
        marg_by_client_ws = marg_q4.groupby(["nome_norm", "ws_key"])["margem"].sum().to_dict()
    else:
        rec_by_client_ws  = {}
        marg_by_client_ws = {}

    # Lookups sem time Hyper: exclui projetos de empresa Hyper/BR07 para evitar
    # atribuição cruzada de receita do time Hyper a AEs de outras verticais.
    # Empresas Hyper no rac_projetos.csv: BR07, BR0C
    # Empresas Hyper no margem_projetos.csv: "Hyper", "BR07" (código residual)
    _EXCL_RAC  = {"BR07", "BR0C"}
    _EXCL_MARG = {"Hyper", "BR07"}
    rac_q4_nh  = rac_q4[~rac_q4["empresa"].isin(_EXCL_RAC)]
    marg_q4_nh = marg_q4[~marg_q4["empresa"].isin(_EXCL_MARG)]

    rac_by_client_nh   = rac_q4_nh.groupby("nome_norm")["valor_liquido"].sum().to_dict()
    marg_by_client_nh  = marg_q4_nh.groupby("nome_norm")["margem"].sum().to_dict()
    rec_by_client_nh   = marg_q4_nh.groupby("nome_norm")["receita"].sum().to_dict()
    custo_by_client_nh = marg_q4_nh.groupby("nome_norm")["custo_rateado"].sum().to_dict()

    if "ws_key" in marg_q4_nh.columns:
        rec_by_client_ws_nh  = marg_q4_nh.groupby(["nome_norm", "ws_key"])["receita"].sum().to_dict()
        marg_by_client_ws_nh = marg_q4_nh.groupby(["nome_norm", "ws_key"])["margem"].sum().to_dict()
    else:
        rec_by_client_ws_nh  = {}
        marg_by_client_ws_nh = {}

    # Add aliases: nome_cliente → nome_base (e.g. "C6 BANK" → "BANCO C6 S.A.")
    # so budget entries keyed by friendly name can find the SAP name in the lookup
    clientes_path = os.path.join(DIR, "parametros.xlsx")
    if os.path.exists(clientes_path):
        try:
            clientes_df = pd.read_excel(clientes_path, sheet_name="clientes")
            if "nome_base" in clientes_df.columns:
                for _, row in clientes_df.iterrows():
                    nc = str(row.get("nome_cliente", "") or "").strip()
                    nb = str(row.get("nome_base", "") or "").strip()
                    if nc and nb:
                        nc_n = norm(nc)
                        for alias in [a.strip() for a in nb.split("|") if a.strip()]:
                            nb_n = norm(alias)
                            for lookup in [rac_by_client, marg_by_client, rec_by_client, custo_by_client,
                                           rac_by_client_nh, marg_by_client_nh, rec_by_client_nh, custo_by_client_nh]:
                                if nb_n in lookup and nc_n not in lookup:
                                    lookup[nc_n] = lookup[nb_n]
                            # Alias WS lookups: (nc_n, ws) → (nb_n, ws)
                            for ws_k in WS_PESOS_Q4:
                                if (nb_n, ws_k) in rec_by_client_ws and (nc_n, ws_k) not in rec_by_client_ws:
                                    rec_by_client_ws[(nc_n, ws_k)]  = rec_by_client_ws[(nb_n, ws_k)]
                                if (nb_n, ws_k) in marg_by_client_ws and (nc_n, ws_k) not in marg_by_client_ws:
                                    marg_by_client_ws[(nc_n, ws_k)] = marg_by_client_ws[(nb_n, ws_k)]
                                if (nb_n, ws_k) in rec_by_client_ws_nh and (nc_n, ws_k) not in rec_by_client_ws_nh:
                                    rec_by_client_ws_nh[(nc_n, ws_k)]  = rec_by_client_ws_nh[(nb_n, ws_k)]
                                if (nb_n, ws_k) in marg_by_client_ws_nh and (nc_n, ws_k) not in marg_by_client_ws_nh:
                                    marg_by_client_ws_nh[(nc_n, ws_k)] = marg_by_client_ws_nh[(nb_n, ws_k)]
        except Exception:
            pass

    # ── Despesas pessoas Q4 (Opção C: proporcional por receita SAP) ─────────────
    total_despesa_pessoas_q4 = 0.0
    if not margem_pess.empty and not class_pess.empty:
        try:
            _mp_q4    = margem_pess[margem_pess["periodo"].isin(Q4_PERIODOS)]
            _cpf_desp = set(class_pess[class_pess["classificacao"] == "despesa"]["cpf_brcpf"].str.strip())
            _mp_desp  = _mp_q4[_mp_q4["cpf"].str.strip().isin(_cpf_desp)]
            total_despesa_pessoas_q4 = float(_mp_desp["custo_rateado"].sum())
        except Exception:
            pass

    # total_dir_rac_q4 será calculado após vert_by_pep e rac_by_pep estarem disponíveis
    total_dir_rac_q4 = 0.0

    # ─ Pep-level lookups for director vertical scope ─────────────────────────────
    _pep_vert_e: dict = {}
    try:
        _pv_e = pd.read_excel(clientes_path, sheet_name="pep_vertical", dtype=str).dropna(subset=["pep", "vertical"])
        _pep_vert_e = dict(zip(_pv_e["pep"].str.strip(), _pv_e["vertical"].str.strip()))
    except Exception:
        pass

    _cli_bu: dict = {}
    if os.path.exists(clientes_path):
        try:
            _cdf_b = pd.read_excel(clientes_path, sheet_name="clientes", dtype=str).fillna("")
            for _, _r in _cdf_b.iterrows():
                _nc = str(_r.get("nome_cliente", "") or "").strip()
                _nb = str(_r.get("nome_base", "") or "").strip()
                _bu2 = str(_r.get("bu", "") or "").strip()
                if _nc and _bu2:
                    _cli_bu[norm(_nc)] = _bu2
                if _nb and _bu2 and norm(_nb) not in _cli_bu:
                    _cli_bu[norm(_nb)] = _bu2
        except Exception:
            pass

    marg_q4["pep_base"] = marg_q4["pep"].astype(str).str.split(".").str[0].str.strip()
    if "ws_key" not in marg_q4.columns:
        marg_q4["ws_key"] = "demais"

    _pep_info = (
        marg_q4.drop_duplicates("pep_base")[["pep_base", "nome_norm", "nome_cliente"]]
        .set_index("pep_base")
    )

    def _resolve_pep_vert(pep_b: str, nome_n: str) -> str:
        pv = _pep_vert_e.get(pep_b, "")
        # pep_vertical.csv sempre prevalece — inclusive "Others":
        # se o pep está explicitamente mapeado (qualquer valor), usa esse valor.
        # Só cai no vlookup de cliente quando o pep não está no arquivo.
        if pv:
            return pv
        cv = _cli_bu.get(nome_n, "")
        return cv if cv else "Others"

    vert_by_pep = {
        pb: _resolve_pep_vert(pb, row["nome_norm"])
        for pb, row in _pep_info.iterrows()
    }
    pep_to_nome_cli = _pep_info["nome_norm"].to_dict()  # usa nome canônico (já aliasado) p/ bater com budget

    rac_by_pep: dict = {}
    if "pep" in rac_q4.columns:
        _rq4 = rac_q4.copy()
        _rq4["pep_base"] = _rq4["pep"].astype(str).str.split(".").str[0].str.strip()
        rac_by_pep = _rq4.groupby("pep_base")["valor_liquido"].sum().to_dict()

    rec_by_pep_ws = marg_q4.groupby(["pep_base", "ws_key"])["receita"].sum().to_dict()
    lb_by_pep_ws  = marg_q4.groupby(["pep_base", "ws_key"])["margem"].sum().to_dict()
    custo_by_pep  = marg_q4.groupby("pep_base")["custo_rateado"].sum().to_dict()

    # Total SAP receita dos diretores — denominador para alocação proporcional de despesas.
    # Usa rec_by_pep_ws (mesma fonte de _sap_rec_total em calc_bonus_diretor) para garantir
    # que as proporções somem exatamente total_despesa_pessoas_q4.
    _dir_verticals = set(DIRETOR_VERTICAL.values())
    total_dir_rac_q4 = sum(
        v for (pep, ws), v in rec_by_pep_ws.items()
        if vert_by_pep.get(pep) in _dir_verticals
    )

    return {
        "pessoas":  pessoas,
        "pesos_m":  pesos_m,
        "pesos_ws": pesos_ws,
        "triggers": triggers,
        "bgt_rec":  bgt_rec,
        "bgt_lb":   bgt_lb,
        "bgt_tcv":  bgt_tcv,
        "rac_by_client":      rac_by_client,
        "marg_by_client":     marg_by_client,
        "rec_by_client":      rec_by_client,
        "custo_by_client":    custo_by_client,
        "rec_by_client_ws":   rec_by_client_ws,
        "marg_by_client_ws":  marg_by_client_ws,
        "rac_by_client_nh":      rac_by_client_nh,
        "marg_by_client_nh":     marg_by_client_nh,
        "rec_by_client_nh":      rec_by_client_nh,
        "custo_by_client_nh":    custo_by_client_nh,
        "rec_by_client_ws_nh":   rec_by_client_ws_nh,
        "marg_by_client_ws_nh":  marg_by_client_ws_nh,
        "nexus":         nexus,
        "lb_trigger":    lb_trigger_map,
        "tcv_real":      tcv_real_map,
        "tcv_real_q3":   tcv_real_q3_map,
        "pesos_ws_pessoa":     pesos_ws_pessoa,
        "pesos_ws_pessoa_q3":  pesos_ws_pessoa_q3,
        "total_despesa_pessoas_q4": total_despesa_pessoas_q4,
        "total_dir_rac_q4":        total_dir_rac_q4,
        "mc_metas_dir":            mc_metas_dir,
        "vert_by_pep":      vert_by_pep,
        "pep_to_nome_cli":  pep_to_nome_cli,
        "rac_by_pep":       rac_by_pep,
        "rec_by_pep_ws":    rec_by_pep_ws,
        "lb_by_pep_ws":     lb_by_pep_ws,
        "custo_by_pep":     custo_by_pep,
    }


# ─── Helpers de trigger/atingimento ──────────────────────────────────────────

TRIGGER_REC_Q4 = 0.85   # Receita/TCV/MC
TRIGGER_MB_Q4  = 0.985  # MB%

WS_PESOS_Q4 = {
    "cloud":      0.08,   # Cloud/Cyber combinados
    "apps":       0.70,
    "dados":      0.08,
    "hyper":      0.08,
    "demais":     0.06,
}

# MB% benchmark Q4 por WS — usado quando o cálculo resulta em 100% (sem dados de custo)
WS_MB_BENCHMARK_Q4 = {
    "cloud":  0.34,
    "dados":  0.35,
    "hyper":  0.35,
    "demais": 0.37,
    # "apps": sem benchmark definido — usa valor calculado
}

WS_MAP = {
    # Normaliza nomes de WS do budget para chaves internas
    "apps":       "apps",
    "cloud":      "cloud",
    "cyber":      "cloud",   # Cyber combinado com Cloud
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


def _match_cliente_ws(cli_n: str, ws_lookup: dict) -> dict:
    """Retorna {ws_key: value} para um cliente com fuzzy match (mesmo critério de _match_cliente).
    Prefere match exato para evitar dupla contagem quando o alias já está no dict."""
    # Verifica se há chave exata — se sim, usa só ela (evita somar alias + original)
    has_exact = any(k_nome == cli_n for (k_nome, _) in ws_lookup)
    result = {}
    prefix = cli_n[:8]
    for (k_nome, k_ws), v in ws_lookup.items():
        if has_exact:
            if k_nome == cli_n:
                result[k_ws] = result.get(k_ws, 0.0) + v
        else:
            if cli_n in k_nome or k_nome.startswith(prefix):
                result[k_ws] = result.get(k_ws, 0.0) + v
    return result


# BS forçado por AE (quando budget tem BS errado)
AE_BS_OVERRIDE: dict = {}

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
    peso_tcv = float(pesos_row["TCV"] or 0)
    peso_rec = float(pesos_row["Receita"] or 0)
    peso_mb  = float(pesos_row["MB_pct"] or 0)

    # Budget Q4 por cliente/WS para este AE (usa nome completo)
    rec_ae  = bgt_rec[bgt_rec["ae_q4"].apply(norm) == pessoa_nome_n].copy()
    lb_ae   = bgt_lb[bgt_lb["ae_q4"].apply(norm) == pessoa_nome_n].copy()

    # Filtra pelo BS predominante (ou override fixo se cadastrado)
    if not rec_ae.empty and "bs" in rec_ae.columns:
        primary_bs = AE_BS_OVERRIDE.get(pessoa_nome_n) or rec_ae["bs"].value_counts().idxmax()
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

    # Pesos por WS: usa premissas_pesos_ws_pessoa.csv; fallback global WS_PESOS_Q4
    person_ws_weights = d["pesos_ws_pessoa"].get(pessoa_nome_n, dict(WS_PESOS_Q4))

    # Realizado por cliente, alocado por WS proporcionalmente ao budget
    realized_rec_ws: dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_lb_ws:  dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_lb_financeiro_ws:    dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_lb_gate_ws:          dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}  # apenas clientes com budget LB > 0
    realized_custo_financeiro_ws: dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    real_lb_financeiro:    float = 0.0  # LB real (marg_by_client) para o gatilho
    real_custo_total_fin:  float = 0.0  # Custo real (custo_rateado) total

    clientes_ae = rec_ae["cliente_norm"].dropna().unique()
    clientes_detalhe = []
    cli_contrib: dict[str, list] = {}  # {ws_k: [{cliente, budget_rec, real_rec}]}

    for cli_n in clientes_ae:
        real_rec  = _match_cliente(cli_n, d["rac_by_client_nh"])
        # Fallback: se não há RAC para este cliente, usa receita SAP do projetos
        if real_rec == 0:
            real_rec = _match_cliente(cli_n, d["rec_by_client_nh"])
        real_lb   = _match_cliente(cli_n, d["marg_by_client_nh"])
        real_custo = _match_cliente(cli_n, d["custo_by_client_nh"])
        lb_visual  = real_rec - abs(real_custo)  # LB financeiro do cliente (mesma base da aba margem por cliente)
        cli_rows = rec_ae[rec_ae["cliente_norm"] == cli_n]
        cli_bgt  = float(cli_rows["q4"].sum())
        cli_display = cli_rows["cliente"].iloc[0] if not cli_rows.empty else cli_n
        cli_bonus_lb  = 0.0
        cli_lb_fin    = 0.0   # LB financeiro deste cliente (RAC × benchmark, consistente com real_rec)
        cli_custo_fin = 0.0   # Custo financeiro deste cliente (derivado de cli_lb_fin)

        # Distribui realizado pela WS real dos projetos (categoria_bu do margem)
        # em vez de proporcional ao budget
        # Usa lookups sem time Hyper (_nh) para não atribuir receita do time Hyper a este AE
        actual_rec_ws  = _match_cliente_ws(cli_n, d["rec_by_client_ws_nh"])
        actual_marg_ws = _match_cliente_ws(cli_n, d["marg_by_client_ws_nh"])
        # Garante todas as chaves de WS
        actual_rec_ws  = {ws_k: actual_rec_ws.get(ws_k, 0.0)  for ws_k in WS_PESOS_Q4}
        actual_marg_ws = {ws_k: actual_marg_ws.get(ws_k, 0.0) for ws_k in WS_PESOS_Q4}
        actual_rec_total  = sum(actual_rec_ws.values())
        actual_marg_total = sum(actual_marg_ws.values())

        # Budget por WS deste cliente (para comparação de meta)
        cli_rec_ws    = cli_rows.groupby("ws_key")["q4"].sum()
        cli_lb_bgt_ws = (
            lb_ae[lb_ae["cliente_norm"] == cli_n].groupby("ws_key")["q4"].sum()
            if not lb_ae.empty else pd.Series(dtype=float)
        )

        if actual_rec_total > 0:
            # Usa proporção real da WS dos projetos
            for ws_k in WS_PESOS_Q4:
                prop = actual_rec_ws[ws_k] / actual_rec_total
                cli_real_ws = real_rec * prop  # receita RAC escalada pela proporção de WS
                realized_rec_ws[ws_k] = realized_rec_ws.get(ws_k, 0.0) + cli_real_ws
                bv = float(cli_rec_ws.get(ws_k, 0.0))
                if cli_real_ws > 0 or bv > 0:
                    cli_contrib.setdefault(ws_k, []).append({
                        "cliente":    cli_display,
                        "budget_rec": round(bv, 2),
                        "real_rec":   round(cli_real_ws, 2),
                    })
                # LB (bônus e financeiro): RAC × benchmark para WS com benchmark; margem real para Apps
                if ws_k in WS_MB_BENCHMARK_Q4:
                    _ws_lb  = cli_real_ws * WS_MB_BENCHMARK_Q4[ws_k]
                    _lb_fin = _ws_lb
                    _cu_fin = _lb_fin - cli_real_ws  # negativo
                else:
                    _ws_lb  = actual_marg_ws.get(ws_k, 0.0)
                    _lb_fin = _ws_lb
                    _cu_fin = _ws_lb - actual_rec_ws.get(ws_k, 0.0)  # negativo
                realized_lb_ws[ws_k] = realized_lb_ws.get(ws_k, 0.0) + _ws_lb
                cli_bonus_lb += _ws_lb
                # LB/Custo financeiros por WS: mesma base do bônus (RAC × benchmark)
                # garante que rec - |custo| = lb em todos os totais exibidos
                realized_lb_financeiro_ws[ws_k]    = realized_lb_financeiro_ws.get(ws_k, 0.0)    + _lb_fin
                realized_custo_financeiro_ws[ws_k] = realized_custo_financeiro_ws.get(ws_k, 0.0) + _cu_fin
                # Gate LB: só conta clientes com budget LB > 0 nesta WS
                if float(cli_lb_bgt_ws.get(ws_k, 0.0)) > 0:
                    realized_lb_gate_ws[ws_k] = realized_lb_gate_ws.get(ws_k, 0.0) + _lb_fin
                cli_lb_fin    += _lb_fin
                cli_custo_fin += _cu_fin
        else:
            # Fallback: proporção do budget (comportamento anterior)
            cli_rec_total = float(cli_rec_ws.sum())
            cli_lb_ws = (
                lb_ae[lb_ae["cliente_norm"] == cli_n].groupby("ws_key")["q4"].sum()
                if not lb_ae.empty else pd.Series(dtype=float)
            )
            cli_lb_total = float(cli_lb_ws.sum()) if len(cli_lb_ws) else 1.0
            for ws_k, bv in cli_rec_ws.items():
                prop = float(bv) / cli_rec_total if cli_rec_total > 0 else 0.0
                cli_real_ws = real_rec * prop
                realized_rec_ws[ws_k] = realized_rec_ws.get(ws_k, 0.0) + cli_real_ws
                _lb_f = real_lb * prop
                _cu_f = real_custo * prop
                realized_lb_financeiro_ws[ws_k]    = realized_lb_financeiro_ws.get(ws_k, 0.0)    + _lb_f
                realized_custo_financeiro_ws[ws_k] = realized_custo_financeiro_ws.get(ws_k, 0.0) + _cu_f
                # Gate LB: só conta clientes com budget LB > 0 nesta WS
                if float(cli_lb_ws.get(ws_k, 0.0)) > 0:
                    realized_lb_gate_ws[ws_k] = realized_lb_gate_ws.get(ws_k, 0.0) + _lb_f
                cli_lb_fin    += _lb_f
                cli_custo_fin += _cu_f
                cli_contrib.setdefault(ws_k, []).append({
                    "cliente":    cli_display,
                    "budget_rec": round(float(bv), 2),
                    "real_rec":   round(cli_real_ws, 2),
                })
            for ws_k, bv in cli_lb_ws.items():
                prop = float(bv) / cli_lb_total if cli_lb_total > 0 else 0.0
                _ws_lb = real_lb * prop
                realized_lb_ws[ws_k] = realized_lb_ws.get(ws_k, 0.0) + _ws_lb
                cli_bonus_lb += _ws_lb

        real_lb_financeiro   += cli_lb_fin
        real_custo_total_fin += cli_custo_fin
        margem_pct_visual = cli_lb_fin / real_rec if real_rec > 0 else None

        clientes_detalhe.append({
            "cliente":    cli_display,
            "budget_rec": round(cli_bgt, 2),
            "real_rec":   round(real_rec, 2),
            "real_custo": round(cli_custo_fin, 2),
            "real_lb":    round(cli_lb_fin, 2),
            "margem_pct": round(margem_pct_visual * 100, 1) if margem_pct_visual is not None else None,
        })

    realized_rec_ws["total"] = sum(v for k, v in realized_rec_ws.items() if k != "total")
    realized_lb_ws["total"]  = sum(v for k, v in realized_lb_ws.items() if k != "total")
    realized_lb_financeiro_ws["total"]    = sum(v for k, v in realized_lb_financeiro_ws.items()    if k != "total")
    realized_lb_gate_ws["total"]          = sum(v for k, v in realized_lb_gate_ws.items()          if k != "total")
    realized_custo_financeiro_ws["total"] = sum(v for k, v in realized_custo_financeiro_ws.items() if k != "total")

    # Calcular MB% realizado vs budget
    bgt_rec_total  = bgt_rec_ws.get("total", 1) or 1
    bgt_lb_total   = bgt_lb_ws.get("total", 0)
    real_rec_total = realized_rec_ws.get("total", 0)
    real_lb_total  = realized_lb_ws.get("total", 0)

    bgt_mb_pct  = bgt_lb_total / bgt_rec_total if bgt_rec_total else 0
    real_mb_pct = real_lb_total / real_rec_total if real_rec_total else 0

    # ─ Gatilho LB — lookup antecipado para uso no gate por WS ─
    lb_trigger_info_pre = d["lb_trigger"].get(pessoa_nome_n, {})
    if not lb_trigger_info_pre:
        primeiro = pessoa_nome_n.split()[0]
        lb_trigger_info_pre = next(
            (v for k, v in d["lb_trigger"].items() if k.startswith(primeiro)), {}
        )
    _meta_lb_pre    = lb_trigger_info_pre.get("meta_lb", 0.0)
    _trigger_lb_pre = lb_trigger_info_pre.get("trigger_lb", 0.0)
    # proporção trigger/meta (tipicamente 85%), usada para calcular trigger por WS
    _trigger_ratio  = (_trigger_lb_pre / _meta_lb_pre) if _meta_lb_pre > 0 else 0.0

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

        # MB% por WS — benchmark fixo para CÁLCULO de atingimento; financeiro para DISPLAY
        bgt_mb_pct_ws  = bgt_lb_ / bgt_r if bgt_r > 0 else 0.0
        real_lb_fin_ws = realized_lb_financeiro_ws.get(ws_k, 0.0)
        if real_r > 0:
            if ws_k in WS_MB_BENCHMARK_Q4:
                real_mb_pct_ws      = WS_MB_BENCHMARK_Q4[ws_k]   # benchmark → ating_mb
                real_lb_            = real_r * real_mb_pct_ws
            else:
                real_mb_pct_ws      = real_lb_ / real_r
            real_mb_pct_display = real_lb_fin_ws / real_r         # financeiro → display
        else:
            real_mb_pct_ws      = 0.0
            real_mb_pct_display = 0.0

        # Trigger MB: meta - 1.5pp (absoluto)
        trigger_mb_value = round(max(0.0, bgt_mb_pct_ws * 100 - 1.5), 2)

        # Gate MB: só trava em Apps
        if ws_k == "apps":
            ating_mb = calc_atingimento_mb(real_mb_pct_ws, bgt_mb_pct_ws)
            mb_gate  = 1.0 if ating_mb > 0 else 0.0
        else:
            # WS sem orçamento E sem receita não geram bônus MB (evita ating=1.0 com inatividade)
            if bgt_r == 0 and real_r == 0:
                ating_mb = 0.0
            elif bgt_lb_ == 0:
                # Sem budget de LB → sem meta de MB → sem bônus MB
                ating_mb = 0.0
            else:
                ating_mb = calc_atingimento_mb(real_mb_pct_ws, bgt_mb_pct_ws) if bgt_mb_pct_ws > 0 else 1.0
            mb_gate  = 1.0

        # ─ Gate LB por WS: trigger proporcional ao budget LB desta WS ─
        bgt_lb_ws_k = bgt_lb_ws.get(ws_k, 0.0)
        trigger_lb_ws_k = round(bgt_lb_ws_k * _trigger_ratio, 2) if bgt_lb_ws_k > 0 else 0.0
        real_lb_fin_ws_k = realized_lb_gate_ws.get(ws_k, 0.0)  # apenas clientes com budget LB > 0
        lb_gate_ws = 1 if (trigger_lb_ws_k <= 0 or real_lb_fin_ws_k >= trigger_lb_ws_k) else 0

        bonus_rec = Q4_QTDE * peso_ws * ating_rec * salario * peso_rec * lb_gate_ws
        rec_gate  = 1 if ating_rec > 0 else 0
        bonus_mb  = Q4_QTDE * peso_ws * ating_mb * mb_gate * salario * peso_mb * lb_gate_ws * rec_gate

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
            "real_mb_pct":         round(real_mb_pct_display * 100, 2),
            "mb_faltante":         round(max(0.0, trigger_mb_value - real_mb_pct_display * 100), 2),
            "ating_mb":            round(ating_mb, 4),
            "mb_gate":             mb_gate,
            "aplica_gate_mb":      ws_k == "apps",
            # Gate LB por WS
            "meta_lb_ws":          round(bgt_lb_ws_k, 2),
            "trigger_lb_ws":       trigger_lb_ws_k,
            "real_lb_financeiro":  round(realized_lb_financeiro_ws.get(ws_k, 0.0), 2),  # total para display
            "real_lb_gate":        round(real_lb_fin_ws_k, 2),  # apenas clientes com budget LB (usado no gate)
            "lb_gate_ws":          lb_gate_ws,
            # Bônus (já aplicado gate LB por WS)
            "bonus_rec":           round(bonus_rec, 2),
            "bonus_mb":            round(bonus_mb, 2),
            "bonus_ws":            round(bonus_rec + bonus_mb, 2),
            # Custo financeiro
            "real_custo_financeiro": round(realized_custo_financeiro_ws.get(ws_k, 0.0), 2),
            # Clientes nesta WS
            "clientes_ws":         cli_contrib.get(ws_k, []),
        })

    # TCV da área (apenas AE_GM — usa TCV do vertical Grupo Mult)
    bgt_tcv_q4_ae = 0.0
    real_tcv_q4_ae = 0.0
    ating_tcv_ae = 0.0
    bonus_tcv_ae = 0.0
    if peso_tcv > 0:
        tcv_rows = d["bgt_tcv"][d["bgt_tcv"]["ae"].apply(
            lambda x: str(x).strip() if pd.notna(x) else "") == "Grupo Mult"]
        bgt_tcv_q4_ae = float(
            tcv_rows[tcv_rows["descricao"].apply(lambda x: "receita" in str(x).lower())]["q4"].sum()
        )
        # Lookup por pessoa (ex: "Edmilson", "Guilherme"); fallback para vertical
        _tcv_key = pessoa["Nome"].strip().split()[0].capitalize()
        real_tcv_q4_ae = float(d["tcv_real"].get(_tcv_key, d["tcv_real"].get("Grupo Mult", 0.0)))
        ating_tcv_ae   = calc_atingimento(real_tcv_q4_ae, bgt_tcv_q4_ae, TRIGGER_REC_Q4)
        bonus_tcv_ae   = Q4_QTDE * ating_tcv_ae * salario * peso_tcv
        bonus_total   += bonus_tcv_ae

    # Atingimento total
    ating_rec_total = calc_atingimento(real_rec_total, bgt_rec_total, TRIGGER_REC_Q4)
    ating_mb_total  = calc_atingimento_mb(real_mb_pct, bgt_mb_pct)

    # Gatilho Mestre: LB total (referência/display; gate já aplicado por WS no loop)
    meta_lb_q4    = _meta_lb_pre
    trigger_lb_q4 = _trigger_lb_pre
    # lb_gate global: 1 se houve bônus efetivo (todos os gates passaram em algum WS)
    lb_gate = 1 if bonus_total > 0 else 0

    trigger_mb_pct_total = round(max(0.0, bgt_mb_pct * 100 - 1.5), 2)

    clientes_detalhe.sort(key=lambda x: x["budget_rec"], reverse=True)
    return {
        "nome":          pessoa["Nome"],
        "posicao":       posicao,
        "contrato":      str(pessoa.get("Contrato", "")),
        "salario_q4":    salario,
        "periodo":       "Q4 2025",
        "peso_tcv":      peso_tcv,
        "peso_receita":  peso_rec,
        "peso_mb":       peso_mb,
        "budget_tcv_q4": round(bgt_tcv_q4_ae, 2),
        "real_tcv_q4":   round(real_tcv_q4_ae, 2),
        "ating_tcv":     round(ating_tcv_ae, 4),
        "bonus_tcv":     round(bonus_tcv_ae, 2),
        "trigger_rec":   TRIGGER_REC_Q4,
        "trigger_mb_pct_total": trigger_mb_pct_total,
        "lb_gate":       lb_gate,
        "meta_lb_q4":    round(meta_lb_q4, 2),
        "trigger_lb_q4": round(trigger_lb_q4, 2),
        "real_lb_total":    round(real_lb_financeiro, 2),
        "real_custo_total": round(real_custo_total_fin, 2),
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


# ─── Cálculo AE Q3 (apenas Grupo Mult) ───────────────────────────────────────

@lru_cache(maxsize=1)
def _load_q3_realized():
    """Carrega e processa dados SAP Q3. Retorna dicts de lookups (vazios se sem dados Q3)."""
    _proj  = pd.read_excel(os.path.join(DIR, "operacional.xlsx"), sheet_name="projetos")
    _proj_rac = _proj[_proj["tipos"].notna() & (_proj["tipos"] != "")].copy()
    _proj_rac = _proj_rac.assign(tipo=_proj_rac["tipos"].str.split(",")).explode("tipo")
    _proj_rac["tipo"] = _proj_rac["tipo"].str.strip()
    _proj_rac = _proj_rac.rename(columns={"receita": "valor_liquido"})
    rac    = _proj_rac
    margem = _proj.rename(columns={"horas": "horas_total"})

    rac_q3  = rac[rac["periodo"].isin(Q3_PERIODOS)].copy()
    marg_q3 = margem[margem["periodo"].isin(Q3_PERIODOS)].copy()

    if rac_q3.empty and marg_q3.empty:
        empty: dict = {
            "rac_by_client_nh":      {},
            "marg_by_client_nh":     {},
            "rec_by_client_nh":      {},
            "custo_by_client_nh":    {},
            "rec_by_client_ws_nh":   {},
            "marg_by_client_ws_nh":  {},
        }
        return empty

    # Substitui receita SAP por RAC onde há match
    if "pep" in rac_q3.columns and not marg_q3.empty:
        _rac_rec = (
            rac_q3.assign(pep_base=rac_q3["pep"].astype(str).str.split(".").str[0].str.strip())
            .groupby(["periodo", "pep_base", "nome_cliente"])["valor_liquido"].sum()
            .reset_index().rename(columns={"valor_liquido": "receita_rac", "pep_base": "_pep_rac"})
        )
        marg_q3["_pep_base_tmp"] = marg_q3["pep"].astype(str).str.split(".").str[0].str.strip()
        marg_q3 = marg_q3.merge(
            _rac_rec,
            left_on=["periodo", "_pep_base_tmp", "nome_cliente"],
            right_on=["periodo", "_pep_rac", "nome_cliente"],
            how="left"
        )
        marg_q3["receita"] = marg_q3["receita_rac"].where(marg_q3["receita_rac"].notna(), marg_q3["receita"])
        marg_q3 = marg_q3.drop(columns=["receita_rac", "_pep_rac", "_pep_base_tmp"], errors="ignore")

    # Aplica benchmarks de MB% por WS (mesma lógica Q4)
    if "categoria_bu" in marg_q3.columns:
        _ws_k_col = marg_q3["categoria_bu"].apply(
            lambda x: _norm_ws(str(x)) if pd.notna(x) and str(x).strip() else "demais"
        )
        for _ws_k, _bench in WS_MB_BENCHMARK_Q4.items():
            _mask = (_ws_k_col == _ws_k) & marg_q3["receita"].notna() & (marg_q3["receita"] != 0)
            marg_q3.loc[_mask, "margem"]        = marg_q3.loc[_mask, "receita"] * _bench
            marg_q3.loc[_mask, "custo_rateado"] = marg_q3.loc[_mask, "receita"] * -(1 - _bench)
            marg_q3.loc[_mask, "margem_pct"]    = _bench
        _apps_zero_mask = (
            (_ws_k_col == "apps") &
            marg_q3["receita"].notna() & (marg_q3["receita"] != 0) &
            (marg_q3["custo_rateado"].fillna(0) == 0)
        )
        if _apps_zero_mask.any():
            for _idx in marg_q3[_apps_zero_mask].index:
                _rec = float(marg_q3.at[_idx, "receita"])
                marg_q3.at[_idx, "custo_rateado"] = _rec * -0.65
                marg_q3.at[_idx, "margem"]         = _rec * 0.35
                marg_q3.at[_idx, "margem_pct"]     = 0.35
        marg_q3["ws_key"] = _ws_k_col

    # Override OpenX
    if "no_hierarquia" in marg_q3.columns:
        openx_mask = marg_q3["no_hierarquia"].str.upper().str.strip() == "OPENX"
        marg_q3.loc[openx_mask, "margem"]        = marg_q3.loc[openx_mask, "receita"] * 0.45
        marg_q3.loc[openx_mask, "custo_rateado"] = marg_q3.loc[openx_mask, "receita"] * -0.55
        marg_q3.loc[openx_mask, "margem_pct"]    = 0.45

    rac_q3["nome_norm"]  = rac_q3["nome_cliente"].apply(norm)
    marg_q3["nome_norm"] = marg_q3["nome_cliente"].apply(norm)

    # Limpa nomes de recorrência
    _recorr_pat = re.compile(r'\([A-Z0-9]+\)\s*$')
    def _clean(n: str) -> str:
        n = _recorr_pat.sub('', n).strip()
        n = re.sub(r'^RECORRENCIA\s+', '', n).strip()
        return re.sub(r'\s+RECORRENCIA\s*$', '', n).strip()
    marg_q3["nome_norm"] = marg_q3["nome_norm"].apply(_clean)

    # Alias SAP → canonical usando parametros.xlsx/clientes
    _cli_path = os.path.join(DIR, "parametros.xlsx")
    if os.path.exists(_cli_path):
        try:
            _cdf = pd.read_excel(_cli_path, sheet_name="clientes")
            if "nome_base" in _cdf.columns:
                _alias: dict[str, str] = {}
                for _, _r in _cdf.iterrows():
                    _nc = str(_r.get("nome_cliente", "") or "").strip()
                    _nb = str(_r.get("nome_base", "") or "").strip()
                    if _nc and _nb:
                        _alias[norm(_nb)] = norm(_nc)
                if _alias:
                    rac_q3["nome_norm"]  = rac_q3["nome_norm"].map(lambda x: _alias.get(x, x))
                    marg_q3["nome_norm"] = marg_q3["nome_norm"].map(lambda x: _alias.get(x, x))
        except Exception:
            pass

    # Exclui empresas Hyper
    _EXCL_RAC  = {"BR07", "BR0C"}
    _EXCL_MARG = {"Hyper", "BR07"}
    rac_q3_nh  = rac_q3[~rac_q3["empresa"].isin(_EXCL_RAC)]
    marg_q3_nh = marg_q3[~marg_q3["empresa"].isin(_EXCL_MARG)] if "empresa" in marg_q3.columns else marg_q3

    rac_by_client_nh  = rac_q3_nh.groupby("nome_norm")["valor_liquido"].sum().to_dict()
    marg_by_client_nh = marg_q3_nh.groupby("nome_norm")["margem"].sum().to_dict()
    rec_by_client_nh  = marg_q3_nh.groupby("nome_norm")["receita"].sum().to_dict()
    custo_by_client_nh = marg_q3_nh.groupby("nome_norm")["custo_rateado"].sum().to_dict()

    if "ws_key" in marg_q3_nh.columns:
        rec_by_client_ws_nh  = marg_q3_nh.groupby(["nome_norm", "ws_key"])["receita"].sum().to_dict()
        marg_by_client_ws_nh = marg_q3_nh.groupby(["nome_norm", "ws_key"])["margem"].sum().to_dict()
    else:
        rec_by_client_ws_nh  = {}
        marg_by_client_ws_nh = {}

    # Adiciona aliases canonical → base para lookups
    if os.path.exists(_cli_path):
        try:
            _cdf2 = pd.read_excel(_cli_path, sheet_name="clientes")
            if "nome_base" in _cdf2.columns:
                for _, _r in _cdf2.iterrows():
                    nc = str(_r.get("nome_cliente", "") or "").strip()
                    nb = str(_r.get("nome_base", "") or "").strip()
                    if nc and nb:
                        nc_n, nb_n = norm(nc), norm(nb)
                        for lk in [rac_by_client_nh, marg_by_client_nh, rec_by_client_nh, custo_by_client_nh]:
                            if nb_n in lk and nc_n not in lk:
                                lk[nc_n] = lk[nb_n]
                        for ws_k in WS_PESOS_Q4:
                            if (nb_n, ws_k) in rec_by_client_ws_nh and (nc_n, ws_k) not in rec_by_client_ws_nh:
                                rec_by_client_ws_nh[(nc_n, ws_k)]  = rec_by_client_ws_nh[(nb_n, ws_k)]
                            if (nb_n, ws_k) in marg_by_client_ws_nh and (nc_n, ws_k) not in marg_by_client_ws_nh:
                                marg_by_client_ws_nh[(nc_n, ws_k)] = marg_by_client_ws_nh[(nb_n, ws_k)]
        except Exception:
            pass

    # Override com dados validados de parametros.xlsx/realizados_manual
    _ov_path = os.path.join(DIR, "parametros.xlsx")
    if os.path.exists(_ov_path):
        try:
            _ov_all = pd.read_excel(_ov_path, sheet_name="realizados_manual")
            ov = _ov_all[_ov_all["tipo"] == "Q3_GM"].rename(
                columns={"ae_ou_vertical": "farmer"}
            )
            for _, row in ov.iterrows():
                cli_n = norm(str(row["cliente"]))
                rec   = float(row["receita"])
                lb    = float(row["lb"])
                rac_by_client_nh[cli_n]  = rec
                rec_by_client_nh[cli_n]  = rec
                marg_by_client_nh[cli_n] = lb
                custo_by_client_nh[cli_n] = lb - rec  # negativo
                rec_by_client_ws_nh[(cli_n, "apps")]  = rec
                marg_by_client_ws_nh[(cli_n, "apps")] = lb
                # limpa ws_keys alternativos do SAP para este cliente
                for _ws in [k for k in list(rec_by_client_ws_nh) if k[0] == cli_n and k[1] != "apps"]:
                    del rec_by_client_ws_nh[_ws]
                for _ws in [k for k in list(marg_by_client_ws_nh) if k[0] == cli_n and k[1] != "apps"]:
                    del marg_by_client_ws_nh[_ws]
        except Exception:
            pass

    return {
        "rac_by_client_nh":      rac_by_client_nh,
        "marg_by_client_nh":     marg_by_client_nh,
        "rec_by_client_nh":      rec_by_client_nh,
        "custo_by_client_nh":    custo_by_client_nh,
        "rec_by_client_ws_nh":   rec_by_client_ws_nh,
        "marg_by_client_ws_nh":  marg_by_client_ws_nh,
    }


def calc_bonus_ae_q3(nome: str) -> dict:
    """Calcula bônus Q3 para AE_GM (Grupo Mult). Estrutura idêntica ao Q4 mas usando colunas q3."""
    d   = _load_all()
    q3r = _load_q3_realized()

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
    pessoa_nome_n = norm(str(pessoa["Nome"]))

    salario = float(pessoa.get("Sal_Q3") or 0)
    posicao = str(pessoa["Posicao"]).upper().strip()

    pesos_row = d["pesos_m"][
        (d["pesos_m"]["Periodo"] == "Quarter") &
        (d["pesos_m"]["Posicao"].str.upper() == posicao)
    ]
    if pesos_row.empty:
        pesos_row = d["pesos_m"][(d["pesos_m"]["Periodo"] == "Quarter") & (d["pesos_m"]["Posicao"] == "AE")]
    pesos_row = pesos_row.iloc[0]
    peso_tcv = float(pesos_row["TCV"] or 0)
    peso_rec = float(pesos_row["Receita"] or 0)
    peso_mb  = float(pesos_row["MB_pct"] or 0)

    # Budget Q3 por cliente/WS para este AE (usa ae_q3 e coluna q3)
    rec_ae = bgt_rec[bgt_rec["ae_q3"].apply(norm) == pessoa_nome_n].copy()
    lb_ae  = bgt_lb[bgt_lb["ae_q3"].apply(norm) == pessoa_nome_n].copy()

    if not rec_ae.empty and "bs" in rec_ae.columns:
        primary_bs = AE_BS_OVERRIDE.get(pessoa_nome_n) or rec_ae["bs"].value_counts().idxmax()
        rec_ae = rec_ae[rec_ae["bs"] == primary_bs].copy()
        if not lb_ae.empty and "bs" in lb_ae.columns:
            lb_ae = lb_ae[lb_ae["bs"] == primary_bs].copy()

    rec_ae["ws_key"] = rec_ae["ws"].apply(_norm_ws)
    lb_ae["ws_key"]  = lb_ae["ws"].apply(_norm_ws)

    bgt_rec_ws = rec_ae.groupby("ws_key")["q3"].sum().to_dict()
    bgt_lb_ws  = lb_ae.groupby("ws_key")["q3"].sum().to_dict()
    bgt_rec_ws["total"] = float(rec_ae["q3"].sum())
    bgt_lb_ws["total"]  = float(lb_ae["q3"].sum())

    person_ws_weights = d["pesos_ws_pessoa_q3"].get(pessoa_nome_n, dict(WS_PESOS_Q4))

    realized_rec_ws:               dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_lb_ws:                dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_lb_financeiro_ws:     dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_lb_gate_ws:           dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_custo_financeiro_ws:  dict[str, float] = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    real_lb_financeiro:   float = 0.0
    real_custo_total_fin: float = 0.0

    clientes_ae = rec_ae["cliente_norm"].dropna().unique()
    clientes_detalhe = []
    cli_contrib: dict[str, list] = {}

    for cli_n in clientes_ae:
        real_rec   = _match_cliente(cli_n, q3r["rac_by_client_nh"])
        real_lb    = _match_cliente(cli_n, q3r["marg_by_client_nh"])
        real_custo = _match_cliente(cli_n, q3r["custo_by_client_nh"])

        cli_rows = rec_ae[rec_ae["cliente_norm"] == cli_n]
        cli_bgt  = float(cli_rows["q3"].sum())
        cli_display = cli_rows["cliente"].iloc[0] if not cli_rows.empty else cli_n
        cli_bonus_lb  = 0.0
        cli_lb_fin    = 0.0
        cli_custo_fin = 0.0

        actual_rec_ws  = _match_cliente_ws(cli_n, q3r["rec_by_client_ws_nh"])
        actual_marg_ws = _match_cliente_ws(cli_n, q3r["marg_by_client_ws_nh"])
        actual_rec_ws  = {ws_k: actual_rec_ws.get(ws_k, 0.0)  for ws_k in WS_PESOS_Q4}
        actual_marg_ws = {ws_k: actual_marg_ws.get(ws_k, 0.0) for ws_k in WS_PESOS_Q4}
        actual_rec_total = sum(actual_rec_ws.values())

        cli_rec_ws    = cli_rows.groupby("ws_key")["q3"].sum()
        cli_lb_bgt_ws = (
            lb_ae[lb_ae["cliente_norm"] == cli_n].groupby("ws_key")["q3"].sum()
            if not lb_ae.empty else pd.Series(dtype=float)
        )

        if actual_rec_total > 0:
            for ws_k in WS_PESOS_Q4:
                prop = actual_rec_ws[ws_k] / actual_rec_total
                cli_real_ws = real_rec * prop
                realized_rec_ws[ws_k] = realized_rec_ws.get(ws_k, 0.0) + cli_real_ws
                bv = float(cli_rec_ws.get(ws_k, 0.0))
                if cli_real_ws > 0 or bv > 0:
                    cli_contrib.setdefault(ws_k, []).append({
                        "cliente":    cli_display,
                        "budget_rec": round(bv, 2),
                        "real_rec":   round(cli_real_ws, 2),
                    })
                if ws_k in WS_MB_BENCHMARK_Q4:
                    _ws_lb  = cli_real_ws * WS_MB_BENCHMARK_Q4[ws_k]
                    _lb_fin = _ws_lb
                    _cu_fin = _lb_fin - cli_real_ws
                else:
                    _ws_lb  = actual_marg_ws.get(ws_k, 0.0)
                    _lb_fin = _ws_lb
                    _cu_fin = _ws_lb - actual_rec_ws.get(ws_k, 0.0)
                realized_lb_ws[ws_k]             = realized_lb_ws.get(ws_k, 0.0)             + _ws_lb
                realized_lb_financeiro_ws[ws_k]  = realized_lb_financeiro_ws.get(ws_k, 0.0)  + _lb_fin
                realized_custo_financeiro_ws[ws_k] = realized_custo_financeiro_ws.get(ws_k, 0.0) + _cu_fin
                cli_bonus_lb += _ws_lb
                if float(cli_lb_bgt_ws.get(ws_k, 0.0)) > 0:
                    realized_lb_gate_ws[ws_k] = realized_lb_gate_ws.get(ws_k, 0.0) + _lb_fin
                cli_lb_fin    += _lb_fin
                cli_custo_fin += _cu_fin
        else:
            cli_rec_total = float(cli_rec_ws.sum())
            cli_lb_ws = (
                lb_ae[lb_ae["cliente_norm"] == cli_n].groupby("ws_key")["q3"].sum()
                if not lb_ae.empty else pd.Series(dtype=float)
            )
            cli_lb_total = float(cli_lb_ws.sum()) if len(cli_lb_ws) else 1.0
            for ws_k, bv in cli_rec_ws.items():
                prop = float(bv) / cli_rec_total if cli_rec_total > 0 else 0.0
                cli_real_ws = real_rec * prop
                realized_rec_ws[ws_k] = realized_rec_ws.get(ws_k, 0.0) + cli_real_ws
                _lb_f  = real_lb    * prop
                _cu_f  = real_custo * prop
                realized_lb_financeiro_ws[ws_k]    = realized_lb_financeiro_ws.get(ws_k, 0.0)    + _lb_f
                realized_custo_financeiro_ws[ws_k] = realized_custo_financeiro_ws.get(ws_k, 0.0) + _cu_f
                if float(cli_lb_ws.get(ws_k, 0.0)) > 0:
                    realized_lb_gate_ws[ws_k] = realized_lb_gate_ws.get(ws_k, 0.0) + _lb_f
                cli_lb_fin    += _lb_f
                cli_custo_fin += _cu_f
                cli_contrib.setdefault(ws_k, []).append({
                    "cliente":    cli_display,
                    "budget_rec": round(float(bv), 2),
                    "real_rec":   round(cli_real_ws, 2),
                })
            for ws_k, bv in cli_lb_ws.items():
                prop = float(bv) / cli_lb_total if cli_lb_total > 0 else 0.0
                _ws_lb = real_lb * prop
                realized_lb_ws[ws_k] = realized_lb_ws.get(ws_k, 0.0) + _ws_lb
                cli_bonus_lb += _ws_lb

        real_lb_financeiro   += cli_lb_fin
        real_custo_total_fin += cli_custo_fin
        margem_pct_visual = cli_lb_fin / real_rec if real_rec > 0 else None
        clientes_detalhe.append({
            "cliente":    cli_display,
            "budget_rec": round(cli_bgt, 2),
            "real_rec":   round(real_rec, 2),
            "real_custo": round(cli_custo_fin, 2),
            "real_lb":    round(cli_lb_fin, 2),
            "margem_pct": round(margem_pct_visual * 100, 1) if margem_pct_visual is not None else None,
        })

    realized_rec_ws["total"]              = sum(v for k, v in realized_rec_ws.items()              if k != "total")
    realized_lb_ws["total"]               = sum(v for k, v in realized_lb_ws.items()               if k != "total")
    realized_lb_financeiro_ws["total"]    = sum(v for k, v in realized_lb_financeiro_ws.items()    if k != "total")
    realized_lb_gate_ws["total"]          = sum(v for k, v in realized_lb_gate_ws.items()          if k != "total")
    realized_custo_financeiro_ws["total"] = sum(v for k, v in realized_custo_financeiro_ws.items() if k != "total")

    bgt_rec_total  = bgt_rec_ws.get("total", 1) or 1
    bgt_lb_total   = bgt_lb_ws.get("total", 0)
    real_rec_total = realized_rec_ws.get("total", 0)
    real_lb_total  = realized_lb_ws.get("total", 0)
    bgt_mb_pct     = bgt_lb_total / bgt_rec_total if bgt_rec_total else 0
    real_mb_pct    = real_lb_total / real_rec_total if real_rec_total else 0

    # Trigger ratio LB (igual ao Q4 — usa mesma tabela anual, proporção é estável)
    lb_trigger_info = d["lb_trigger"].get(pessoa_nome_n, {})
    if not lb_trigger_info:
        primeiro = pessoa_nome_n.split()[0]
        lb_trigger_info = next(
            (v for k, v in d["lb_trigger"].items() if k.startswith(primeiro)), {}
        )
    _meta_lb    = lb_trigger_info.get("meta_lb", 0.0)
    _trigger_lb = lb_trigger_info.get("trigger_lb", 0.0)
    _trigger_ratio = (_trigger_lb / _meta_lb) if _meta_lb > 0 else 0.0

    detalhe_ws = []
    bonus_total = 0.0

    for ws_k in WS_PESOS_Q4:
        peso_ws  = person_ws_weights.get(ws_k, 0.0)
        bgt_r    = bgt_rec_ws.get(ws_k, 0.0)
        real_r   = realized_rec_ws.get(ws_k, 0.0)
        bgt_lb_  = bgt_lb_ws.get(ws_k, 0.0)
        real_lb_ = realized_lb_ws.get(ws_k, 0.0)

        ating_rec = calc_atingimento(real_r, bgt_r, TRIGGER_REC_Q3)

        bgt_mb_pct_ws  = bgt_lb_ / bgt_r if bgt_r > 0 else 0.0
        real_lb_fin_ws = realized_lb_financeiro_ws.get(ws_k, 0.0)
        if real_r > 0:
            if ws_k in WS_MB_BENCHMARK_Q4:
                real_mb_pct_ws      = WS_MB_BENCHMARK_Q4[ws_k]
                real_lb_            = real_r * real_mb_pct_ws
            else:
                real_mb_pct_ws      = real_lb_ / real_r
            real_mb_pct_display = real_lb_fin_ws / real_r
        else:
            real_mb_pct_ws      = 0.0
            real_mb_pct_display = 0.0

        trigger_mb_value = round(max(0.0, bgt_mb_pct_ws * 100 - MB_TRIGGER_DELTA_Q3 * 100), 2)

        if ws_k == "apps":
            ating_mb = calc_atingimento_mb(real_mb_pct_ws, bgt_mb_pct_ws, MB_TRIGGER_DELTA_Q3)
            mb_gate  = 1.0 if ating_mb > 0 else 0.0
        else:
            if bgt_r == 0 and real_r == 0:
                ating_mb = 0.0
            elif bgt_lb_ == 0:
                ating_mb = 0.0
            else:
                ating_mb = calc_atingimento_mb(real_mb_pct_ws, bgt_mb_pct_ws, MB_TRIGGER_DELTA_Q3) if bgt_mb_pct_ws > 0 else 1.0
            mb_gate  = 1.0

        bgt_lb_ws_k     = bgt_lb_ws.get(ws_k, 0.0)
        trigger_lb_ws_k = round(bgt_lb_ws_k * TRIGGER_REC_Q3, 2) if bgt_lb_ws_k > 0 else 0.0
        real_lb_fin_ws_k = realized_lb_gate_ws.get(ws_k, 0.0)
        lb_gate_ws = 1 if (trigger_lb_ws_k <= 0 or real_lb_fin_ws_k >= trigger_lb_ws_k) else 0

        bonus_rec = Q3_QTDE * peso_ws * ating_rec * salario * peso_rec * lb_gate_ws
        rec_gate  = lb_gate_ws  # Q3: se o gate de LB passou, o bônus MB também é pago
        bonus_mb  = Q3_QTDE * peso_ws * ating_mb  * mb_gate  * salario * peso_mb  * lb_gate_ws * rec_gate

        bonus_total += bonus_rec + bonus_mb

        detalhe_ws.append({
            "ws":                  ws_k,
            "peso_ws":             round(peso_ws, 4),
            "budget_rec":          round(bgt_r, 2),
            "trigger_rec_amount":  round(bgt_r * TRIGGER_REC_Q3, 2),
            "real_rec":            round(real_r, 2),
            "receita_faltante":    round(max(0.0, bgt_r * TRIGGER_REC_Q3 - real_r), 2),
            "ating_rec":           round(ating_rec, 4),
            "budget_mb_pct":       round(bgt_mb_pct_ws * 100, 2),
            "trigger_mb_pct":      trigger_mb_value,
            "real_mb_pct":         round(real_mb_pct_display * 100, 2),
            "mb_faltante":         round(max(0.0, trigger_mb_value - real_mb_pct_display * 100), 2),
            "ating_mb":            round(ating_mb, 4),
            "mb_gate":             mb_gate,
            "aplica_gate_mb":      ws_k == "apps",
            "meta_lb_ws":          round(bgt_lb_ws_k, 2),
            "trigger_lb_ws":       trigger_lb_ws_k,
            "real_lb_financeiro":  round(realized_lb_financeiro_ws.get(ws_k, 0.0), 2),
            "real_lb_gate":        round(real_lb_fin_ws_k, 2),
            "lb_gate_ws":          lb_gate_ws,
            "bonus_rec":           round(bonus_rec, 2),
            "bonus_mb":            round(bonus_mb, 2),
            "bonus_ws":            round(bonus_rec + bonus_mb, 2),
            "real_custo_financeiro": round(realized_custo_financeiro_ws.get(ws_k, 0.0), 2),
            "clientes_ws":         cli_contrib.get(ws_k, []),
        })

    # TCV Grupo Mult Q3
    bgt_tcv_q3_ae = 0.0
    real_tcv_q3_ae = 0.0
    ating_tcv_ae = 0.0
    bonus_tcv_ae = 0.0
    if peso_tcv > 0:
        tcv_rows = d["bgt_tcv"][d["bgt_tcv"]["ae"].apply(
            lambda x: str(x).strip() if pd.notna(x) else "") == "Grupo Mult"]
        bgt_tcv_q3_ae = float(
            tcv_rows[tcv_rows["descricao"].apply(lambda x: "receita" in str(x).lower())]["q3"].sum()
        )
        # Q3 TCV realizado: lookup por pessoa; fallback para vertical
        _tcv_key_q3 = pessoa["Nome"].strip().split()[0].capitalize()
        real_tcv_q3_ae = float(d["tcv_real_q3"].get(_tcv_key_q3, d["tcv_real_q3"].get("Grupo Mult", 0.0)))
        ating_tcv_ae   = calc_atingimento(real_tcv_q3_ae, bgt_tcv_q3_ae, TRIGGER_REC_Q3)
        bonus_tcv_ae   = Q3_QTDE * ating_tcv_ae * salario * peso_tcv
        bonus_total   += bonus_tcv_ae

    ating_rec_total = calc_atingimento(real_rec_total, bgt_rec_total, TRIGGER_REC_Q3)
    ating_mb_total  = calc_atingimento_mb(real_mb_pct, bgt_mb_pct, MB_TRIGGER_DELTA_Q3)
    lb_gate = 1 if bonus_total > 0 else 0
    trigger_mb_pct_total = round(max(0.0, bgt_mb_pct * 100 - MB_TRIGGER_DELTA_Q3 * 100), 2)

    clientes_detalhe.sort(key=lambda x: x["budget_rec"], reverse=True)
    return {
        "nome":          pessoa["Nome"],
        "posicao":       posicao,
        "contrato":      str(pessoa.get("Contrato", "")),
        "salario_q4":    salario,  # campo salario_q4 contém salário do período (Q3 neste caso)
        "periodo":       "Q3 2025",
        "peso_tcv":      peso_tcv,
        "peso_receita":  peso_rec,
        "peso_mb":       peso_mb,
        "budget_tcv_q4": round(bgt_tcv_q3_ae, 2),
        "real_tcv_q4":   round(real_tcv_q3_ae, 2),
        "ating_tcv":     round(ating_tcv_ae, 4),
        "bonus_tcv":     round(bonus_tcv_ae, 2),
        "trigger_rec":   TRIGGER_REC_Q3,
        "trigger_mb_pct_total": trigger_mb_pct_total,
        "lb_gate":       lb_gate,
        "meta_lb_q4":    0.0,
        "trigger_lb_q4": 0.0,
        "real_lb_total":     round(real_lb_financeiro, 2),
        "real_custo_total":  round(real_custo_total_fin, 2),
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
    norm("Zanini"):       "Finance",
    norm("Artea"):        "Multisector",
    norm("Henrique"):     "Grupo Mult",
    norm("Alexsandro"):   "Retail",
}

# Chave no budget_tcv para cada vertical de Diretor
DIRETOR_TCV_KEY = {
    "Health":       "Health",
    "Multisector":  "Multisector",
    "Finance":      "Wagner",
    "Grupo Mult":   "Felipe",
    "Retail":       "Retail",
}

# Mapeamento vertical → bs no budget_receita/lb
VERTICAL_BS_MAP = {
    "Health":       "Health",
    "Multisector":  "Multisector",
    "Finance":      "Finance",
    "Grupo Mult":   "Grupo Mult",
    "Retail":       "Retail",
}

# Verticais Nexus correspondentes para MC% (nexus_agg.csv usa "Finance & Insurance" e "Logistics")
NEXUS_VERTICAL_MAP = {
    "Finance":      ["Finance & Insurance"],
    "Health":       ["Health"],
    "Grupo Mult":   ["Logistics"],
    "Multisector":  ["Multisector"],
    "Retail":       ["Retail"],
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
    peso_lb  = float(pesos_row["MB_pct"] or 0)   # LB absoluto (10%)

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
    # TCV realizado: lido do tcv_realizado.csv por vertical
    real_tcv_q4 = float(d["tcv_real"].get(vertical, 0.0)) if vertical else 0.0

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
    # Realizado receita: soma de RAC dos clientes da vertical + detalhe por cliente
    real_rec_q4 = 0.0
    clientes_detalhe_dir = []

    # Base de clientes: todos os clientes da vertical (budget_receita + clientes.csv)
    # sem filtro de AE — o diretor é responsável pela vertical inteira
    cli_budget: dict[str, tuple[str, float]] = {}  # {norm_name: (display, budget_q4)}
    if not rec_dir.empty:
        grp = rec_dir.groupby("cliente_norm", as_index=False).agg(
            cliente=("cliente", "first"), q4=("q4", "sum")
        )
        for _, r in grp.iterrows():
            k = norm(r["cliente"])
            if not k:  # ignora linhas com cliente vazio
                continue
            cli_budget[k] = (r["cliente"], float(r["q4"]))

    # Complementa com parametros.xlsx/clientes (todos da BU, com ou sem AE)
    clientes_path = os.path.join(DIR, "parametros.xlsx")
    bu_key = bs_key or (vertical or "")
    if os.path.exists(clientes_path) and bu_key:
        try:
            cdf = pd.read_excel(clientes_path, sheet_name="clientes", dtype=str).fillna("")
            for _, row in cdf[cdf["bu"].str.lower() == bu_key.lower()].iterrows():
                nc = str(row["nome_cliente"]).strip()
                if nc:
                    k = norm(nc)
                    if k not in cli_budget:
                        cli_budget[k] = (nc, 0.0)
        except Exception:
            pass

    cli_source = [(k, disp, bgt) for k, (disp, bgt) in cli_budget.items()]

    _bgt_by_cli = {norm(disp): bgt for _, disp, bgt in cli_source}

    # ─ Realizado por PEP (espelha escopo da aba Margem por Cliente) ─────────────
    real_rec_q4 = 0.0       # RAC — base do gatilho de receita
    _sap_rec_total = 0.0    # SAP receita — denominador do LB%
    realized_rec_ws_dir: dict = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    realized_lb_ws_dir:  dict = {ws_k: 0.0 for ws_k in WS_PESOS_Q4}
    _cli_agg: dict = {}

    for pep_b, pep_vert in d.get("vert_by_pep", {}).items():
        if pep_vert != vertical:
            continue
        pep_rac       = d.get("rac_by_pep", {}).get(pep_b, 0.0)
        pep_custo     = d.get("custo_by_pep", {}).get(pep_b, 0.0)
        pep_rec_ws    = {ws_k: d.get("rec_by_pep_ws", {}).get((pep_b, ws_k), 0.0) for ws_k in WS_PESOS_Q4}
        pep_lb_ws     = {ws_k: d.get("lb_by_pep_ws", {}).get((pep_b, ws_k), 0.0) for ws_k in WS_PESOS_Q4}
        pep_rec_total = sum(pep_rec_ws.values())
        real_rec_q4  += pep_rac
        _sap_rec_total += pep_rec_total

        # LB e receita por WS: usa SAP diretamente (benchmark já aplicado em _load_all)
        # Assim o MB% do breakdown WS bate com o MB% da Carteira de Clientes
        for ws_k in WS_PESOS_Q4:
            realized_rec_ws_dir[ws_k] += pep_rec_ws[ws_k]
            realized_lb_ws_dir[ws_k]  += pep_lb_ws[ws_k]

        pep_lb_total = sum(pep_lb_ws.values())
        cli_disp = d.get("pep_to_nome_cli", {}).get(pep_b, pep_b)
        if cli_disp not in _cli_agg:
            _cli_agg[cli_disp] = {"rec": 0.0, "custo": 0.0, "lb": 0.0}
        _cli_agg[cli_disp]["rec"]   += pep_rac
        _cli_agg[cli_disp]["custo"] += pep_custo
        _cli_agg[cli_disp]["lb"]    += pep_lb_total

    clientes_detalhe_dir = [
        {
            "cliente":    cli_disp,
            "budget_rec": round(_bgt_by_cli.get(norm(cli_disp), 0.0), 2),
            "real_rec":   round(agg["rec"], 2),
            "real_custo": round(agg["custo"], 2),
            "real_lb":    round(agg["lb"], 2),
            "margem_pct": round(agg["lb"] / agg["rec"] * 100, 1) if agg["rec"] > 0 else None,
        }
        for cli_disp, agg in _cli_agg.items()
    ]
    # Adiciona clientes com budget mas sem PEPs realizados no SAP
    _cli_agg_keys = {norm(k) for k in _cli_agg}
    for cli_n, cli_disp, bgt in cli_source:
        if cli_n not in _cli_agg_keys and bgt > 0:
            clientes_detalhe_dir.append({
                "cliente":    cli_disp,
                "budget_rec": round(bgt, 2),
                "real_rec":   0.0,
                "real_custo": 0.0,
                "real_lb":    0.0,
                "margem_pct": None,
            })
    clientes_detalhe_dir.sort(key=lambda x: x["budget_rec"], reverse=True)

    ating_rec = calc_atingimento(real_rec_q4, bgt_rec_q4, TRIGGER_REC_Q4)

    # ─ WS breakdown budget ───────────────────────────────────────────────────────
    if not rec_dir.empty:
        bgt_rec_ws_dir = rec_dir.copy()
        bgt_rec_ws_dir["ws_key"] = rec_dir["ws"].apply(_norm_ws)
        bgt_rec_ws = bgt_rec_ws_dir.groupby("ws_key")["q4"].sum().to_dict()
    else:
        bgt_rec_ws = {}
    bgt_rec_ws["total"] = sum(v for k, v in bgt_rec_ws.items() if k != "total")

    # ─ MC% ─
    # MC% = (LB SAP + Despesas Nexus) / Receita SAP
    # Usa SAP receita como denominador (espelha MargemTab); RAC já está em real_rec_q4
    _real_rec_sap = _sap_rec_total if _sap_rec_total > 0 else real_rec_q4
    _real_lb_sap  = sum(realized_lb_ws_dir.values())

    nexus_q4 = nexus[nexus["Periodo"].isin(Q4_PERIODOS)]
    if vertical and vertical in NEXUS_VERTICAL_MAP:
        nexus_verticals = NEXUS_VERTICAL_MAP[vertical]
        nq4_actual = nexus_q4[(nexus_q4["[Vertical]"].isin(nexus_verticals)) & (nexus_q4["[Tipo]"] == "Actual")]
        nq4_budget = nexus_q4[(nexus_q4["[Vertical]"].isin(nexus_verticals)) & (nexus_q4["[Tipo]"] == "Budget")]
    else:
        nq4_actual = pd.DataFrame()
        nq4_budget = pd.DataFrame()

    CUSTO_AGRUP   = ["Payroll costs", "Third-party costs", "Other costs"]
    DESPESA_AGRUP = ["Payroll expenses", "Deductions and taxes"]

    if not nq4_actual.empty:
        gross_rev        = float(nq4_actual[nq4_actual["Agrupador"] == "Gross revenue"]["[Valor]"].sum())
        real_payroll     = float(nq4_actual[nq4_actual["Agrupador"] == "Payroll costs"]["[Valor]"].sum())
        real_third_party = float(nq4_actual[nq4_actual["Agrupador"] == "Third-party costs"]["[Valor]"].sum())
        real_other_costs = float(nq4_actual[nq4_actual["Agrupador"] == "Other costs"]["[Valor]"].sum())
        real_payroll_exp = float(nq4_actual[nq4_actual["Agrupador"] == "Payroll expenses"]["[Valor]"].sum())
        real_deductions  = float(nq4_actual[nq4_actual["Agrupador"] == "Deductions and taxes"]["[Valor]"].sum())
        direct_costs = real_payroll + real_third_party + real_other_costs
        # Opção C: despesas pessoas proporcionais por receita SAP
        _total_desp_p  = d.get("total_despesa_pessoas_q4", 0.0)
        _total_dir_rac = d.get("total_dir_rac_q4", 0.0)
        despesas = _total_desp_p * (_real_rec_sap / _total_dir_rac) if _total_dir_rac else 0.0
        # MC% = (LB SAP + Despesas pessoas) / Receita SAP
        real_mc_pct = (_real_lb_sap + despesas) / _real_rec_sap if _real_rec_sap else 0.0
        # Diretor é responsável pela vertical inteira → usar nexus gross_rev como realizado
        if gross_rev > 0:
            real_rec_q4 = float(gross_rev)
            ating_rec = calc_atingimento(real_rec_q4, bgt_rec_q4, TRIGGER_REC_Q4)
    else:
        gross_rev = real_payroll = real_third_party = real_other_costs = 0.0
        real_payroll_exp = real_deductions = 0.0
        _total_desp_p  = d.get("total_despesa_pessoas_q4", 0.0)
        _total_dir_rac = d.get("total_dir_rac_q4", 0.0)
        despesas = _total_desp_p * (_real_rec_sap / _total_dir_rac) if _total_dir_rac else 0.0
        real_mc_pct = (_real_lb_sap + despesas) / _real_rec_sap if _real_rec_sap else 0.0

    # Budget MC%: bgt_lb / bgt_rec para a vertical
    # Para verticais sem linhas no budget_receita.csv, usa nexus Budget
    bgt_lb  = d["bgt_lb"]
    lb_dir  = bgt_lb[bgt_lb["bs"].str.lower() == bs_key.lower()] if (vertical and bs_key) else pd.DataFrame()
    bgt_lb_q4  = float(lb_dir["q4"].sum()) if not lb_dir.empty else 0.0
    bgt_gross = bgt_payroll = bgt_third_party = bgt_other_costs = bgt_payroll_exp = bgt_deductions = 0.0
    if bgt_rec_q4 == 0 and not nq4_budget.empty:
        bgt_gross        = float(nq4_budget[nq4_budget["Agrupador"] == "Gross revenue"]["[Valor]"].sum())
        bgt_payroll      = float(nq4_budget[nq4_budget["Agrupador"] == "Payroll costs"]["[Valor]"].sum())
        bgt_third_party  = float(nq4_budget[nq4_budget["Agrupador"] == "Third-party costs"]["[Valor]"].sum())
        bgt_other_costs  = float(nq4_budget[nq4_budget["Agrupador"] == "Other costs"]["[Valor]"].sum())
        bgt_payroll_exp  = float(nq4_budget[nq4_budget["Agrupador"] == "Payroll expenses"]["[Valor]"].sum())
        bgt_deductions   = float(nq4_budget[nq4_budget["Agrupador"] == "Deductions and taxes"]["[Valor]"].sum())
        bgt_direct = bgt_payroll + bgt_third_party + bgt_other_costs
        bgt_rec_q4 = float(bgt_gross)
        bgt_lb_q4  = float(bgt_gross + bgt_direct)
        ating_rec  = calc_atingimento(real_rec_q4, bgt_rec_q4, TRIGGER_REC_Q4)
    elif not lb_dir.empty:
        # Para verticais com dados no budget_lb.csv, busca também o breakdown do nexus budget
        bgt_gross       = float(nq4_budget[nq4_budget["Agrupador"] == "Gross revenue"]["[Valor]"].sum()) if not nq4_budget.empty else bgt_rec_q4
        bgt_payroll     = float(nq4_budget[nq4_budget["Agrupador"] == "Payroll costs"]["[Valor]"].sum()) if not nq4_budget.empty else 0.0
        bgt_third_party = float(nq4_budget[nq4_budget["Agrupador"] == "Third-party costs"]["[Valor]"].sum()) if not nq4_budget.empty else 0.0
        bgt_other_costs = float(nq4_budget[nq4_budget["Agrupador"] == "Other costs"]["[Valor]"].sum()) if not nq4_budget.empty else 0.0
        bgt_payroll_exp = float(nq4_budget[nq4_budget["Agrupador"] == "Payroll expenses"]["[Valor]"].sum()) if not nq4_budget.empty else 0.0
        bgt_deductions  = float(nq4_budget[nq4_budget["Agrupador"] == "Deductions and taxes"]["[Valor]"].sum()) if not nq4_budget.empty else 0.0
    _bgt_direct = bgt_payroll + bgt_third_party + bgt_other_costs
    # Budget MC% = (LB SAP budget + Despesas Nexus budget) / Receita SAP budget
    # Para diretores sem budget SAP (bgt_rec_q4 = Nexus gross), usa fórmula Nexus completa
    # MC absoluto (R$) — meta e realizado
    _bgt_mc_abs  = bgt_lb_q4 + bgt_payroll_exp + bgt_deductions
    _real_mc_abs = _real_lb_sap + despesas

    # Override: meta MC fixa por diretor (metas_mc_dir.csv)
    _mc_metas = d.get("mc_metas_dir", {})
    if nome_n in _mc_metas:
        _bgt_mc_abs = _mc_metas[nome_n]

    bgt_mc_pct = _bgt_mc_abs / bgt_rec_q4 if bgt_rec_q4 else 0.0

    # Gate: critério por valor absoluto (MC realizado >= 85% da meta)
    _trigger_mc_abs = _bgt_mc_abs * TRIGGER_REC_Q4
    mc_gate = 1.0 if _real_mc_abs >= _trigger_mc_abs else 0.0
    trigger_mc_pct_val = _trigger_mc_abs / bgt_rec_q4 if bgt_rec_q4 else 0.0

    # Atingimento: compara valor absoluto (R$), sem patamar mínimo (trigger=0)
    ating_mc = calc_atingimento(_real_mc_abs, _bgt_mc_abs, 0.0) if _bgt_mc_abs > 0 else 0.0

    # ─ WS breakdown — Parte 2: detalhe_ws_dir (bgt_lb_q4 já disponível) ─
    dir_ws_weights = d["pesos_ws_pessoa"].get(norm(str(pessoa["Nome"])), dict(WS_PESOS_Q4))
    detalhe_ws_dir = []
    bonus_rec_ws_total = 0.0
    for ws_k, _default_peso in WS_PESOS_Q4.items():
        peso_ws = dir_ws_weights.get(ws_k, _default_peso)
        bgt_r   = bgt_rec_ws.get(ws_k, 0.0)
        real_r  = realized_rec_ws_dir.get(ws_k, 0.0)
        # LB proporcional ao WS
        bgt_lb_ws  = bgt_r * (bgt_lb_q4 / bgt_rec_q4 if bgt_rec_q4 else 0.0)
        real_lb_ws = realized_lb_ws_dir.get(ws_k, 0.0)
        bgt_mb_pct_ws  = round(bgt_lb_ws  / bgt_r  * 100, 2) if bgt_r  > 0 else 0.0
        if real_r > 0:
            real_mb_pct_ws = round(real_lb_ws / real_r * 100, 2)
        else:
            real_mb_pct_ws = 0.0
        ating_r   = calc_atingimento(real_r, bgt_r, TRIGGER_REC_Q4) if bgt_r > 0 else 0.0
        ating_lb_ws = calc_atingimento(real_lb_ws, bgt_lb_ws, TRIGGER_REC_Q4) if bgt_lb_ws > 0 else 0.0
        bonus_ws  = round(Q4_QTDE * salario * peso_rec * peso_ws * ating_r, 2)
        bonus_rec_ws_total += bonus_ws
        detalhe_ws_dir.append({
            "ws":           ws_k,
            "peso_ws":      round(peso_ws, 4),
            "budget_rec":   round(bgt_r, 2),
            "real_rec":     round(real_r, 2),
            "ating_rec":    round(ating_r, 4),
            "bgt_lb_ws":    round(bgt_lb_ws, 2),
            "real_lb_ws":   round(real_lb_ws, 2),
            "budget_mb_pct": bgt_mb_pct_ws,
            "real_mb_pct":   real_mb_pct_ws,
            "ating_mb":      round(ating_lb_ws, 4),
            "bonus_ws":     bonus_ws,
        })

    # ─ LB absoluto (10%) ─
    real_lb_dir = sum(realized_lb_ws_dir.values())
    ating_lb_dir = calc_atingimento(real_lb_dir, bgt_lb_q4, TRIGGER_REC_Q4) if bgt_lb_q4 > 0 else 0.0

    # ─ Bônus ─
    if mc_gate == 0:
        bonus_tcv = 0.0
        bonus_rec = 0.0
        bonus_mc  = 0.0
        bonus_lb  = 0.0
        for ws in detalhe_ws_dir:
            ws["bonus_ws"] = 0.0
        bonus_rec_ws_total = 0.0
    else:
        bonus_tcv = Q4_QTDE * 1.0 * ating_tcv  * salario * peso_tcv
        bonus_rec = bonus_rec_ws_total
        bonus_mc  = Q4_QTDE * 1.0 * ating_mc   * salario * peso_mc
        bonus_lb  = Q4_QTDE * 1.0 * ating_lb_dir * salario * peso_lb

    bonus_total = bonus_tcv + bonus_rec + bonus_mc + bonus_lb

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
        "peso_lb":       peso_lb,
        "budget_lb_q4":      round(bgt_lb_q4, 2),
        "real_lb_q4":        round(real_lb_dir, 2),
        "ating_lb":          round(ating_lb_dir, 4),
        "bonus_lb":          round(bonus_lb, 2),
        "budget_tcv_q4":     round(bgt_tcv_q4, 2),
        "real_tcv_q4":       round(real_tcv_q4, 2),
        "ating_tcv":         round(ating_tcv, 4),
        "budget_rec_q4":     round(bgt_rec_q4, 2),
        "real_rec_q4":       round(real_rec_q4, 2),
        "real_rec_sap":      round(_real_rec_sap, 2),   # rec SAP para display MB/MC
        "ating_rec":         round(ating_rec, 4),
        "budget_mc_pct":     round(bgt_mc_pct * 100, 2),
        "trigger_mc_pct":    round(trigger_mc_pct_val * 100, 2),
        "real_mc_pct":       round(real_mc_pct * 100, 2),
        "budget_mc_abs":     round(_bgt_mc_abs, 2),
        "trigger_mc_abs":    round(_trigger_mc_abs, 2),
        "real_mc_abs":       round(_real_mc_abs, 2),
        "real_mb_pct":       round(_real_lb_sap / _real_rec_sap * 100, 2) if _real_rec_sap else 0.0,
        "ating_mc":          round(ating_mc, 4),
        # Breakdown custos/despesas para auditoria do MC%
        "real_gross_rev":       round(gross_rev, 2),
        "real_payroll":         round(real_payroll, 2),
        "real_third_party":     round(real_third_party, 2),
        "real_other_costs":     round(real_other_costs, 2),
        "real_payroll_exp":     round(real_payroll_exp, 2),
        "real_deductions":      round(real_deductions, 2),
        "real_despesa_pessoas": round(despesas, 2),
        "bgt_gross_rev":        round(bgt_gross, 2),
        "bgt_payroll":          round(bgt_payroll, 2),
        "bgt_third_party":      round(bgt_third_party, 2),
        "bgt_other_costs":      round(bgt_other_costs, 2),
        "bgt_payroll_exp":      round(bgt_payroll_exp, 2),
        "bgt_deductions":       round(bgt_deductions, 2),
        "bonus_tcv":         round(bonus_tcv, 2),
        "bonus_rec":         round(bonus_rec, 2),
        "bonus_mc":          round(bonus_mc, 2),
        "bonus_lb":          round(bonus_lb, 2),
        "bonus_total":       round(bonus_total, 2),
        "detalhe_ws":        detalhe_ws_dir,
        "clientes_detalhe":  clientes_detalhe_dir,
    }


# ─── AE → Vertical lookup via clientes.csv ────────────────────────────────────

def _ae_vertical_lookup() -> dict:
    """
    Builds {norm(ae_name): 'vertical1/vertical2'} from parametros.xlsx/clientes.
    Also indexes by first word (nickname) for partial matching.
    """
    path = os.path.join(DIR, "parametros.xlsx")
    if not os.path.exists(path):
        return {}
    try:
        df = pd.read_excel(path, sheet_name="clientes", dtype=str).fillna("")
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


# ─── Metas Anuais ────────────────────────────────────────────────────────────

_METAS_XLSX_PATH   = os.path.join(DIR, "parametros.xlsx")
_PERIODOS_ANUAIS   = ["Q1Y25", "Q2Y25", "Q3Y25"]  # Q4 calculado pelo engine

# Tipos de margem por grupo
_TIPOS_LB  = {"lb", "mb%"}   # AEs Finance/Health/Multisector
_TIPOS_MC  = {"mc", "mc%"}   # Diretores e Retail

@lru_cache(maxsize=1)
def _load_metas_anuais() -> pd.DataFrame:
    if not os.path.exists(_METAS_XLSX_PATH):
        return pd.DataFrame()
    df = pd.ExcelFile(_METAS_XLSX_PATH).parse("anuais")
    df["nome_norm"]   = df["nome"].apply(norm)
    df["periodo"]     = df["periodo"].str.upper().str.strip()
    df["meta_tipo_n"] = df["meta_tipo"].str.lower().str.strip()
    return df


def _safe_float(v, default=0.0) -> float:
    """Converte valor para float, retornando default para None/NaN/string vazia."""
    import math
    try:
        f = float(v) if v is not None and str(v).strip() != "" else default
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def _pesos_anuais() -> dict:
    """Retorna dict posicao_upper → {rec, lb_mb, tcv} para período Anual."""
    df = pd.ExcelFile(os.path.join(DIR, "parametros.xlsx")).parse("pesos_meta")
    anual = df[df["Periodo"].str.lower() == "anual"]
    result = {}
    for _, row in anual.iterrows():
        pos = str(row["Posicao"]).upper().strip()
        result[pos] = {
            "rec":   _safe_float(row.get("Receita")),
            "lb_mb": _safe_float(row.get("MB_pct")),
            "mc":    _safe_float(row.get("MC_pct")),
            "tcv":   _safe_float(row.get("TCV")),
        }
    return result


def calc_bonus_anual(nome: str, posicao: str, salario: float,
                     q4_rec_real: float, q4_rec_meta: float,
                     q4_lb_real: float = 0, q4_lb_meta: float = 0) -> dict:
    """
    Calcula bônus anual (Q1+Q2+Q3 do CSV + Q4 do engine).
    Inclui Receita e LB/MB% (AEs) ou MC/MC% (Diretores).
    Valor cheio = 3 × salário × atingimento_anual
    """
    df_all = _load_metas_anuais()
    nome_n = norm(nome)

    if df_all.empty:
        return {"disponivel": False}

    pessoa_all = df_all[df_all["nome_norm"] == nome_n]
    if pessoa_all.empty:
        primeiro = nome_n.split()[0]
        pessoa_all = df_all[df_all["nome_norm"].str.startswith(primeiro)]
    if pessoa_all.empty:
        return {"disponivel": False}

    # Detecta qual tipo de margem a pessoa usa (LB/MB% ou MC/MC%)
    tipos_presentes = set(pessoa_all["meta_tipo_n"].unique())
    usa_mc = bool(tipos_presentes & _TIPOS_MC)
    tipo_lb_key  = "mc"   if usa_mc else "lb"
    tipos_lb_set = _TIPOS_MC if usa_mc else _TIPOS_LB
    label_lb     = "MC"   if usa_mc else "LB"

    # Pesos anuais
    pos_up = posicao.upper().strip()
    pesos  = _pesos_anuais().get(pos_up, {"rec": 0.5, "lb_mb": 0.4, "mc": 0.0, "tcv": 0.0})
    peso_rec  = pesos["rec"]
    peso_lb   = pesos["mc"] if usa_mc else pesos["lb_mb"]

    trimestres = []
    for per in _PERIODOS_ANUAIS:
        # Receita (ws != "Total")
        rec_rows = pessoa_all[(pessoa_all["periodo"] == per) &
                              (pessoa_all["meta_tipo_n"] == "receita") &
                              (pessoa_all["ws"].str.lower() != "total")]
        # LB/MC — linha Total (ws == "Total")
        lb_rows  = pessoa_all[(pessoa_all["periodo"] == per) &
                              (pessoa_all["meta_tipo_n"].isin(tipos_lb_set)) &
                              (pessoa_all["ws"].str.lower() == "total") &
                              (pessoa_all["meta_tipo_n"] != "mb%") &   # usa LB amount, não pct
                              (pessoa_all["meta_tipo_n"] != "mc%")]    # usa MC amount, não pct
        if rec_rows.empty:
            continue

        rec_meta = float(rec_rows["meta"].sum())
        rec_real = float(rec_rows["realizado"].sum())
        lb_meta  = float(lb_rows["meta"].sum())  if not lb_rows.empty else 0.0
        lb_real  = float(lb_rows["realizado"].sum()) if not lb_rows.empty else 0.0
        mb_meta  = round(lb_meta / rec_meta * 100, 2) if rec_meta > 0 else None
        mb_real  = round(lb_real / rec_real * 100, 2) if rec_real > 0 else None
        sal_row  = float(rec_rows["salario"].iloc[0])

        trimestres.append({
            "periodo":   per,
            "rec_meta":  round(rec_meta, 2),
            "rec_real":  round(rec_real, 2),
            "lb_meta":   round(lb_meta, 2),
            "lb_real":   round(lb_real, 2),
            "mb_meta":   mb_meta,
            "mb_real":   mb_real,
            "salario":   round(sal_row, 2),
        })

    # Q4 vindo do engine
    q4_mb_meta = round(q4_lb_meta / q4_rec_meta * 100, 2) if q4_rec_meta > 0 else None
    q4_mb_real = round(q4_lb_real / q4_rec_real * 100, 2) if q4_rec_real > 0 else None
    trimestres.append({
        "periodo":  "Q4Y25",
        "rec_meta": round(q4_rec_meta, 2),
        "rec_real": round(q4_rec_real, 2),
        "lb_meta":  round(q4_lb_meta, 2),
        "lb_real":  round(q4_lb_real, 2),
        "mb_meta":  q4_mb_meta,
        "mb_real":  q4_mb_real,
        "salario":  round(salario, 2),
    })

    # Totais anuais
    total_rec_meta = sum(t["rec_meta"] for t in trimestres)
    total_rec_real = sum(t["rec_real"] for t in trimestres)
    total_lb_meta  = sum(t["lb_meta"]  for t in trimestres)
    total_lb_real  = sum(t["lb_real"]  for t in trimestres)

    # Atingimentos anuais
    ating_rec = calc_atingimento(total_rec_real, total_rec_meta, 0.85)

    total_mb_meta = total_lb_meta / total_rec_meta if total_rec_meta > 0 else 0
    total_mb_real = total_lb_real / total_rec_real if total_rec_real > 0 else 0
    ating_lb  = calc_atingimento_mb(total_mb_real, total_mb_meta, MB_TRIGGER_DELTA) if total_mb_meta > 0 else 0.0

    # Gatilho mestre anual: LB/MC deve atingir 85% da meta anual (mesmo critério do Q4)
    lb_trigger_anual = total_lb_meta * TRIGGER_REC_Q4
    lb_gate = 1 if (total_lb_meta <= 0 or total_lb_real >= lb_trigger_anual) else 0

    ating_anual = peso_rec * ating_rec + peso_lb * ating_lb
    bonus_anual = round(3 * salario * ating_anual * lb_gate, 2)

    return {
        "disponivel":    True,
        "label_lb":      label_lb,
        "lb_gate":          lb_gate,
        "lb_trigger_anual": round(lb_trigger_anual, 2),
        "trimestres":    trimestres,
        "total_rec_meta": round(total_rec_meta, 2),
        "total_rec_real": round(total_rec_real, 2),
        "total_lb_meta":  round(total_lb_meta, 2),
        "total_lb_real":  round(total_lb_real, 2),
        "total_mb_meta":  round(total_mb_meta * 100, 2),
        "total_mb_real":  round(total_mb_real * 100, 2),
        "ating_rec":      round(ating_rec, 4),
        "ating_lb":       round(ating_lb, 4),
        "peso_rec":       peso_rec,
        "peso_lb":        peso_lb,
        "ating_anual":    round(ating_anual, 4),
        "bonus_anual":    bonus_anual,
        "salario":        round(salario, 2),
    }


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
                q4_mc_real = res.get("real_mc_abs") or (res["real_mc_pct"] / 100 * res["real_rec_q4"] if res.get("real_mc_pct") else 0)
                q4_mc_meta = res.get("budget_mc_abs") or (res["budget_mc_pct"] / 100 * res["budget_rec_q4"] if res.get("budget_mc_pct") else 0)
                anual = calc_bonus_anual(nome, pos, res["salario_q4"],
                                         res["real_rec_q4"], res["budget_rec_q4"],
                                         q4_mc_real, q4_mc_meta)
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
                    "pct_mc":   round(res["real_mc_abs"] / res["budget_mc_abs"], 4) if res.get("budget_mc_abs") else 0,
                    "mc_gate":   res["mc_gate"],
                    "gate_ok":   res["mc_gate"] == 1.0,
                    "tipo_calc": "Diretor",
                    "bonus_anual":  anual.get("bonus_anual"),
                    "ating_anual":  anual.get("ating_anual"),
                    "anual_ok":     anual.get("disponivel", False),
                })
            elif pos in ("AE", "AE_GM", "AE2", "HUNTER", "ESTRATEGISTAS", "CS"):
                res = calc_bonus_ae(nome)
                bgt_r = res["budget_rec_total"] or 1
                bgt_m = res["budget_mb_pct"] or 1
                nome_n_vis = norm(nome)
                vertical_ae = "Grupo Mult" if pos == "AE_GM" else (AE_BS_OVERRIDE.get(nome_n_vis) or _resolve_vertical_for_ae(nome, ae_vert))
                q4_lb_meta = res["budget_mb_pct"] / 100 * res["budget_rec_total"] if res.get("budget_mb_pct") else 0
                anual = calc_bonus_anual(nome, pos, res["salario_q4"],
                                         res["real_rec_total"], res["budget_rec_total"],
                                         res.get("real_lb_total", 0), q4_lb_meta)
                bgt_tcv = res.get("budget_tcv_q4") or 0
                real_tcv = res.get("real_tcv_q4") or 0
                resultados.append({
                    "nome":     res["nome"],
                    "posicao":  res["posicao"],
                    "contrato": res["contrato"],
                    "vertical": vertical_ae,
                    "salario":  res["salario_q4"],
                    "bonus":    res["bonus_total"],
                    "ating_principal": res["ating_rec_total"],
                    "ating_rec":  res["ating_rec_total"],
                    "ating_mb":   res["ating_mb_total"],
                    "ating_tcv":  res.get("ating_tcv"),
                    "ating_mc":   None,
                    "pct_rec":  round(res["real_rec_total"] / bgt_r, 4),
                    "pct_mb":   round(res["real_mb_pct"] / bgt_m, 4) if bgt_m else 0,
                    "pct_tcv":  round(real_tcv / bgt_tcv, 4) if bgt_tcv else None,
                    "pct_mc":   None,
                    "mc_gate":    None,
                    "gate_ok":    bool(res.get("lb_gate", 1)),
                    "tipo_calc":  "Comercial",
                    "bonus_anual":  anual.get("bonus_anual"),
                    "ating_anual":  anual.get("ating_anual"),
                    "anual_ok":     anual.get("disponivel", False),
                })
        except Exception as e:
            nome_n_err = norm(nome)
            resultados.append({
                "nome":     nome,
                "posicao":  pos,
                "contrato": str(p.get("Contrato", "")),
                "vertical": AE_BS_OVERRIDE.get(nome_n_err) or _resolve_vertical_for_ae(nome, ae_vert),
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


# ─── Visão Master Q3 (apenas AE_GM) ──────────────────────────────────────────

def get_visao_master_q3() -> list[dict]:
    """Retorna visão consolidada Q3 para AE_GM (Grupo Mult)."""
    d = _load_all()
    pessoas = d["pessoas"]
    resultados = []

    # Inclui AE_GM + AEs que têm budget Q3 no Grupo Mult (ex: Danilo — AE sem TCV)
    bgt_rec_q3 = d["bgt_rec"]
    ae_com_budget_q3_gm = set(
        bgt_rec_q3[
            (bgt_rec_q3["bs"].str.upper().str.strip() == "GRUPO MULT") &
            (bgt_rec_q3["q3"].fillna(0) > 0)
        ]["ae_q3"].apply(lambda x: str(x).strip().upper())
    )
    ae_gm = pessoas[
        (pessoas["Posicao"].str.upper().str.strip() == "AE_GM") |
        (pessoas["Posicao"].str.upper().str.strip() == "AE") & pessoas["Nome"].apply(lambda x: str(x).strip().upper()).isin(ae_com_budget_q3_gm)
    ]

    for _, p in ae_gm.iterrows():
        nome = p["Nome"]
        sal  = float(p.get("Sal_Q3") or 0)
        try:
            res  = calc_bonus_ae_q3(nome)
            bgt_r = res["budget_rec_total"] or 1
            bgt_m = res["budget_mb_pct"] or 1
            resultados.append({
                "nome":     res["nome"],
                "posicao":  res["posicao"],
                "contrato": res["contrato"],
                "vertical": "Grupo Mult",
                "salario":  res["salario_q4"],
                "bonus":    res["bonus_total"],
                "ating_rec":  res["ating_rec_total"],
                "ating_mb":   res["ating_mb_total"],
                "ating_tcv":  res.get("ating_tcv"),
                "pct_rec":  round(res["real_rec_total"] / bgt_r, 4),
                "pct_mb":   round(res["real_mb_pct"] / bgt_m, 4) if bgt_m else 0,
                "pct_tcv":  round(res["real_tcv_q4"] / res["budget_tcv_q4"], 4)
                            if res.get("budget_tcv_q4") else None,
                "gate_ok":  bool(res.get("lb_gate", 1)),
                "tipo_calc": "Comercial",
            })
        except Exception as e:
            resultados.append({
                "nome":     nome,
                "posicao":  "AE_GM",
                "contrato": str(p.get("Contrato", "")),
                "vertical": "Grupo Mult",
                "salario":  sal,
                "bonus":    0.0,
                "ating_rec":  0.0,
                "ating_mb":   None,
                "ating_tcv":  None,
                "pct_rec":  None,
                "pct_mb":   None,
                "pct_tcv":  None,
                "gate_ok":  False,
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

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
import bcrypt
import pandas as pd
import gdown
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ───────────────────────────────────────────────────────────────────────

SECRET_KEY = "wk_secret_key_2024_react"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 480

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

USERS = {
    "amanda": {"name": "Amanda", "hashed_password": "$2b$12$mfHiyBw/auw.B745JxG2eO5Qlw/urUAOOVwi5x2koGXqWhUDhZv/a"},
    "paola":  {"name": "Paola",  "hashed_password": "$2b$12$RWwqeh1tC5HC9flxYsR3s.a8RyTyCuDcsksRvtnI9K4DbwbKIR5KC"},
    "yuri":   {"name": "Yuri",   "hashed_password": "$2b$12$lafxeoNomlDKRwz5seUPUe72xx06URZiuxTx2vbhJ6pFVy1HQpuhG"},
}

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_token(username: str):
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username not in USERS:
            raise HTTPException(status_code=401)
        return username
    except JWTError:
        raise HTTPException(status_code=401)

@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = USERS.get(form.username)
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos")
    return {"access_token": create_token(form.username), "token_type": "bearer"}

# ── Cache em memória ───────────────────────────────────────────────────────────

_cache: dict = {"df": None, "nomes": None, "sap": None, "nexus": None, "clt": None}
_ready: dict = {"sap": False, "nexus": False}

CLT_FOLDER_ID = "1aEHQAARXkf_BZbc5j0Z8Tt0s5Fmk6tSu"
CLT_SHEETS    = ["FC", "NX", "HY", "DOJO", "ND", "SGA"]
CLT_MONTHS_PT = ["janeiro","fevereiro","março","abril","maio","junho",
                 "julho","agosto","setembro","outubro","novembro","dezembro"]
CLT_MONTHS_BR = ["Jan","Fev","Mar","Abr","Mai","Jun",
                 "Jul","Ago","Set","Out","Nov","Dez"]

WORKER_ID   = "13ORJ-dpxKXVF6sVy3Ex0Fp-hOLhxM8H_"
PERSONAL_ID = "1qXu1bjWKqL3tNMYUAFjoMSiSle417WPF"
SAP_ID      = "1Lm-G9ZJUC2Hzc9iIKIb6LCemYJqtzNQO"
NEXUS_ID    = "1BBjfSYTGLAeuxMih4CDMgyfmVDGfkxkW"

COMPANY_NAMES = {
    "BR02": "FCamara", "BRO2": "FCamara",
    "BR03": "Dojo",
    "BR04": "Nação Digital",
    "BR05": "SGA", "BR06": "Dojo",
    "BR07": "Hyper", "BR0C": "Hyper",
    "BR08": "Omnik",
    "BR09": "NextGen",
}
SAP_NAMES = {"BR02": "FCamara", "BR07": "Hyper", "BR09": "NextGen"}

def get_nomes() -> dict:
    if _cache["nomes"] is None:
        if not os.path.exists("personaldata.xlsx"):
            gdown.download(id=PERSONAL_ID, output="personaldata.xlsx", quiet=True)
        df = pd.read_excel("personaldata.xlsx", sheet_name="YY1_FCTEAM5_PERSONEW",
                           usecols=["ID Number", "Full Name"])
        df = df.dropna(subset=["ID Number"]).drop_duplicates("ID Number")
        _cache["nomes"] = dict(zip(df["ID Number"].astype(str), df["Full Name"]))
    return _cache["nomes"]

def get_df() -> pd.DataFrame:
    if _cache["df"] is None:
        if not os.path.exists("worker.xlsx"):
            gdown.download(id=WORKER_ID, output="worker.xlsx", quiet=True)
        df = pd.read_excel("worker.xlsx", sheet_name="receita_worker")
        df["lucro_bruto"] = df["receita_liquida"] - df["cost"]
        _cache["df"] = df
    return _cache["df"]

def get_sap() -> pd.DataFrame:
    mtime = os.path.getmtime("sap_agg.csv")
    if _cache["sap"] is None or _cache.get("sap_mtime") != mtime:
        print("Carregando sap_agg.csv...")
        df = pd.read_csv("sap_agg.csv")
        df["CompanyCode"] = df["CompanyCode"].map(COMPANY_NAMES).fillna(df["CompanyCode"])
        for col in ["CompanyCode", "agrupador_fpa", "vertical", "ProfitCenter"]:
            if col in df.columns:
                df[col] = df[col].astype("category")
        df["AmountInCompanyCodeCurrency"] = df["AmountInCompanyCodeCurrency"].astype("float32")
        print(f"SAP carregado: {len(df)} linhas")
        _cache["sap"] = df
        _cache["sap_mtime"] = mtime
    return _cache["sap"]

def get_nexus() -> pd.DataFrame:
    mtime = os.path.getmtime("nexus_agg.csv")
    if _cache["nexus"] is None or _cache.get("nexus_mtime") != mtime:
        print("Carregando nexus_agg.csv...")
        df = pd.read_csv("nexus_agg.csv")
        df = df.rename(columns={"Agrupador": "[Agrupador FP&A - COA]", "Periodo": "Período"})
        if "Ano" in df.columns:
            df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce").astype("Int16")
        df["[Valor]"] = df["[Valor]"].astype("float32")
        for col in ["[Tipo]", "[Moeda]", "[Empresa]", "[Vertical]", "[Stream]",
                    "[Agrupador FP&A - COA]", "Período"]:
            if col in df.columns:
                df[col] = df[col].astype("category")
        print(f"Nexus carregado: {len(df)} linhas")
        print(f"  Tipos: {df['[Tipo]'].dropna().unique().tolist()}")
        print(f"  Moedas: {df['[Moeda]'].dropna().unique().tolist()}")
        _cache["nexus"] = df
        _cache["nexus_mtime"] = mtime
    return _cache["nexus"]

def get_clt() -> dict:
    """Returns {mes_label: {empresa: total_totalizador}}"""
    if _cache["clt"] is None:
        import subprocess, sys, glob, re
        os.makedirs("clt_files", exist_ok=True)
        subprocess.run(
            [sys.executable, "-c",
             f"import gdown; gdown.download_folder(id='{CLT_FOLDER_ID}', output='clt_files', quiet=False)"],
            capture_output=True, text=True, timeout=300
        )
        result: dict = {}
        for filepath in glob.glob("clt_files/**/*", recursive=True):
            if os.path.isdir(filepath):
                continue
            fn = os.path.basename(filepath).lower()
            month_label = None
            for i, m in enumerate(CLT_MONTHS_PT):
                if m in fn:
                    year_match = re.search(r'20\d\d', fn)
                    year = year_match.group(0) if year_match else "2026"
                    month_label = f"{CLT_MONTHS_BR[i]}/{year}"
                    break
            if not month_label:
                continue
            month_data: dict = {}
            for sheet in CLT_SHEETS:
                try:
                    df = pd.read_excel(filepath, sheet_name=sheet)
                    col = next((c for c in df.columns if "totalizador" in str(c).lower()), None)
                    if col:
                        month_data[sheet] = float(pd.to_numeric(df[col], errors="coerce").sum())
                except Exception:
                    pass
            if month_data:
                result[month_label] = month_data
        _cache["clt"] = result
    return _cache["clt"]

def _preload_heavy():
    try:
        print("Carregando SAP...")
        get_sap()
        _ready["sap"] = True
        sap = get_sap()
        print(f"SAP carregado. Rows={len(sap)}, agrupadores={sap['agrupador_fpa'].dropna().unique().tolist()[:5]}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"Erro ao carregar SAP: {e}")
    try:
        print("Carregando Nexus...")
        get_nexus()
        _ready["nexus"] = True
        nx = get_nexus()
        print(f"Nexus carregado. Rows={len(nx)}, cols={list(nx.columns)}")
        print(f"  Tipos: {nx['[Tipo]'].dropna().unique().tolist()}")
        print(f"  Moedas: {nx['[Moeda]'].dropna().unique().tolist()}")
        print(f"  Empresas: {nx['[Empresa]'].dropna().unique().tolist()}")
        print(f"  Anos: {sorted(nx['Ano'].dropna().unique().tolist())}")
        print("Servidor pronto.")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"Erro ao carregar Nexus: {e}")

@app.on_event("startup")
async def startup():
    print("Carregando Worker...")
    get_df()
    get_nomes()
    print("Worker carregado. Iniciando carregamento pesado em background...")
    import threading
    threading.Thread(target=_preload_heavy, daemon=True).start()

# ── P&L Engine ─────────────────────────────────────────────────────────────────

COSTS_ITEMS = ["Payroll costs", "Third-party costs", "Licenses and infrastructure costs", "Other costs"]
SGA_ITEMS = [
    "Payroll expenses", "Third-party expenses", "Commission expenses",
    "Marketing and selling expenses", "General and administrative expenses",
    "Consulting expenses", "Occupancy expenses", "Travel expenses",
    "Tax expenses", "Other operating income (expenses) net",
]
SUBTOTALS = {"Net revenue", "Total costs", "Gross profit", "Gross margin %", "Total SG&A", "EBITDA", "EBITDA %"}
PCT_ROWS = {"Gross margin %", "EBITDA %"}
PL_ORDER = [
    "Gross revenue", "Deductions and taxes", "Net revenue",
    "Payroll costs", "Third-party costs", "Licenses & infra costs", "Other costs", "Total costs",
    "Gross profit", "Gross margin %",
    "Payroll expenses", "Third-party expenses", "Commission expenses",
    "Marketing & selling exp.", "G&A expenses", "Consulting expenses",
    "Occupancy expenses", "Travel expenses", "Tax expenses", "Other operating net",
    "Total SG&A", "EBITDA", "EBITDA %",
]
LABEL_MAP = {
    "Licenses & infra costs":   "Licenses and infrastructure costs",
    "Marketing & selling exp.": "Marketing and selling expenses",
    "G&A expenses":             "General and administrative expenses",
    "Other operating net":      "Other operating income (expenses) net",
}

def compute_pl(df, col_group):
    piv = df.pivot_table(
        index="[Agrupador FP&A - COA]", columns=col_group,
        values="[Valor]", aggfunc="sum", fill_value=0,
    )
    cols = list(piv.columns)

    def g(label):
        raw = LABEL_MAP.get(label, label)
        return piv.loc[raw].copy() if raw in piv.index else pd.Series(0.0, index=cols)

    gross   = g("Gross revenue")
    deduct  = g("Deductions and taxes")
    net_rev = gross + deduct
    costs   = sum(g(c) for c in COSTS_ITEMS)
    gp      = net_rev + costs
    sga     = sum(g(s) for s in SGA_ITEMS)
    ebitda  = gp + sga
    safe    = net_rev.replace(0, float("nan"))

    data = {
        "Gross revenue": gross, "Deductions and taxes": deduct, "Net revenue": net_rev,
        "Payroll costs": g("Payroll costs"), "Third-party costs": g("Third-party costs"),
        "Licenses & infra costs": g("Licenses & infra costs"), "Other costs": g("Other costs"),
        "Total costs": costs, "Gross profit": gp, "Gross margin %": (gp / safe).fillna(0),
        "Payroll expenses": g("Payroll expenses"), "Third-party expenses": g("Third-party expenses"),
        "Commission expenses": g("Commission expenses"), "Marketing & selling exp.": g("Marketing & selling exp."),
        "G&A expenses": g("G&A expenses"), "Consulting expenses": g("Consulting expenses"),
        "Occupancy expenses": g("Occupancy expenses"), "Travel expenses": g("Travel expenses"),
        "Tax expenses": g("Tax expenses"), "Other operating net": g("Other operating net"),
        "Total SG&A": sga, "EBITDA": ebitda, "EBITDA %": (ebitda / safe).fillna(0),
    }

    result = pd.DataFrame(data).T
    result.columns = cols
    result = result.loc[PL_ORDER]
    result["Total"] = result.sum(axis=1)
    nr_t = result.loc["Net revenue", "Total"]
    result.loc["Gross margin %", "Total"] = result.loc["Gross profit", "Total"] / nr_t if nr_t else 0
    result.loc["EBITDA %", "Total"] = result.loc["EBITDA", "Total"] / nr_t if nr_t else 0
    return result

def pl_to_json(result):
    rows = []
    for row_name in result.index:
        is_pct = row_name in PCT_ROWS
        is_subtotal = row_name in SUBTOTALS
        row = {
            "name": row_name,
            "is_subtotal": is_subtotal,
            "is_pct": is_pct,
            "values": {str(col): float(result.loc[row_name, col]) for col in result.columns},
        }
        rows.append(row)
    return {"rows": rows, "columns": [str(c) for c in result.columns]}

# ── Worker endpoints ───────────────────────────────────────────────────────────

def apply_filters(df, competencias="", sap_code="", client_name="", project_id="", worker_id=""):
    if competencias:
        df = df[df["competencia"].isin(competencias.split(","))]
    if sap_code:
        df = df[df["sap_code"] == sap_code]
    if client_name:
        df = df[df["client_name"] == client_name]
    if project_id:
        df = df[df["project_id"] == project_id]
    if worker_id:
        df = df[df["worker_id"] == worker_id]
    return df

@app.get("/api/competencias")
def get_competencias(user=Depends(get_current_user)):
    return sorted(get_df()["competencia"].dropna().unique().tolist())

@app.get("/api/kpis")
def get_kpis(competencias="", sap_code="", client_name="", project_id="", worker_id="",
             user=Depends(get_current_user)):
    df = apply_filters(get_df(), competencias, sap_code, client_name, project_id, worker_id)
    rl = df["receita_liquida"].sum()
    lb = df["lucro_bruto"].sum()
    return {
        "receita_bruta":   float(df["receita_bruta"].sum()),
        "receita_liquida": float(rl),
        "custo":           float(df["cost"].sum()),
        "lucro_bruto":     float(lb),
        "margem_bruta":    float(lb / rl) if rl else 0,
    }

@app.get("/api/metricas")
def get_metricas(level: str, competencias="", sap_code="", client_name="", project_id="",
                 user=Depends(get_current_user)):
    df = apply_filters(get_df(), competencias, sap_code, client_name, project_id)
    agg = {"receita_bruta": ("receita_bruta","sum"), "receita_liquida": ("receita_liquida","sum"),
           "custo": ("cost","sum"), "lucro_bruto": ("lucro_bruto","sum")}
    if level == "worker_id":
        df = df.copy()
        df["_gm"] = df["gross_margin"] * df["receita_liquida"]
        agg["_gm"] = ("_gm", "sum")
    g = df.groupby(level, as_index=False).agg(**agg)
    safe_rl = g["receita_liquida"].replace(0, float("nan"))
    if level == "worker_id":
        g["margem_bruta"] = g["_gm"] / safe_rl
        g = g.drop(columns=["_gm"])
        nomes = get_nomes()
        g["nome"] = g[level].astype(str).map(nomes).fillna(g[level])
    else:
        g["margem_bruta"] = g["lucro_bruto"] / safe_rl
        g["nome"] = g[level].map(SAP_NAMES).fillna(g[level]) if level == "sap_code" else g[level]
    g = g.sort_values("receita_bruta", ascending=False)
    total_rl = g["receita_liquida"].sum()
    total_lb = g["lucro_bruto"].sum()
    total_gm = (
        (g["margem_bruta"] * g["receita_liquida"]).sum() / total_rl
        if level == "worker_id" and total_rl else
        total_lb / total_rl if total_rl else 0
    )
    total_row = {level: "Total", "nome": "Total",
                 "receita_bruta": g["receita_bruta"].sum(), "receita_liquida": total_rl,
                 "custo": g["custo"].sum(), "lucro_bruto": total_lb, "margem_bruta": total_gm}
    result = pd.concat([pd.DataFrame([total_row]), g], ignore_index=True)
    return result.fillna(0).to_dict(orient="records")

@app.get("/api/mensal")
def get_mensal(competencias="", sap_code="", client_name="", project_id="", worker_id="",
               user=Depends(get_current_user)):
    df = apply_filters(get_df(), competencias, sap_code, client_name, project_id, worker_id)
    m = df.groupby("competencia", as_index=False).agg(
        receita_bruta=("receita_bruta","sum"), custo=("cost","sum"),
        receita_liquida=("receita_liquida","sum"), lucro_bruto=("lucro_bruto","sum"),
    )
    m["margem_bruta"] = m["lucro_bruto"] / m["receita_liquida"].replace(0, float("nan"))
    m = m.sort_values("competencia").fillna(0)
    total_rl = m["receita_liquida"].sum()
    total_lb = m["lucro_bruto"].sum()
    total_row = {"competencia": "Total", "receita_bruta": m["receita_bruta"].sum(),
                 "custo": m["custo"].sum(), "receita_liquida": total_rl,
                 "lucro_bruto": total_lb, "margem_bruta": total_lb / total_rl if total_rl else 0}
    result = pd.concat([pd.DataFrame([total_row]), m], ignore_index=True)
    return result.to_dict(orient="records")

# ── SAP endpoints ──────────────────────────────────────────────────────────────

@app.get("/api/sap/filters")
def get_sap_filters(user=Depends(get_current_user)):
    if not _ready["sap"]:
        raise HTTPException(status_code=503, detail="SAP ainda carregando, aguarde...")
    try:
        df = get_sap()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar SAP: {e}")
    return {
        "companies": sorted(df["CompanyCode"].dropna().unique().tolist()),
        "verticals": sorted(df["vertical"].dropna().unique().tolist()),
        "profit_centers": sorted(df["ProfitCenter"].dropna().unique().tolist()),
    }

@app.get("/api/sap/data")
def get_sap_data(companies="", verticals="", profit_centers="", user=Depends(get_current_user)):
    if not _ready["sap"]:
        raise HTTPException(status_code=503, detail="SAP ainda carregando, aguarde...")
    df = get_sap()
    if companies:
        df = df[df["CompanyCode"].isin(companies.split(","))]
    if verticals:
        df = df[df["vertical"].isin(verticals.split(","))]
    if profit_centers:
        df = df[df["ProfitCenter"].isin(profit_centers.split(","))]

    pivot = df.pivot_table(
        index="agrupador_fpa", columns="FiscalPeriod",
        values="AmountInCompanyCodeCurrency", aggfunc="sum", fill_value=0,
    )
    pivot.columns = [f"Mês {int(c)}" for c in pivot.columns]
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.reset_index()
    return {
        "columns": list(pivot.columns),
        "data": pivot.to_dict(orient="records"),
    }

# ── Debug endpoint ─────────────────────────────────────────────────────────────

@app.get("/api/debug/nexus")
def debug_nexus(user=Depends(get_current_user)):
    if not _ready["nexus"]:
        return {"status": "not_ready"}
    df = get_nexus()
    tipos  = df["[Tipo]"].dropna().astype(str).unique().tolist()   if "[Tipo]"    in df.columns else []
    moedas = df["[Moeda]"].dropna().astype(str).unique().tolist()  if "[Moeda]"   in df.columns else []
    empresas = df["[Empresa]"].dropna().astype(str).unique().tolist() if "[Empresa]" in df.columns else []
    anos   = sorted(df["Ano"].dropna().astype(int).unique().tolist()) if "Ano" in df.columns else []
    df_act = _filter_nexus(df, tipo="Actual")
    sample = df.head(3).astype(str).to_dict(orient="records") if len(df) > 0 else []
    return {
        "status": "ready",
        "total_rows": len(df),
        "columns": list(df.columns),
        "tipos": tipos,
        "moedas": moedas,
        "empresas": empresas,
        "anos": anos,
        "rows_after_actual_filter": len(df_act),
        "sample": sample,
    }

# ── Nexus endpoints ────────────────────────────────────────────────────────────

@app.get("/api/nexus/filters")
def get_nexus_filters(user=Depends(get_current_user)):
    if not _ready["nexus"]:
        raise HTTPException(status_code=503, detail="Nexus ainda carregando, aguarde...")
    try:
        df = get_nexus()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar Nexus: {e}")
    return {
        "anos": sorted(df["Ano"].dropna().unique().tolist()),
        "empresas": sorted(df["[Empresa]"].dropna().unique().tolist()),
        "streams": sorted(df["[Stream]"].dropna().unique().tolist()),
    }

def _filter_nexus(df, anos="", tipo="Actual", empresas="", streams=""):
    """Filtra DataFrame do Nexus com fallbacks robustos para tipo e moeda."""
    if anos:
        df = df[df["Ano"].isin([int(a) for a in anos.split(",")])]
    if empresas:
        df = df[df["[Empresa]"].isin(empresas.split(","))]
    if streams:
        df = df[df["[Stream]"].isin(streams.split(","))]
    # Filtro de tipo: tenta exato, depois case-insensitive
    if "[Tipo]" in df.columns:
        mask = df["[Tipo]"].astype(str) == tipo
        if not mask.any():
            mask = df["[Tipo]"].astype(str).str.lower() == tipo.lower()
        df = df[mask]
    # Filtro de moeda: filtra BRL (e BLR, typo no dado)
    if "[Moeda]" in df.columns:
        df = df[df["[Moeda]"].astype(str).isin(["BRL", "BLR"])]
    return df

@app.get("/api/dre")
def get_dre(anos="", tipo="Actual", empresas="", user=Depends(get_current_user)):
    if not _ready["nexus"]:
        raise HTTPException(status_code=503, detail="Nexus ainda carregando, aguarde...")
    df = _filter_nexus(get_nexus(), anos=anos, tipo=tipo, empresas=empresas)
    print(f"DRE filtrado: {len(df)} rows (tipo={tipo}, anos={anos}, empresas={empresas})")
    if df.empty:
        return {"rows": [], "columns": []}
    return pl_to_json(compute_pl(df, "Período"))

@app.get("/api/streams")
def get_streams(anos="", tipo="Actual", empresas="", streams="", user=Depends(get_current_user)):
    if not _ready["nexus"]:
        raise HTTPException(status_code=503, detail="Nexus ainda carregando, aguarde...")
    df = _filter_nexus(get_nexus(), anos=anos, tipo=tipo, empresas=empresas, streams=streams)
    print(f"Streams filtrado: {len(df)} rows")
    if df.empty:
        return {"rows": [], "columns": []}
    return pl_to_json(compute_pl(df, "[Stream]"))

@app.get("/api/matricial")
def get_matricial(anos="", tipo="Actual", user=Depends(get_current_user)):
    if not _ready["nexus"]:
        raise HTTPException(status_code=503, detail="Nexus ainda carregando, aguarde...")
    df = _filter_nexus(get_nexus(), anos=anos, tipo=tipo)
    print(f"Matricial filtrado: {len(df)} rows")
    if df.empty:
        return {"rows": [], "columns": []}
    result = compute_pl(df, "[Empresa]")
    kpi_rows = ["Net revenue", "Gross profit", "Gross margin %", "Total SG&A", "EBITDA", "EBITDA %"]
    result = result.loc[[r for r in kpi_rows if r in result.index]]
    # Transpor: empresas viram linhas, KPIs viram colunas
    mat = result.T.reset_index()
    mat = mat.rename(columns={"index": "Empresa"})
    return {
        "columns": list(mat.columns),
        "data": mat.fillna(0).to_dict(orient="records"),
        "pct_cols": list(PCT_ROWS),
    }

# ── Cache helper ───────────────────────────────────────────────────────────────

_file_cache: dict = {}

def read_csv_cached(path: str, **kwargs) -> pd.DataFrame:
    mtime = os.path.getmtime(path)
    entry = _file_cache.get(path)
    if entry is None or entry["mtime"] != mtime:
        _file_cache[path] = {"df": pd.read_csv(path, **kwargs), "mtime": mtime}
    return _file_cache[path]["df"]

# ── Metas endpoints ────────────────────────────────────────────────────────────

def get_metas_df() -> pd.DataFrame:
    df = read_csv_cached("metas_custo.csv", dtype={"numero_pessoal": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
    return df

@app.get("/api/metas/filters")
def get_metas_filters(user=Depends(get_current_user)):
    df = get_metas_df()
    return {
        "competencias": sorted(df["competencia"].dropna().unique().tolist()),
        "empresas":     sorted(df["empresa"].dropna().unique().tolist()),
        "tipos":        sorted(df["tipo"].dropna().unique().tolist()),
    }

@app.get("/api/metas/custo-pessoal")
def get_metas_custo_pessoal(
    competencias: str = "", empresas: str = "", tipos: str = "",
    user=Depends(get_current_user)
):
    df = get_metas_df()
    if competencias:
        df = df[df["competencia"].isin(competencias.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    if tipos:
        df = df[df["tipo"].isin(tipos.split(","))]
    agg = df.groupby(["numero_pessoal", "nome", "empresa", "tipo"], as_index=False)["custo"].sum()
    agg = agg.sort_values("custo")
    return agg.fillna("").to_dict(orient="records")

# ── RAC Financial ──────────────────────────────────────────────────────────────

def get_rac_proj() -> pd.DataFrame:
    df = read_csv_cached("rac_projetos.csv", dtype={"pep": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
    return df

def get_rac_pess() -> pd.DataFrame:
    df = read_csv_cached("rac_pessoas.csv", dtype={"pep": str, "cpf": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
    return df

@app.get("/api/rac/filters")
def get_rac_filters(user=Depends(get_current_user)):
    df = get_rac_proj()
    return {
        "periodos": sorted(df["periodo"].dropna().unique().tolist()),
        "empresas": sorted(df["empresa"].dropna().unique().tolist()),
        "tipos":    sorted(df["tipo"].dropna().unique().tolist()),
    }

@app.get("/api/rac/projetos")
def get_rac_projetos(
    periodos: str = "", empresas: str = "", tipos: str = "",
    user=Depends(get_current_user)
):
    df = get_rac_proj()
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    if tipos:
        df = df[df["tipo"].isin(tipos.split(","))]
    df["pep"] = df["pep"].str.split(".").str[0]
    agg = df.groupby(["pep", "nome_cliente", "empresa"], as_index=False)["valor_liquido"].sum()
    agg = agg.sort_values("valor_liquido", ascending=False)
    return agg.fillna("").to_dict(orient="records")

@app.get("/api/rac/pessoas")
def get_rac_pessoas(
    pep: str = "", periodos: str = "", empresas: str = "",
    user=Depends(get_current_user)
):
    df = get_rac_pess()
    if pep:
        df = df[df["pep"].str.split(".").str[0] == pep]
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    df["cpf"] = df["cpf"].str.replace(r"^BRCPF", "", regex=True).fillna("")
    df["numero_pessoal"] = df["numero_pessoal"].fillna("")
    agg = df.groupby(["cpf", "numero_pessoal", "nome", "empresa"], as_index=False)["valor_liquido"].sum()
    agg = agg.sort_values("valor_liquido", ascending=False)
    return agg.fillna("").to_dict(orient="records")

# ── Margem por Projeto ─────────────────────────────────────────────────────────

def _clientes_lookup() -> tuple[dict, dict]:
    """Returns ({nome_upper: vertical/bu}, {nome_upper: ae}) using nome_base when available"""
    try:
        cli = read_clientes_csv()
        vertical_map: dict = {}
        ae_map: dict = {}
        for _, row in cli.iterrows():
            bu       = str(row.get("bu",  "") or "")
            ae       = str(row.get("ae",  "") or "")
            nome_base = str(row.get("nome_base", "") or "").strip()
            nome_cli  = str(row.get("nome_cliente", "") or "").strip()
            for key in ([nome_base.upper()] if nome_base else []) + ([nome_cli.upper()] if nome_cli else []):
                vertical_map[key] = bu
                if ae:
                    ae_map[key] = ae
        return vertical_map, ae_map
    except Exception:
        return {}, {}

def _vertical_lookup() -> dict:
    return _clientes_lookup()[0]

def get_margem_proj() -> pd.DataFrame:
    df = read_csv_cached("margem_projetos.csv", dtype={"pep": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])

    # Substitui receita pelo valor do RAC (fonte primária correta)
    rac = read_csv_cached("rac_projetos.csv", dtype={"pep": str})
    rac["pep"] = rac["pep"].str.split(".").str[0]
    rac_receita = rac.groupby(["periodo", "pep", "nome_cliente"])["valor_liquido"].sum().reset_index()
    rac_receita = rac_receita.rename(columns={"valor_liquido": "receita_rac"})
    df["pep_base"] = df["pep"].str.split(".").str[0]
    df = df.merge(rac_receita, left_on=["periodo", "pep_base", "nome_cliente"],
                  right_on=["periodo", "pep", "nome_cliente"], how="left", suffixes=("", "_rac_key"))
    df["receita"] = df["receita_rac"].where(df["receita_rac"].notna(), df["receita"])
    df["margem"]  = df["receita"] - df["custo_rateado"].fillna(0)
    df["margem_pct"] = df.apply(lambda r: r["margem"] / r["receita"] if r["receita"] else None, axis=1)
    df = df.drop(columns=["pep_base", "receita_rac", "pep_rac_key"], errors="ignore")

    vlookup, ae_lookup = _clientes_lookup()
    key = df["nome_cliente"].str.upper().str.strip()
    df["vertical"] = key.map(vlookup).fillna("")
    df["ae"]       = key.map(ae_lookup).fillna("")
    return df

def get_margem_pess() -> pd.DataFrame:
    df = read_csv_cached("margem_pessoas.csv", dtype={"pep": str, "cpf": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
    return df

@app.get("/api/margem/filters")
def get_margem_filters(user=Depends(get_current_user)):
    df = get_margem_proj()
    cats = []
    if "categoria_bu" in df.columns:
        cats = sorted(df["categoria_bu"].dropna().unique().tolist())
    verts = sorted([v for v in df["vertical"].dropna().unique().tolist() if v])
    aes   = sorted([v for v in df["ae"].dropna().unique().tolist() if v])
    return {
        "periodos":      sorted(df["periodo"].dropna().unique().tolist()),
        "empresas":      sorted(df["empresa"].dropna().unique().tolist()),
        "categorias_bu": cats,
        "verticais":     verts,
        "aes":           aes,
    }

def _clientes_nomes_upper() -> set:
    df = read_clientes_csv()
    # Use nome_base when available, otherwise nome_cliente
    match_col = df["nome_base"].str.strip() if "nome_base" in df.columns else df["nome_cliente"].str.strip()
    base_names = match_col[match_col != ""].str.upper()
    fallback = df.loc[match_col == "", "nome_cliente"].str.upper().str.strip()
    return set(base_names.tolist()) | set(fallback.tolist())

@app.get("/api/resumo")
def get_resumo(periodos: str = "", empresas: str = "", categorias_bu: str = "", verticais: str = "", apenas_atribuidos: bool = False, user=Depends(get_current_user)):
    df = get_margem_proj()
    if apenas_atribuidos:
        nomes = _clientes_nomes_upper()
        df = df[df["nome_cliente"].str.upper().str.strip().isin(nomes)]
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    if categorias_bu and "categoria_bu" in df.columns:
        df = df[df["categoria_bu"].isin(categorias_bu.split(","))]
    if verticais:
        df = df[df["vertical"].isin(verticais.split(","))]
    agg = df.groupby(["empresa", "periodo"], as_index=False).agg(
        receita       = ("receita",       "sum"),
        custo_rateado = ("custo_rateado", "sum"),
        margem        = ("margem",        "sum"),
    )
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    return agg.fillna("").to_dict(orient="records")

# ── Clientes endpoints ──────────────────────────────────────────────────────

def read_clientes_csv() -> pd.DataFrame:
    path = "clientes.csv"
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str).fillna("")
        return df
    return pd.DataFrame(columns=["nome_cliente","bu","ae"])

def write_clientes_csv(df: pd.DataFrame):
    df.to_csv("clientes.csv", index=False)

@app.get("/api/clientes")
def get_clientes_list(search: str = "", user=Depends(get_current_user)):
    clientes = read_clientes_csv()
    proj = get_margem_proj()
    proj["nome_upper"] = proj["nome_cliente"].str.upper().str.strip()
    totais = proj.groupby("nome_upper", as_index=False).agg(
        receita=("receita","sum"),
        custo_rateado=("custo_rateado","sum"),
        margem=("margem","sum"),
        num_projetos=("pep","nunique"),
    )
    # Use nome_base for matching when available, otherwise nome_cliente
    if "nome_base" in clientes.columns:
        clientes["nome_upper"] = clientes.apply(
            lambda r: r["nome_base"].upper().strip() if r["nome_base"].strip() else r["nome_cliente"].upper().strip(), axis=1
        )
    else:
        clientes["nome_upper"] = clientes["nome_cliente"].str.upper().str.strip()
    merged = clientes.merge(totais, on="nome_upper", how="left").drop(columns=["nome_upper"])
    if "nome_base" in merged.columns:
        merged = merged.drop(columns=["nome_base"])
    merged["margem_pct"] = merged.apply(
        lambda r: float(r["margem"]) / float(r["receita"]) if r.get("receita") not in ("", None, 0) and float(r.get("receita",0)) != 0 else None,
        axis=1
    )
    if search:
        merged = merged[merged["nome_cliente"].str.upper().str.contains(search.upper(), na=False)]
    return merged.fillna("").to_dict(orient="records")

@app.post("/api/clientes/ae")
def update_cliente_ae(body: dict, user=Depends(get_current_user)):
    nome = str(body.get("nome_cliente","")).strip()
    ae   = str(body.get("ae","")).strip()
    df = read_clientes_csv()
    if nome in df["nome_cliente"].values:
        df.loc[df["nome_cliente"] == nome, "ae"] = ae
    else:
        new_row = pd.DataFrame([{"nome_cliente": nome, "bu": "", "ae": ae}])
        df = pd.concat([df, new_row], ignore_index=True)
    write_clientes_csv(df)
    return {"ok": True}

@app.get("/api/margem/projetos")
def get_margem_projetos(periodos: str = "", empresas: str = "", categorias_bu: str = "", verticais: str = "", aes: str = "", breakdown: bool = False, nome_cliente: str = "", apenas_atribuidos: bool = False, user=Depends(get_current_user)):
    df = get_margem_proj()
    if apenas_atribuidos:
        nomes = _clientes_nomes_upper()
        df = df[df["nome_cliente"].str.upper().str.strip().isin(nomes)]
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    if categorias_bu and "categoria_bu" in df.columns:
        df = df[df["categoria_bu"].isin(categorias_bu.split(","))]
    if verticais:
        df = df[df["vertical"].isin(verticais.split(","))]
    if aes:
        df = df[df["ae"].isin(aes.split(","))]
    if nome_cliente:
        nc_upper = nome_cliente.upper().strip()
        match_names = {nc_upper}
        try:
            clientes_df = read_clientes_csv()
            if "nome_base" in clientes_df.columns:
                row = clientes_df[clientes_df["nome_cliente"].str.upper().str.strip() == nc_upper]
                if not row.empty:
                    nb = str(row.iloc[0].get("nome_base", "") or "").strip()
                    if nb:
                        match_names.add(nb.upper())
        except Exception:
            pass
        df = df[df["nome_cliente"].str.upper().str.strip().isin(match_names)]
    df["pep"] = df["pep"].str.split(".").str[0]
    base_extra = ["categoria_bu", "no_hierarquia", "centro_lucro"] if not breakdown and all(c in df.columns for c in ["categoria_bu", "no_hierarquia", "centro_lucro"]) else []
    v_ae_extra = [k for k in ["vertical", "ae"] if k in df.columns]
    extra_keys = base_extra + v_ae_extra
    group_keys = (["periodo", "pep", "nome_cliente", "empresa"] if breakdown else ["pep", "nome_cliente", "empresa"]) + extra_keys
    agg = df.groupby(group_keys, as_index=False).agg(
        receita      =("receita",       "sum"),
        custo_rateado=("custo_rateado", "sum"),
        horas_total  =("horas_total",   "sum"),
        margem       =("margem",        "sum"),
    )
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    agg = agg.sort_values("receita", ascending=False)
    return agg.fillna("").to_dict(orient="records")

@app.get("/api/margem/pessoas")
def get_margem_pessoas(pep: str = "", periodos: str = "", empresas: str = "", breakdown: bool = False, apenas_atribuidos: bool = False, user=Depends(get_current_user)):
    df = get_margem_pess()
    if apenas_atribuidos:
        proj = get_margem_proj()
        nomes = _clientes_nomes_upper()
        peps_ok = set(proj[proj["nome_cliente"].str.upper().str.strip().isin(nomes)]["pep"].str.split(".").str[0].tolist())
        df = df[df["pep"].str.split(".").str[0].isin(peps_ok)]
    if pep:
        df = df[df["pep"].str.split(".").str[0] == pep]
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    df["cpf"] = df["cpf"].str.replace(r"^BRCPF", "", regex=True).fillna("")
    group_keys = ["periodo", "cpf", "nome", "empresa"] if breakdown else ["cpf", "nome", "empresa"]
    agg = df.groupby(group_keys, as_index=False).agg(
        receita      =("receita",       "sum"),
        custo_rateado=("custo_rateado", "sum"),
        horas        =("horas",         "sum"),
        margem       =("margem",        "sum"),
    )
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    # build cpf→ID lookup from relacao_pessoas.xlsx, then nome fallback via rac_pessoas
    # (rac_pessoas.csv has numero_pessoal+nome but no cpf column)
    cpf_to_id: dict = {}
    if os.path.exists("relacao_pessoas.xlsx"):
        xl = pd.read_excel("relacao_pessoas.xlsx", dtype=str)
        xl["cpf_c"] = xl["CPF / Worker ID"].str.replace(r"^BRCPF", "", regex=True).fillna("")
        xl["id_sap"] = xl["ID SAP"].fillna("")
        for _, row in xl[(xl["cpf_c"] != "") & (xl["id_sap"] != "")].drop_duplicates("cpf_c").iterrows():
            cpf_to_id[row["cpf_c"]] = row["id_sap"]
    rp = get_rac_pess()[["numero_pessoal","nome"]].copy()
    rp["numero_pessoal"] = rp["numero_pessoal"].fillna("")
    nome_to_id = (rp[rp["numero_pessoal"] != ""]
                  .assign(nome_key=lambda d: d["nome"].str.lower().str.strip())
                  .drop_duplicates("nome_key").set_index("nome_key")["numero_pessoal"].to_dict())
    agg["numero_pessoal"] = agg.apply(
        lambda r: cpf_to_id.get(r["cpf"]) or nome_to_id.get(str(r["nome"]).lower().strip()) or "", axis=1
    )
    agg = agg.sort_values("receita", ascending=False)
    return agg.fillna("").to_dict(orient="records")

@app.get("/api/rac/pessoa_projetos")
def get_rac_pessoa_projetos(
    cpf: str = "", numero_pessoal: str = "",
    periodos: str = "", empresas: str = "",
    user=Depends(get_current_user)
):
    df = get_rac_pess()
    df["cpf_clean"] = df["cpf"].str.replace(r"^BRCPF", "", regex=True).fillna("")
    df["numero_pessoal"] = df["numero_pessoal"].fillna("")
    if cpf:
        df = df[df["cpf_clean"] == cpf]
    elif numero_pessoal:
        df = df[df["numero_pessoal"] == numero_pessoal]
    else:
        return []
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    df["pep_base"] = df["pep"].str.split(".").str[0]
    agg = df.groupby(["pep_base", "empresa"], as_index=False)["valor_liquido"].sum()
    proj = get_rac_proj()[["pep", "nome_cliente"]].copy()
    proj["pep_base"] = proj["pep"].str.split(".").str[0]
    proj = proj.drop_duplicates("pep_base")[["pep_base", "nome_cliente"]]
    agg = agg.merge(proj, on="pep_base", how="left")
    agg = agg.rename(columns={"pep_base": "pep"})
    agg = agg.sort_values("valor_liquido", ascending=False)
    return agg.fillna("").to_dict(orient="records")

@app.get("/api/margem/pessoa_projetos")
def get_margem_pessoa_projetos(
    cpf: str = "", periodos: str = "", empresas: str = "", breakdown: bool = False,
    user=Depends(get_current_user)
):
    if not cpf:
        return []
    df = get_margem_pess()
    df["cpf_clean"] = df["cpf"].str.replace(r"^BRCPF", "", regex=True).fillna("")
    df = df[df["cpf_clean"] == cpf]
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    df["pep_base"] = df["pep"].str.split(".").str[0]
    group_keys = ["periodo", "pep_base", "empresa"] if breakdown else ["pep_base", "empresa"]
    agg = df.groupby(group_keys, as_index=False).agg(
        receita      =("receita",       "sum"),
        custo_rateado=("custo_rateado", "sum"),
        horas        =("horas",         "sum"),
        margem       =("margem",        "sum"),
    )
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    proj = get_margem_proj()[["pep", "nome_cliente"]].copy()
    proj["pep_base"] = proj["pep"].str.split(".").str[0]
    proj = proj.drop_duplicates("pep_base")[["pep_base", "nome_cliente"]]
    agg = agg.merge(proj, on="pep_base", how="left")
    agg = agg.rename(columns={"pep_base": "pep"})
    agg = agg.sort_values("receita", ascending=False)
    return agg.fillna("").to_dict(orient="records")

# ── Razão / Check Lucas endpoints ─────────────────────────────────────────────

def get_razao() -> pd.DataFrame:
    df = read_csv_cached("razao_agg.csv").copy()
    df["periodo"] = df["FiscalYear"].astype(int).astype(str) + "-" + df["FiscalPeriod"].astype(int).apply(lambda x: f"{x:02d}")
    return df

@app.get("/api/razao/filters")
def get_razao_filters(user=Depends(get_current_user)):
    try:
        df = get_razao()
        rac = get_rac_proj()
        periodos = sorted(set(df["periodo"].unique().tolist()) | set(rac["periodo"].dropna().unique().tolist()))
        empresas = sorted(set(df["empresa"].dropna().unique().tolist()) | set(rac["empresa"].dropna().unique().tolist()))
        return {"periodos": periodos, "empresas": empresas}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/razao/comparativo")
def get_razao_comparativo(periodos: str = "", empresas: str = "", user=Depends(get_current_user)):
    razao = get_razao()
    pess  = get_margem_pess()

    sel_periodos = [p for p in periodos.split(",") if p] if periodos else []
    sel_empresas = [e for e in empresas.split(",") if e] if empresas else []

    if sel_periodos:
        razao = razao[razao["periodo"].isin(sel_periodos)]
        pess  = pess[pess["periodo"].isin(sel_periodos)]
    if sel_empresas:
        razao = razao[razao["empresa"].isin(sel_empresas)]
        pess  = pess[pess["empresa"].isin(sel_empresas)]

    # Razão: receita, payroll (CLT), third-party (PJ)
    razao_receita = (
        razao[razao["agrupador_fpa"] == "Net Revenue"]
        .groupby(["empresa","periodo"], as_index=False)["AmountInCompanyCodeCurrency"]
        .sum().rename(columns={"AmountInCompanyCodeCurrency": "receita_razao"})
    )
    razao_payroll = (
        razao[razao["agrupador_fpa"] == "Payroll costs"]
        .groupby(["empresa","periodo"], as_index=False)["AmountInCompanyCodeCurrency"]
        .sum().rename(columns={"AmountInCompanyCodeCurrency": "payroll_razao"})
    )
    razao_3p = (
        razao[razao["agrupador_fpa"] == "Third-party costs"]
        .groupby(["empresa","periodo"], as_index=False)["AmountInCompanyCodeCurrency"]
        .sum().rename(columns={"AmountInCompanyCodeCurrency": "thirdparty_razao"})
    )

    # Receita RAC vem de rac_projetos (MapaReceita "Efeito Receita Competência")
    proj = get_rac_proj()
    if sel_periodos:
        proj = proj[proj["periodo"].isin(sel_periodos)]
    if sel_empresas:
        proj = proj[proj["empresa"].isin(sel_empresas)]
    receita_rac = (
        proj.groupby(["empresa","periodo"], as_index=False)["valor_liquido"]
        .sum().rename(columns={"valor_liquido": "receita"})
    )

    # Custos RAC: PJ e CLT de margem_pessoas
    # Classificacao: billable/nao_classificado -> custo (entra na MB); non-billable -> despesa
    metas = read_csv_cached("metas_custo.csv", dtype={"numero_pessoal": str})
    pj_cpfs = set(
        metas[(metas["tipo"] == "PJ") & (metas["categoria"] == "PJs - Core")]
        ["numero_pessoal"].dropna().unique()
    )

    classif = read_csv_cached("classificacao_pessoas.csv")
    despesa_cpfs = set(classif[classif["classificacao"] == "despesa"]["cpf_brcpf"].dropna().unique())

    pess["is_pj"]      = pess["cpf"].isin(pj_cpfs)
    pess["is_despesa"] = pess["cpf"].isin(despesa_cpfs)

    # Custo PJ: PJs-Core que são custo (billable/nao_classificado)
    custo_pj = (
        pess[pess["is_pj"] & ~pess["is_despesa"]]
        .groupby(["empresa","periodo"], as_index=False)["custo_rateado"]
        .sum().rename(columns={"custo_rateado": "custo_pj"})
    )
    # Custo CLT: CLTs que são custo (billable/nao_classificado)
    custo_clt = (
        pess[~pess["is_pj"] & ~pess["is_despesa"]]
        .groupby(["empresa","periodo"], as_index=False)["custo_rateado"]
        .sum().rename(columns={"custo_rateado": "custo_clt"})
    )

    # Merge tudo
    df = razao_receita \
        .merge(razao_payroll,  on=["empresa","periodo"], how="outer") \
        .merge(razao_3p,       on=["empresa","periodo"], how="outer") \
        .merge(receita_rac,    on=["empresa","periodo"], how="outer") \
        .merge(custo_clt,      on=["empresa","periodo"], how="outer") \
        .merge(custo_pj,       on=["empresa","periodo"], how="outer")

    df = df.fillna(0)

    # Normaliza sinais: tudo positivo para comparação
    # Net Revenue na Razão é negativo (convenção contábil) → inverte
    df["receita_razao"] = df["receita_razao"] * -1
    # Custos RAC são negativos → inverte
    df["custo_clt"] = df["custo_clt"] * -1
    df["custo_pj"]  = df["custo_pj"]  * -1
    # Payroll e Third-party na Razão já são positivos ✓

    df["custo_total_rac"]   = df["custo_clt"] + df["custo_pj"]
    df["custo_total_razao"] = df["payroll_razao"] + df["thirdparty_razao"]
    df["margem_rac"]        = df["receita"]        - df["custo_total_rac"]
    df["margem_razao"]      = df["receita_razao"]  - df["custo_total_razao"]

    df["diff_receita"]  = df["receita"]    - df["receita_razao"]
    df["diff_clt"]      = df["custo_clt"]  - df["payroll_razao"]
    df["diff_pj"]       = df["custo_pj"]   - df["thirdparty_razao"]
    df["diff_margem"]   = df["margem_rac"] - df["margem_razao"]

    df = df.sort_values(["periodo","empresa"])
    return df.to_dict(orient="records")

# ── CLT endpoints ──────────────────────────────────────────────────────────────

@app.get("/api/clt/debug")
def get_clt_debug(user=Depends(get_current_user)):
    import subprocess, sys, glob
    os.makedirs("clt_files", exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-c",
         f"import gdown; gdown.download_folder(id='{CLT_FOLDER_ID}', output='clt_files', quiet=False)"],
        capture_output=True, text=True, timeout=300
    )
    all_files = glob.glob("clt_files/**/*", recursive=True)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
        "files": all_files,
    }

@app.get("/api/clt/data")
def get_clt_data(meses: str = "", user=Depends(get_current_user)):
    try:
        data = get_clt()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar CLT: {e}")
    all_meses = sorted(data.keys(), key=lambda s: (s.split("/")[1], CLT_MONTHS_BR.index(s.split("/")[0]) if s.split("/")[0] in CLT_MONTHS_BR else 99))
    sel = meses.split(",") if meses else all_meses
    totals: dict = {}
    for mes in sel:
        if mes in data:
            for empresa, val in data[mes].items():
                totals[empresa] = totals.get(empresa, 0.0) + val
    order = {s: i for i, s in enumerate(CLT_SHEETS)}
    rows = sorted([{"empresa": e, "totalizador": v} for e, v in totals.items()],
                  key=lambda x: order.get(x["empresa"], 99))
    total = sum(r["totalizador"] for r in rows)
    rows.append({"empresa": "Total", "totalizador": total})
    return {"meses": all_meses, "data": rows}

# ── Apuração de Metas endpoints ───────────────────────────────────────────────

from apuracao_engine import (
    calc_bonus_ae, calc_bonus_diretor, get_visao_master,
    _load_all, norm as eng_norm
)

@app.get("/api/apuracao/pessoas")
def get_apuracao_pessoas(user=Depends(get_current_user)):
    """Lista todos os avaliados com posição, contrato e salário Q4."""
    d = _load_all()
    pessoas = d["pessoas"]
    result = []
    for _, p in pessoas.iterrows():
        sal = float(p["Sal_Q4"]) if not __import__("math").isnan(float(p["Sal_Q4"] or 0)) else 0.0
        if sal == 0:
            continue
        result.append({
            "nome":     p["Nome"],
            "posicao":  str(p["Posicao"]),
            "contrato": str(p.get("Contrato", "")),
            "salario":  round(sal, 2),
        })
    return result

@app.get("/api/apuracao/calcular")
def get_apuracao_calcular(nome: str, user=Depends(get_current_user)):
    """Calcula bônus Q4 para uma pessoa específica."""
    d = _load_all()
    pessoas = d["pessoas"]
    nome_n = eng_norm(nome)
    pessoa = pessoas[pessoas["nome_norm"] == nome_n]
    if pessoa.empty:
        pessoa = pessoas[pessoas["nome_norm"].str.contains(nome_n.split()[0])]
    if pessoa.empty:
        raise HTTPException(status_code=404, detail=f"Pessoa não encontrada: {nome}")
    pos = str(pessoa.iloc[0]["Posicao"]).upper().strip()
    try:
        if pos == "DIRETOR":
            return calc_bonus_diretor(nome)
        else:
            return calc_bonus_ae(nome)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apuracao/visao-master")
def get_apuracao_visao_master(user=Depends(get_current_user)):
    """Retorna todos os avaliados com bônus calculado (visão consolidada)."""
    try:
        return get_visao_master()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apuracao/pdf")
def get_apuracao_pdf(nome: str, user=Depends(get_current_user)):
    """Gera PDF com memória de cálculo individual (Q4 2025)."""
    from fastapi.responses import Response
    from pdf_apuracao import gerar_pdf
    d = _load_all()
    pessoas = d["pessoas"]
    nome_n = eng_norm(nome)
    pessoa = pessoas[pessoas["nome_norm"] == nome_n]
    if pessoa.empty:
        pessoa = pessoas[pessoas["nome_norm"].str.contains(nome_n.split()[0])]
    if pessoa.empty:
        raise HTTPException(status_code=404, detail=f"Pessoa não encontrada: {nome}")
    pos = str(pessoa.iloc[0]["Posicao"]).upper().strip()
    try:
        dados = calc_bonus_diretor(nome) if pos == "DIRETOR" else calc_bonus_ae(nome)
        pdf_bytes = gerar_pdf(dados)
        nome_arquivo = nome.replace(" ", "_").replace("/", "_")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="apuracao_q4_{nome_arquivo}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

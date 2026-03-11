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
    "BR02": "FCamara", "BR07": "Hyper", "BR09": "NextGen",
    "BR05": "SGA", "BR06": "Dojo", "BR04": "Nação Digital",
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
    return read_csv_cached("metas_custo.csv", dtype={"numero_pessoal": str})

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
    return read_csv_cached("rac_projetos.csv", dtype={"pep": str})

def get_rac_pess() -> pd.DataFrame:
    return read_csv_cached("rac_pessoas.csv", dtype={"pep": str, "cpf": str})

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
        df = df[df["pep"] == pep]
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    agg = df.groupby(["cpf", "nome", "empresa", "pep"], as_index=False)["valor_liquido"].sum()
    agg = agg.sort_values("valor_liquido", ascending=False)
    return agg.fillna("").to_dict(orient="records")

# ── Margem por Projeto ─────────────────────────────────────────────────────────

def get_margem_proj() -> pd.DataFrame:
    return read_csv_cached("margem_projetos.csv", dtype={"pep": str})

def get_margem_pess() -> pd.DataFrame:
    return read_csv_cached("margem_pessoas.csv", dtype={"pep": str, "cpf": str})

@app.get("/api/margem/filters")
def get_margem_filters(user=Depends(get_current_user)):
    df = get_margem_proj()
    return {
        "periodos": sorted(df["periodo"].dropna().unique().tolist()),
        "empresas": sorted(df["empresa"].dropna().unique().tolist()),
    }

@app.get("/api/margem/projetos")
def get_margem_projetos(periodos: str = "", empresas: str = "", user=Depends(get_current_user)):
    df = get_margem_proj()
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    agg = df.groupby(["pep","nome_cliente","empresa"], as_index=False).agg(
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
def get_margem_pessoas(pep: str = "", periodos: str = "", empresas: str = "", user=Depends(get_current_user)):
    df = get_margem_pess()
    if pep:
        df = df[df["pep"] == pep]
    if periodos:
        df = df[df["periodo"].isin(periodos.split(","))]
    if empresas:
        df = df[df["empresa"].isin(empresas.split(","))]
    agg = df.groupby(["pep","cpf","nome","empresa"], as_index=False).agg(
        receita      =("receita",       "sum"),
        custo_rateado=("custo_rateado", "sum"),
        horas        =("horas",         "sum"),
        margem       =("margem",        "sum"),
    )
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
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
        margem = get_margem_proj()
        periodos = sorted(set(df["periodo"].unique().tolist()) | set(margem["periodo"].dropna().unique().tolist()))
        empresas = sorted(set(df["empresa"].dropna().unique().tolist()) | set(margem["empresa"].dropna().unique().tolist()))
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

    # Nossos dados: PJ = CPF começa com BRCPF, CLT = resto
    metas = read_csv_cached("metas_custo.csv", dtype={"numero_pessoal": str})
    pj_cpfs = set(metas[metas["tipo"] == "PJ"]["numero_pessoal"].dropna().unique())

    pess["is_pj"] = pess["cpf"].isin(pj_cpfs)

    custo_pj = (
        pess[pess["is_pj"]]
        .groupby(["empresa","periodo"], as_index=False)["custo_rateado"]
        .sum().rename(columns={"custo_rateado": "custo_pj"})
    )
    custo_clt = (
        pess[~pess["is_pj"]]
        .groupby(["empresa","periodo"], as_index=False)["custo_rateado"]
        .sum().rename(columns={"custo_rateado": "custo_clt"})
    )
    receita_rac = (
        pess.groupby(["empresa","periodo"], as_index=False)["receita"]
        .sum()
    )

    # Merge tudo
    df = razao_receita \
        .merge(razao_payroll,  on=["empresa","periodo"], how="outer") \
        .merge(razao_3p,       on=["empresa","periodo"], how="outer") \
        .merge(receita_rac,    on=["empresa","periodo"], how="outer") \
        .merge(custo_clt,      on=["empresa","periodo"], how="outer") \
        .merge(custo_pj,       on=["empresa","periodo"], how="outer")

    df = df.fillna(0)

    # Inverte sinal dos custos RAC (negativos no sistema → positivos para comparação)
    df["custo_clt"] = df["custo_clt"] * -1
    df["custo_pj"]  = df["custo_pj"]  * -1

    df["custo_total_rac"]    = df["custo_clt"] + df["custo_pj"]
    df["custo_total_razao"]  = df["payroll_razao"] + df["thirdparty_razao"]
    df["margem_rac"]         = df["receita"] - df["custo_total_rac"]
    df["margem_razao"]       = df["receita_razao"] + df["custo_total_razao"]

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

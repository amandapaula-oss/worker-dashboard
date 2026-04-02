from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
import bcrypt
import pandas as pd
import gdown
import os
import math

def _sanitize(obj):
    """Recursively replace NaN/Inf with None so JSON serialization never fails."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj

app = FastAPI()

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ───────────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY", "wk_secret_key_2024_react")
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

_cache: dict = {"df": None, "nomes": None, "sap": None, "nexus": None, "clt": None, "financeiro": None, "nova_base": None}
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
    "BR03": "Omnik",
    "BR04": "Nação Digital",
    "BR05": "SGA", "BR06": "Dojo",
    "BR07": "Hyper", "BR0C": "Hyper",
    "BR08": "Dojo", "Omnik": "Dojo",
    "BR09": "NextGen",
}
SAP_NAMES = {"BR02": "FCamara", "BR07": "Hyper", "BR09": "NextGen"}

def get_nomes() -> dict:
    if _cache["nomes"] is None:
        if not os.path.exists("pessoas.xlsx"):
            gdown.download(id=PERSONAL_ID, output="pessoas.xlsx", quiet=True)
        df = pd.read_excel("pessoas.xlsx", sheet_name="personal_data",
                           usecols=["ID Number", "Full Name"])
        df = df.dropna(subset=["ID Number"]).drop_duplicates("ID Number")
        _cache["nomes"] = dict(zip(df["ID Number"].astype(str), df["Full Name"]))
    return _cache["nomes"]

def get_df() -> pd.DataFrame:
    if _cache["df"] is None:
        if not os.path.exists("pessoas.xlsx"):
            gdown.download(id=WORKER_ID, output="pessoas.xlsx", quiet=True)
        df = pd.read_excel("pessoas.xlsx", sheet_name="receita_worker")
        df["lucro_bruto"] = df["receita_liquida"] - df["cost"]
        _cache["df"] = df
    return _cache["df"]

def _get_financeiro() -> pd.DataFrame:
    """Carrega aba financeiro de operacional.xlsx com cache baseado em mtime."""
    mtime = os.path.getmtime("operacional.xlsx")
    if _cache["financeiro"] is None or _cache.get("financeiro_mtime") != mtime:
        print("Carregando operacional.xlsx/financeiro...")
        df = pd.read_excel("operacional.xlsx", sheet_name="financeiro", dtype=str)
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").astype("float32")
        df["ano"]   = pd.to_numeric(df["ano"],   errors="coerce").astype("Int16")
        _cache["financeiro"]      = df
        _cache["financeiro_mtime"] = mtime
        print(f"operacional.xlsx/financeiro carregado: {len(df)} linhas")
    return _cache["financeiro"]

def get_sap() -> pd.DataFrame:
    fin = _get_financeiro()
    df  = fin[fin["fonte"] == "SAP"].copy()
    df  = df.rename(columns={
        "empresa":   "CompanyCode",
        "agrupador": "agrupador_fpa",
        "valor":     "AmountInCompanyCodeCurrency",
        "profit_center": "ProfitCenter",
    })
    df["FiscalPeriod"] = df["periodo"].str[5:7].astype(int)
    df["CompanyCode"]  = df["CompanyCode"].map(COMPANY_NAMES).fillna(df["CompanyCode"])
    for col in ["CompanyCode", "agrupador_fpa", "vertical", "ProfitCenter"]:
        if col in df.columns:
            df[col] = df[col].astype("category")
    if not _ready["sap"]:
        _ready["sap"] = True
    return df

def get_nexus() -> pd.DataFrame:
    fin = _get_financeiro()
    df  = fin[fin["fonte"] == "Nexus"].copy()
    df  = df.rename(columns={
        "empresa":          "[Empresa]",
        "vertical":         "[Vertical]",
        "agrupador":        "[Agrupador FP&A - COA]",
        "valor":            "[Valor]",
        "tipo_financeiro":  "[Tipo]",
        "moeda":            "[Moeda]",
        "stream":           "[Stream]",
        "periodo":          "Período",
    })
    df["Ano"] = df["ano"].astype("Int16")
    for col in ["[Tipo]", "[Moeda]", "[Empresa]", "[Vertical]", "[Stream]",
                "[Agrupador FP&A - COA]", "Período"]:
        if col in df.columns:
            df[col] = df[col].astype("category")
    if not _ready["nexus"]:
        _ready["nexus"] = True
    return df

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
        print("Carregando financeiro.csv (SAP + Nexus + Razão)...")
        _get_financeiro()
        sap = get_sap()
        _ready["sap"] = True
        print(f"SAP: {len(sap)} linhas, agrupadores={sap['agrupador_fpa'].dropna().unique().tolist()[:5]}")
        nx = get_nexus()
        _ready["nexus"] = True
        print(f"Nexus: {len(nx)} linhas")
        print(f"  Tipos: {nx['[Tipo]'].dropna().astype(str).unique().tolist()}")
        print(f"  Moedas: {nx['[Moeda]'].dropna().astype(str).unique().tolist()}")
        print(f"  Empresas: {nx['[Empresa]'].dropna().astype(str).unique().tolist()}")
        print(f"  Anos: {sorted(nx['Ano'].dropna().astype(int).unique().tolist())}")
        print("Servidor pronto.")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"Erro ao carregar financeiro.csv: {e}")

@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
@app.head("/health")
async def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    # Tudo em background para o servidor declarar "Live" imediatamente
    import threading
    def _preload_all():
        try:
            print("Carregando Worker (background)...")
            get_df()
            get_nomes()
            print("Worker carregado. Carregando dados pesados...")
        except Exception as e:
            print(f"Erro no preload leve: {e}")
        _preload_heavy()
        try:
            print("Pré-carregando nova base 2026...")
            _get_nova_base()
            print("Nova base carregada.")
        except Exception as e:
            print(f"Erro ao pré-carregar nova base: {e}")
    threading.Thread(target=_preload_all, daemon=True).start()

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

_SHEET_FILE = {
    "projetos":              "operacional.xlsx",
    "rac_pessoas":           "operacional.xlsx",
    "margem_pessoas":        "operacional.xlsx",
    "metas_custo":           "parametros.xlsx",
    "relacao_pessoas":        "pessoas.xlsx",
    "pep_vertical":          "parametros.xlsx",
    "clientes":              "parametros.xlsx",
}

def read_sheet_cached(sheet: str, **kwargs) -> pd.DataFrame:
    path = _SHEET_FILE[sheet]
    mtime = os.path.getmtime(path)
    key = (path, sheet)
    entry = _file_cache.get(key)
    if entry is None or entry["mtime"] != mtime:
        _file_cache[key] = {"df": pd.read_excel(path, sheet_name=sheet, **kwargs), "mtime": mtime}
    return _file_cache[key]["df"]

# compat alias
def read_csv_cached(path: str, **kwargs) -> pd.DataFrame:
    sheet = path.replace(".csv", "")
    return read_sheet_cached(sheet, **kwargs)

# ── Metas endpoints ────────────────────────────────────────────────────────────

def get_metas_df() -> pd.DataFrame:
    df = read_csv_cached("metas_custo.csv", dtype={"id_sap": str, "cpf": str}).copy()
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
    id_cols = [c for c in ["id_sap", "cpf"] if c in df.columns]
    group_keys = id_cols + ["nome", "empresa", "tipo"]
    agg = df.groupby(group_keys, as_index=False)["custo"].sum()
    agg = agg.sort_values("custo")
    return agg.fillna("").to_dict(orient="records")

# ── RAC Financial ──────────────────────────────────────────────────────────────

def get_rac_proj() -> pd.DataFrame:
    """Lê projetos.csv e adapta para o formato legado de rac_projetos."""
    df = read_csv_cached("projetos.csv", dtype={"pep": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
    # expande a coluna 'tipos' (csv) em linhas individuais para manter compatibilidade
    if "tipos" in df.columns:
        df = df[df["tipos"].notna() & (df["tipos"] != "")]
        df = df.assign(tipo=df["tipos"].str.split(",")).explode("tipo")
        df["tipo"] = df["tipo"].str.strip()
    df = df.rename(columns={"receita": "valor_liquido"})
    return df

def get_rac_pess() -> pd.DataFrame:
    df = read_csv_cached("rac_pessoas.csv", dtype={"pep": str, "numero_pessoal": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
    if "cpf" not in df.columns:
        df["cpf"] = ""
    return df

@app.get("/api/rac/filters")
def get_rac_filters(user=Depends(get_current_user)):
    df = read_csv_cached("projetos.csv", dtype={"pep": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
    # extrai todos os tipos únicos do campo csv
    tipos_raw = df["tipos"].dropna().str.split(",").explode().str.strip()
    tipos = sorted(tipos_raw[tipos_raw != ""].unique().tolist())
    return {
        "periodos": sorted(df["periodo"].dropna().unique().tolist()),
        "empresas": sorted(df["empresa"].dropna().unique().tolist()),
        "tipos":    tipos,
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
        sel = set(tipos.split(","))
        df = df[df["tipo"].isin(sel)]
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
    df["cpf"] = df["cpf"].astype(str).str.replace(r"^BRCPF", "", regex=True).fillna("")
    df["numero_pessoal"] = df["numero_pessoal"].fillna("").astype(str)
    agg = df.groupby(["numero_pessoal", "nome", "empresa"], as_index=False)["valor_liquido"].sum()
    agg["cpf"] = ""
    agg = agg.sort_values("valor_liquido", ascending=False)
    return agg.fillna("").to_dict(orient="records")

# ── Margem por Projeto ─────────────────────────────────────────────────────────

def _clientes_lookup() -> tuple[dict, dict]:
    """Returns ({nome_upper: vertical/bu}, {nome_upper: ae}) using nome_base (pipe-separated aliases) when available"""
    try:
        cli = read_clientes_csv()
        vertical_map: dict = {}
        ae_map: dict = {}
        for _, row in cli.iterrows():
            bu        = str(row.get("bu",  "") or "")
            ae        = str(row.get("ae",  "") or "")
            nome_base = str(row.get("nome_base", "") or "").strip()
            nome_cli  = str(row.get("nome_cliente", "") or "").strip()
            aliases   = [a.strip().upper() for a in nome_base.split("|") if a.strip()]
            for key in aliases + ([nome_cli.upper()] if nome_cli else []):
                vertical_map[key] = bu
                if ae:
                    ae_map[key] = ae
        return vertical_map, ae_map
    except Exception:
        return {}, {}

def _vertical_lookup() -> dict:
    return _clientes_lookup()[0]

# Benchmark de margem Q4 por categoria_bu — alinhado com apuracao_engine.py
WS_MB_BENCHMARK = {
    "Cloud/Cyber": 0.34,
    "Dados":       0.35,
    "Hyper":       0.35,
    "Demais":      0.37,
    # Apps: usa margem calculada
}

def get_margem_proj() -> pd.DataFrame:
    # projetos.csv já traz receita com valor RAC onde disponível (pré-mesclado)
    df = read_csv_cached("projetos.csv", dtype={"pep": str}).copy()
    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
    # renomeia horas para horas_total para compatibilidade
    if "horas" in df.columns and "horas_total" not in df.columns:
        df = df.rename(columns={"horas": "horas_total"})

    # Custos reais de pessoas para Apps com custo_rateado=0 no SAP
    try:
        _mp = read_csv_cached("margem_pessoas.csv", dtype={"pep": str, "cpf": str})
        _cl = read_csv_cached("relacao_pessoas.csv", dtype={"CPF / Worker ID": str})
        _cpf_custo = set(_cl[_cl["classificacao"] == "custo"]["CPF / Worker ID"].dropna().str.strip())
        _mp_custo  = _mp[_mp["cpf"].str.strip().isin(_cpf_custo)].copy()
        _mp_custo["pep_base"] = _mp_custo["pep"].str.split(".").str[0]
        _pep_period_custo = _mp_custo.groupby(["pep_base", "periodo"])["custo_rateado"].sum().to_dict()
    except Exception:
        _pep_period_custo = {}

    # Simula custo/margem usando benchmark para WS com margem definida
    # Alinhado com apuracao_engine.py: categoria vazia/Vazio → tratada como "Demais"
    def _apply_benchmark(row, field):
        _cat_raw = row.get("categoria_bu", "")
        cat = str(_cat_raw).strip() if pd.notna(_cat_raw) else ""
        rec = row["receita"] if pd.notna(row["receita"]) else 0.0
        existing_custo = row["custo_rateado"] if pd.notna(row.get("custo_rateado")) else 0.0
        # Categoria explícita com benchmark definido — sempre sobrescreve SAP
        if cat in WS_MB_BENCHMARK and rec != 0:
            if field == "margem":
                return rec * WS_MB_BENCHMARK[cat]
            else:
                return -rec * (1 - WS_MB_BENCHMARK[cat])
        # Apps com custo=0: usa custo real de pessoas; fallback benchmark 35%
        if cat == "Apps" and rec != 0 and existing_custo == 0:
            _pep_b = str(row.get("pep", "")).split(".")[0]
            _per   = str(row.get("periodo", ""))
            _custo = _pep_period_custo.get((_pep_b, _per), None)
            if _custo is not None and _custo != 0:
                if field == "margem":      return rec + _custo
                else:                      return _custo
            else:
                if field == "margem":      return rec * 0.35
                else:                      return -rec * 0.65
        # Categoria vazia, "Vazio" ou desconhecida → aplica benchmark Demais (37%)
        # Evita margem irreal de 100% quando SAP não tem custo_rateado
        if (not cat or cat.strip().lower() in ("", "vazio")) and rec != 0:
            bench = WS_MB_BENCHMARK.get("Demais", 0.37)
            if field == "margem":
                return rec * bench
            else:
                return -rec * (1 - bench)
        if field == "margem":
            return rec + existing_custo
        return row["custo_rateado"]

    df["margem"]       = df.apply(_apply_benchmark, field="margem", axis=1)
    df["custo_rateado"]= df.apply(_apply_benchmark, field="custo_rateado", axis=1)

    # Override OpenX: assume MB% = 45% (alinhado com apuracao_engine.py)
    if "no_hierarquia" in df.columns:
        openx_mask = df["no_hierarquia"].str.upper().str.strip() == "OPENX"
        df.loc[openx_mask, "margem"]        = df.loc[openx_mask, "receita"] * 0.45
        df.loc[openx_mask, "custo_rateado"] = df.loc[openx_mask, "receita"] * -0.55

    df["margem_pct"] = df.apply(lambda r: r["margem"] / r["receita"] if r["receita"] and r["receita"] > 0 else None, axis=1)
    df = df.drop(columns=["pep_base", "receita_rac", "pep_rac_key"], errors="ignore")

    vlookup, ae_lookup = _clientes_lookup()
    # Limpa nomes do tipo "Recorrência Cliente (BR03CLP00043)" antes do vlookup
    import re as _re
    _recorr_pat = _re.compile(r'\([A-Z0-9]+\)\s*$', _re.IGNORECASE)
    def _clean_cli(n: str) -> str:
        n = _recorr_pat.sub('', str(n)).strip()
        n = _re.sub(r'(?i)^Recorr[êe]ncia\s+', '', n).strip()
        n = _re.sub(r'(?i)\s+Recorr[êe]ncia\s*$', '', n).strip()
        return n.upper().strip()
    key = df["nome_cliente"].apply(_clean_cli)
    df["vertical"] = key.map(vlookup).fillna("")
    df["ae"]       = key.map(ae_lookup).fillna("")

    # Normaliza nome_cliente para o nome canônico usando aliases do cadastro
    try:
        _cli = read_clientes_csv()
        _alias_map: dict = {}
        for _, _row in _cli.iterrows():
            _canonical = str(_row["nome_cliente"]).strip()
            _alias_map[_canonical.upper()] = _canonical
            _nb = str(_row.get("nome_base", "") or "")
            for _alias in [a.strip() for a in _nb.split("|") if a.strip()]:
                _alias_map[_alias.upper()] = _canonical
        df["nome_cliente"] = key.map(_alias_map).fillna(df["nome_cliente"].str.strip())
    except Exception:
        pass

    # PEP-level vertical override (para clientes que aparecem em múltiplas verticais)
    # Regra: pep_vertical.csv sempre prevalece — inclusive "Others".
    # Se o pep está mapeado no arquivo, esse valor é usado independente do vlookup do cliente.
    # Isso garante que clientes Finance/Retail/etc. com pep=Others não contaminem a vertical errada.
    try:
        pv = read_sheet_cached("pep_vertical", dtype=str).dropna(subset=["pep", "vertical"])
        pv_map = dict(zip(pv["pep"].str.strip(), pv["vertical"].str.strip()))
        pep_override = df["pep"].str.strip().map(pv_map)
        df.loc[pep_override.notna(), "vertical"] = pep_override[pep_override.notna()]
    except Exception:
        pass

    df["vertical"] = df["vertical"].replace("", "Others").fillna("Others")

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
    centros = sorted([v for v in df["centro_lucro"].dropna().unique().tolist() if v]) if "centro_lucro" in df.columns else []
    return {
        "periodos":      sorted(df["periodo"].dropna().unique().tolist()),
        "empresas":      sorted(df["empresa"].dropna().unique().tolist()),
        "categorias_bu": cats,
        "verticais":     verts,
        "aes":           aes,
        "centros_lucro": centros,
    }

def _clientes_nomes_upper() -> set:
    df = read_clientes_csv()
    nomes: set = set()
    for _, row in df.iterrows():
        nomes.add(str(row["nome_cliente"]).upper().strip())
        if "nome_base" in df.columns:
            nb = str(row.get("nome_base", "") or "")
            for alias in [a.strip().upper() for a in nb.split("|") if a.strip()]:
                nomes.add(alias)
    return nomes

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
    path = "parametros.xlsx"
    if os.path.exists(path):
        df = pd.read_excel(path, sheet_name="clientes", dtype=str).fillna("")
        return df
    return pd.DataFrame(columns=["nome_cliente","bu","ae"])

def write_clientes_csv(df: pd.DataFrame):
    path = "parametros.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name="clientes", index=False)
    _file_cache.pop(("parametros.xlsx", "clientes"), None)

@app.get("/api/clientes")
def get_clientes_list(search: str = "", user=Depends(get_current_user)):
    clientes = read_clientes_csv()
    proj = get_margem_proj()

    # Build alias → canonical nome_cliente map (handles pipe-separated aliases)
    alias_to_canonical: dict = {}
    for _, row in clientes.iterrows():
        canonical = str(row["nome_cliente"]).strip()
        alias_to_canonical[canonical.upper()] = canonical
        if "nome_base" in clientes.columns:
            nb = str(row.get("nome_base", "") or "")
            for alias in [a.strip() for a in nb.split("|") if a.strip()]:
                alias_to_canonical[alias.upper()] = canonical

    # Map each project to its canonical client name
    proj_nc_upper = proj["nome_cliente"].str.upper().str.strip()
    proj["nome_canonical"] = proj_nc_upper.map(alias_to_canonical).fillna(proj["nome_cliente"].str.strip())
    proj["nome_canonical_upper"] = proj["nome_canonical"].str.upper().str.strip()

    # Aggregate totals by canonical name (all aliases summed together)
    totais = proj.groupby("nome_canonical_upper", as_index=False).agg(
        receita=("receita","sum"),
        custo_rateado=("custo_rateado","sum"),
        margem=("margem","sum"),
        num_projetos=("pep","nunique"),
    )
    proj_ws = proj[~proj["categoria_bu"].isin(["", "Vazio"])].sort_values("receita", ascending=False)
    ws_first = proj_ws.groupby("nome_canonical_upper")["categoria_bu"].first()
    totais["ws"] = totais["nome_canonical_upper"].map(ws_first).fillna("")
    totais = totais.rename(columns={"nome_canonical_upper": "nome_upper"})

    # Add any clients present in projetos but not yet in clientes.csv
    clientes["nome_upper"] = clientes["nome_cliente"].str.upper().str.strip()
    missing_mask = ~totais["nome_upper"].isin(clientes["nome_upper"])
    missing = totais.loc[missing_mask, ["nome_upper"]].copy()
    missing["nome_cliente"] = missing["nome_upper"]
    missing["bu"] = ""
    missing["ae"] = ""
    if "nome_base" in clientes.columns:
        missing["nome_base"] = ""
    if not missing.empty:
        clientes = pd.concat([clientes, missing[clientes.columns]], ignore_index=True)
        clientes["nome_upper"] = clientes["nome_cliente"].str.upper().str.strip()

    merged = clientes.merge(totais, on="nome_upper", how="left").drop(columns=["nome_upper"])
    merged["margem_pct"] = merged.apply(
        lambda r: float(r["margem"]) / float(r["receita"]) if r.get("receita") not in ("", None, 0) and float(r.get("receita",0)) != 0 else None,
        axis=1
    )
    if search:
        q = search.upper()
        nome_match = merged["nome_cliente"].str.upper().str.contains(q, na=False)
        if "nome_base" in merged.columns:
            alias_match = merged["nome_base"].str.upper().str.contains(q, na=False)
            merged = merged[nome_match | alias_match]
        else:
            merged = merged[nome_match]
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
def get_margem_projetos(periodos: str = "", empresas: str = "", categorias_bu: str = "", verticais: str = "", aes: str = "", centros_lucro: str = "", breakdown: bool = False, nome_cliente: str = "", apenas_atribuidos: bool = False, user=Depends(get_current_user)):
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
    if centros_lucro and "centro_lucro" in df.columns:
        df = df[df["centro_lucro"].isin(centros_lucro.split(","))]
    if nome_cliente:
        nc_upper = nome_cliente.upper().strip()
        match_names = {nc_upper}
        try:
            clientes_df = read_clientes_csv()
            if "nome_base" in clientes_df.columns:
                row = clientes_df[clientes_df["nome_cliente"].str.upper().str.strip() == nc_upper]
                if not row.empty:
                    nb = str(row.iloc[0].get("nome_base", "") or "").strip()
                    for alias in [a.strip() for a in nb.split("|") if a.strip()]:
                        match_names.add(alias.upper())
        except Exception:
            pass
        df = df[df["nome_cliente"].str.upper().str.strip().isin(match_names)]
    df["pep"] = df["pep"].str.split(".").str[0]
    base_extra = ["categoria_bu", "no_hierarquia", "centro_lucro"] if not breakdown and all(c in df.columns for c in ["categoria_bu", "no_hierarquia", "centro_lucro"]) else []
    v_ae_extra = [k for k in ["vertical", "ae"] if k in df.columns]
    extra_keys = base_extra + v_ae_extra
    group_keys = (["periodo", "pep", "nome_cliente", "empresa"] if breakdown else ["pep", "nome_cliente", "empresa"]) + extra_keys
    for k in group_keys:
        if k in df.columns:
            df[k] = df[k].fillna("")
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
    try:
        xl = pd.read_excel("pessoas.xlsx", sheet_name="relacao_pessoas", dtype=str)
        xl["cpf_c"] = xl["CPF / Worker ID"].str.replace(r"^BRCPF", "", regex=True).fillna("")
        xl["id_sap"] = xl["ID SAP"].fillna("")
        for _, row in xl[(xl["cpf_c"] != "") & (xl["id_sap"] != "")].drop_duplicates("cpf_c").iterrows():
            cpf_to_id[row["cpf_c"]] = row["id_sap"]
    except Exception:
        pass
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
    fin = _get_financeiro()
    df  = fin[fin["fonte"] == "Razao"].copy()
    df  = df.rename(columns={
        "agrupador": "agrupador_fpa",
        "valor":     "AmountInCompanyCodeCurrency",
    })
    df["FiscalYear"]   = df["ano"].astype("Int16")
    df["FiscalPeriod"] = df["periodo"].str[5:7].astype(int)
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
    metas = read_csv_cached("metas_custo.csv", dtype={"cpf": str, "id_sap": str})
    pj_cpfs = set(
        metas[(metas["tipo"] == "PJ") & (metas["categoria"] == "PJs - Core")]
        ["cpf"].dropna().unique()
    )

    classif = read_csv_cached("relacao_pessoas.csv")
    despesa_cpfs = set(classif[classif["classificacao"] == "despesa"]["CPF / Worker ID"].dropna().unique())

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
    calc_bonus_ae, calc_bonus_ae_q3, calc_bonus_diretor, get_visao_master,
    get_visao_master_q3, _load_all, norm as eng_norm
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
    import traceback
    try:
        d = _load_all()
        pessoas = d["pessoas"]
        nome_n = eng_norm(nome)
        pessoa = pessoas[pessoas["nome_norm"] == nome_n]
        if pessoa.empty:
            pessoa = pessoas[pessoas["nome_norm"].str.contains(nome_n.split()[0])]
        if pessoa.empty:
            raise HTTPException(status_code=404, detail=f"Pessoa não encontrada: {nome}")
        pos = str(pessoa.iloc[0]["Posicao"]).upper().strip()
        if pos == "DIRETOR":
            result = calc_bonus_diretor(nome)
        else:
            result = calc_bonus_ae(nome)
        return JSONResponse(content=_sanitize(result))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e} | {traceback.format_exc()}")

@app.get("/api/apuracao/calcular-q3")
def get_apuracao_calcular_q3(nome: str, user=Depends(get_current_user)):
    """Calcula bônus Q3 para AE_GM (Grupo Mult)."""
    import traceback
    try:
        result = calc_bonus_ae_q3(nome)
        return JSONResponse(content=_sanitize(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e} | {traceback.format_exc()}")

@app.get("/api/apuracao/visao-master")
def get_apuracao_visao_master(user=Depends(get_current_user)):
    """Retorna todos os avaliados com bônus calculado (visão consolidada)."""
    try:
        return get_visao_master()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apuracao/visao-master-q3")
def get_apuracao_visao_master_q3(user=Depends(get_current_user)):
    """Retorna bônus Q3 para AE_GM (Grupo Mult)."""
    try:
        return get_visao_master_q3()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apuracao/bonus-anual/{nome}")
def get_bonus_anual(nome: str, user=Depends(get_current_user)):
    """Retorna detalhes do bônus anual (Q1-Q4) para uma pessoa."""
    from apuracao_engine import calc_bonus_anual as _calc_anual
    try:
        d = _load_all()
        pessoas = d["pessoas"]
        nome_n = eng_norm(nome)
        pessoa = pessoas[pessoas["nome_norm"] == nome_n]
        if pessoa.empty:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")
        p   = pessoa.iloc[0]
        pos = str(p["Posicao"]).upper().strip()
        sal = float(p["Sal_Q4"] or 0)
        if pos == "DIRETOR":
            res = calc_bonus_diretor(nome)
            q4_real = res["real_rec_q4"]
            q4_meta = res["budget_rec_q4"]
            q4_lb_real = res.get("real_mc_pct", 0) / 100 * q4_real if res.get("real_mc_pct") else 0
            q4_lb_meta = res.get("budget_mc_pct", 0) / 100 * q4_meta if res.get("budget_mc_pct") else 0
        else:
            res = calc_bonus_ae(nome)
            q4_real = res["real_rec_total"]
            q4_meta = res["budget_rec_total"]
            q4_lb_real = res.get("real_lb_total", 0)
            q4_lb_meta = res.get("budget_mb_pct", 0) / 100 * q4_meta if res.get("budget_mb_pct") else 0
        return JSONResponse(content=_sanitize(_calc_anual(nome, pos, sal, q4_real, q4_meta, q4_lb_real, q4_lb_meta)))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"{e} | {traceback.format_exc()}")

@app.get("/api/apuracao/pdf-q3")
def get_apuracao_pdf_q3(nome: str, user=Depends(get_current_user)):
    """Gera PDF com memória de cálculo individual (Q3 2025)."""
    from fastapi.responses import Response
    from pdf_apuracao import gerar_pdf
    from apuracao_engine import calc_bonus_ae_q3
    try:
        dados = calc_bonus_ae_q3(nome)
        pdf_bytes = gerar_pdf(dados)
        nome_arquivo = nome.replace(" ", "_").replace("/", "_")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="apuracao_q3_{nome_arquivo}.pdf"'}
        )
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

@app.get("/api/apuracao/exportar-xlsx")
def get_exportar_xlsx(user=Depends(get_current_user)):
    """Gera e retorna apuracao_q4_exportado.xlsx com todos os AEs."""
    from fastapi.responses import Response
    from exportar_apuracao_q4 import gerar_xlsx_bytes
    try:
        data = gerar_xlsx_bytes()
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="apuracao_q4_exportado.xlsx"'},
        )
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"{e} | {traceback.format_exc()}")

# ── Nova Base 2026 ─────────────────────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _get_nova_base() -> pd.DataFrame:
    if _cache["nova_base"] is None:
        path = os.path.join(_BASE_DIR, "base_2026.xlsx")
        if not os.path.exists(path):
            path = os.path.join(_BASE_DIR, "..", "base_2026.xlsx")
        print(f"[nova_base] loading from: {path} (exists={os.path.exists(path)})")
        df = pd.read_excel(path, sheet_name="base", dtype=str)
        for col in ["receita", "custo_rateado", "horas", "margem", "valor_liquido", "valor",
                    "taxa_hora", "hour_price", "gross_revenue"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        _cache["nova_base"] = df
    return _cache["nova_base"]

@app.get("/api/nova-base/filters")
def get_nova_base_filters(user=Depends(get_current_user)):
    df = _get_nova_base()
    def uniq(col):
        return sorted(df[col].dropna().astype(str).str.strip().unique().tolist()) if col in df.columns else []
    return {
        "periodos":        uniq("periodo"),
        "fontes":          uniq("fonte"),
        "empresas":        uniq("empresa"),
        "macro_areas":     uniq("macro_area"),
        "areas":           uniq("area"),
        "tipos_contrato":  uniq("tipo_contrato"),
        "classificacoes":  uniq("classificacao"),
        "verticais":       uniq("vertical"),
    }

@app.get("/api/nova-base/resumo")
def get_nova_base_resumo(
    periodos: str = "",
    empresas: str = "",
    fontes: str = "",
    macro_areas: str = "",
    tipos_contrato: str = "",
    classificacoes: str = "",
    agrupar_por: str = "empresa",
    user=Depends(get_current_user)
):
    df = _get_nova_base().copy()

    def filt(col, param):
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if vals and col in df.columns:
            return df[df[col].astype(str).str.strip().isin(vals)]
        return df

    if periodos:       df = filt("periodo", periodos)
    if empresas:       df = filt("empresa", empresas)
    if fontes:         df = filt("fonte", fontes)
    if macro_areas:    df = filt("macro_area", macro_areas)
    if tipos_contrato: df = filt("tipo_contrato", tipos_contrato)
    if classificacoes: df = filt("classificacao", classificacoes)

    group_col = agrupar_por if agrupar_por in df.columns else "empresa"
    for col in ["receita", "custo_rateado", "horas", "valor_liquido"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df[group_col] = df[group_col].fillna("").astype(str).str.strip()
    df["periodo"]  = df["periodo"].fillna("").astype(str).str.strip()
    df = df[df[group_col].ne("") & df["periodo"].str.match(r"^\d{4}-\d{2}$")]

    agg = df.groupby([group_col, "periodo"], as_index=False).agg(
        receita       = ("receita",       "sum"),
        custo_rateado = ("custo_rateado", "sum"),
        horas         = ("horas",         "sum"),
        valor_liquido = ("valor_liquido", "sum"),
    )
    agg = agg.rename(columns={group_col: "grupo"})
    return _sanitize(agg.to_dict(orient="records"))

@app.get("/api/nova-base/data")
def get_nova_base_data(
    periodos: str = "",
    fontes: str = "",
    empresas: str = "",
    macro_areas: str = "",
    areas: str = "",
    tipos_contrato: str = "",
    classificacoes: str = "",
    verticais: str = "",
    user=Depends(get_current_user)
):
    df = _get_nova_base().copy()

    def filt(col, param):
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if vals and col in df.columns:
            return df[df[col].astype(str).str.strip().isin(vals)]
        return df

    if periodos:       df = filt("periodo", periodos)
    if fontes:         df = filt("fonte", fontes)
    if empresas:       df = filt("empresa", empresas)
    if macro_areas:    df = filt("macro_area", macro_areas)
    if areas:          df = filt("area", areas)
    if tipos_contrato: df = filt("tipo_contrato", tipos_contrato)
    if classificacoes: df = filt("classificacao", classificacoes)
    if verticais:      df = filt("vertical", verticais)

    MAX = 5000
    total = len(df)
    df = df.head(MAX)

    cols_show = [
        "fonte", "periodo", "empresa", "pep_base", "nome_pessoa",
        "nome_cliente", "tipo_contrato", "classificacao", "area",
        "centro_lucro", "macro_area", "vertical",
        "receita", "custo_rateado", "horas", "margem",
        "valor_liquido", "taxa_hora", "billable_category", "Comentarios",
    ]
    cols_show = [c for c in cols_show if c in df.columns]
    return _sanitize({"total": total, "truncated": total > MAX, "rows": df[cols_show].to_dict(orient="records")})

@app.get("/api/nova-base/dre")
def get_nova_base_dre(
    periodos: str = "",
    empresas: str = "",
    fontes: str = "",
    macro_areas: str = "",
    user=Depends(get_current_user)
):
    df = _get_nova_base().copy()

    def filt(col, param):
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if vals and col in df.columns:
            return df[df[col].astype(str).str.strip().isin(vals)]
        return df

    if periodos:    df = filt("periodo", periodos)
    if empresas:    df = filt("empresa", empresas)
    if fontes:      df = filt("fonte", fontes)
    if macro_areas: df = filt("macro_area", macro_areas)

    for col in ["receita", "custo_rateado", "valor_liquido"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["periodo"] = df["periodo"].fillna("").astype(str).str.strip()
    df = df[df["periodo"].str.match(r"^\d{4}-\d{2}$")]

    if df.empty:
        return {"rows": [], "columns": []}

    all_periods = sorted(df["periodo"].unique().tolist())
    columns = all_periods + ["Total"]

    # ── Helpers ────────────────────────────────────────────────────────────────
    def row_vals(piv_row: pd.Series):
        """piv_row: Series indexed by periodo (already reindexed)."""
        d = {p: float(piv_row.get(p, 0)) for p in all_periods}
        d["Total"] = float(piv_row.sum())
        return d

    def pct_vals(rec_row: pd.Series, vl_row: pd.Series):
        d = {}
        for p in all_periods:
            rec = float(rec_row.get(p, 0))
            vl  = float(vl_row.get(p, 0))
            d[p] = vl / rec if rec else 0.0
        tot_rec = float(rec_row.sum())
        tot_vl  = float(vl_row.sum())
        d["Total"] = tot_vl / tot_rec if tot_rec else 0.0
        return d

    def zero_vals():
        return {c: 0.0 for c in columns}

    # ── Single aggregation pass ────────────────────────────────────────────────
    # Total
    agg_total = df.groupby("periodo")[["receita", "custo_rateado", "valor_liquido"]].sum().reindex(all_periods, fill_value=0)

    rows = [
        {"name": "Receita",        "is_subtotal": True,  "is_pct": False, "is_group": False, "values": row_vals(agg_total["receita"])},
        {"name": "Custo",          "is_subtotal": False, "is_pct": False, "is_group": False, "values": row_vals(agg_total["custo_rateado"])},
        {"name": "Gross Profit",   "is_subtotal": True,  "is_pct": False, "is_group": False, "values": row_vals(agg_total["valor_liquido"])},
        {"name": "Gross Margin %", "is_subtotal": True,  "is_pct": True,  "is_group": False, "values": pct_vals(agg_total["receita"], agg_total["valor_liquido"])},
    ]

    # Macro Área — one groupby for ALL areas at once
    if "macro_area" in df.columns:
        df["macro_area"] = df["macro_area"].fillna("").astype(str).str.strip()
        agg_ma = (
            df[df["macro_area"].ne("")]
            .groupby(["macro_area", "periodo"])[["receita", "custo_rateado", "valor_liquido"]]
            .sum()
            .unstack("periodo")
            .reindex(columns=all_periods, level="periodo", fill_value=0)
        )
        for ma in sorted(agg_ma.index.tolist()):
            rec = agg_ma.loc[ma, "receita"]
            cus = agg_ma.loc[ma, "custo_rateado"]
            vl  = agg_ma.loc[ma, "valor_liquido"]
            rows.append({"name": ma,                 "is_subtotal": False, "is_pct": False, "is_group": True,  "values": zero_vals()})
            rows.append({"name": "  Receita",        "is_subtotal": False, "is_pct": False, "is_group": False, "values": row_vals(rec)})
            rows.append({"name": "  Custo",          "is_subtotal": False, "is_pct": False, "is_group": False, "values": row_vals(cus)})
            rows.append({"name": "  Gross Profit",   "is_subtotal": True,  "is_pct": False, "is_group": False, "values": row_vals(vl)})
            rows.append({"name": "  Gross Margin %", "is_subtotal": True,  "is_pct": True,  "is_group": False, "values": pct_vals(rec, vl)})

    return {"rows": rows, "columns": columns}

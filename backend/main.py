from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import bcrypt
import pandas as pd
import gdown
import os
import math
import traceback
import httpx

from correcoes_mar26 import (
    CORRECOES_PESSOAS,
    CENTRO_CUSTO_SALES_HYPER,
    MAPPING_EMPRESA,
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

def _supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

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

# Rate limiter (in-memory, conta por IP). Reset quando o backend reinicia.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Muitas tentativas. Aguarde alguns minutos e tente novamente."},
    )

app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS: lista de origens permitidas via env var ALLOWED_ORIGINS (separadas por vírgula).
# Default cobre o dominio do Vercel e dev local. Override via env var se mudar.
_allowed_origins_env = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://fcamara.vercel.app"
)
_ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
# Permite preview deploys do Vercel (vercel.app) via regex
_ALLOWED_ORIGIN_REGEX = os.environ.get(
    "ALLOWED_ORIGIN_REGEX",
    r"https://.*\.vercel\.app"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=_ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Headers de segurança em todas as respostas
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# Modo debug controla se o traceback é exposto na resposta (default: false em prod)
_DEBUG = os.environ.get("DEBUG_ERRORS", "").lower() in ("1", "true", "yes")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    # Loga internamente o stacktrace mas SEM URL completa (pode ter token em query)
    print(f"[ERROR] {request.method} {request.url.path} → {exc}\n{tb}")
    content = {"detail": "Erro interno do servidor"}
    if _DEBUG:
        content["traceback"] = tb
        content["error"] = str(exc)
    return JSONResponse(status_code=500, content=content)

# ── Auth ───────────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is required. "
        "Generate one: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "480"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# BUs canônicas (espelho do _BU_DEF usado no dataset). bus=[] significa admin (acesso total).
USERS = {
    "amanda":   {"name": "Amanda", "hashed_password": "$2b$12$mfHiyBw/auw.B745JxG2eO5Qlw/urUAOOVwi5x2koGXqWhUDhZv/a", "bus": []},
    "paola":    {"name": "Paola",  "hashed_password": "$2b$12$RWwqeh1tC5HC9flxYsR3s.a8RyTyCuDcsksRvtnI9K4DbwbKIR5KC", "bus": []},
    "yuri":     {"name": "Yuri",   "hashed_password": "$2b$12$lafxeoNomlDKRwz5seUPUe72xx06URZiuxTx2vbhJ6pFVy1HQpuhG", "bus": []},
    "amisrael": {"name": "Israel", "hashed_password": "$2b$12$Uxf53rbxFSof7w.wszVac.HmMOLoK17EfmisNDHc9NaxVHoaCbgO.", "bus": []},
}

BU_CARDS = ["BU Finance", "BU Health", "BU Multisector", "BU Retail", "BU Logistics"]

def get_user_bus(user: str) -> list:
    """BUs liberadas pro usuário. Lista vazia = admin (vê tudo)."""
    return list(USERS.get(user, {}).get("bus", []))

def enforce_bu_filter(user: str, verticais: str) -> str:
    """Restringe o parâmetro `verticais` às BUs liberadas pro usuário.
    - Admin (sem restrição): retorna `verticais` inalterado.
    - Restrito + sem `verticais`: retorna as BUs do usuário (force-filter).
    - Restrito + com `verticais`: intersecção. Se vazia → sentinel que não casa.
    """
    allowed = get_user_bus(user)
    if not allowed:
        return verticais
    requested = [v.strip() for v in (verticais or "").split(",") if v.strip()]
    if not requested:
        return ",".join(allowed)
    inter = [v for v in requested if v in allowed]
    return ",".join(inter) if inter else "__NO_ACCESS__"

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
@limiter.limit("5/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    user = USERS.get(form.username)
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos")
    return {"access_token": create_token(form.username), "token_type": "bearer"}

@app.get("/api/me")
def get_me(user=Depends(get_current_user)):
    info = USERS.get(user, {})
    allowed = get_user_bus(user)
    # BUs visíveis nos cards: se admin (allowed vazio) → todas; senão → só as permitidas.
    visible_bus = BU_CARDS if not allowed else [b for b in BU_CARDS if b in allowed]
    return {
        "username": user,
        "name": info.get("name", user),
        "is_admin": not allowed,
        "bus": allowed,
        "visible_bus": visible_bus,
    }

# ── Cache em memória ───────────────────────────────────────────────────────────

_cache: dict = {"df": None, "nomes": None, "sap": None, "nexus": None, "clt": None, "financeiro": None, "nova_base": None}
_ready: dict = {"sap": False, "nexus": False}

CLT_FOLDER_ID = os.environ.get("CLT_FOLDER_ID", "1aEHQAARXkf_BZbc5j0Z8Tt0s5Fmk6tSu")
CLT_SHEETS    = ["FC", "NX", "HY", "DOJO", "ND", "SGA"]
CLT_MONTHS_PT = ["janeiro","fevereiro","março","abril","maio","junho",
                 "julho","agosto","setembro","outubro","novembro","dezembro"]
CLT_MONTHS_BR = ["Jan","Fev","Mar","Abr","Mai","Jun",
                 "Jul","Ago","Set","Out","Nov","Dez"]

WORKER_ID   = os.environ.get("WORKER_ID", "13ORJ-dpxKXVF6sVy3Ex0Fp-hOLhxM8H_")
PERSONAL_ID = os.environ.get("PERSONAL_ID", "1qXu1bjWKqL3tNMYUAFjoMSiSle417WPF")
SAP_ID      = "1Lm-G9ZJUC2Hzc9iIKIb6LCemYJqtzNQO"
NEXUS_ID    = "1BBjfSYTGLAeuxMih4CDMgyfmVDGfkxkW"

COMPANY_NAMES = {
    "BR02": "BR02 FCamara", "BRO2": "BR02 FCamara", "FCamara": "BR02 FCamara",
    "BR03": "BR03 Omnik", "Omnik": "BR03 Omnik",
    "BR04": "BR04 Nação Digital", "Nação Digital": "BR04 Nação Digital",
    "BR05": "BR05 SGA", "SGA": "BR05 SGA",
    "BR07": "BR07 Hyper", "BR0C": "BR0C Hyper", "Hyper": "BR07 Hyper",
    "BR08": "BR08 Dojo", "Dojo": "BR08 Dojo",
    "BR09": "BR09 NextGen", "NextGen": "BR09 NextGen", "Next": "BR09 NextGen",
}
SAP_NAMES = {"BR02": "BR02 FCamara", "BR07": "BR07 Hyper", "BR09": "BR09 NextGen"}

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
        # Nova base carrega lazy (na primeira requisição) para não estourar memória no startup
        _preload_heavy()
        print("Todos os dados carregados.")
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
    "budget":                "parametros.xlsx",
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
    calc_bonus_ae, calc_bonus_ae_q3, calc_bonus_diretor, calc_bonus_diretor_q3,
    get_visao_master, get_visao_master_q3, _load_all, norm as eng_norm
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
    """Calcula bônus Q3 para AE_GM ou DIRETOR (Grupo Mult)."""
    import traceback
    try:
        d = _load_all()
        pessoas = d["pessoas"]
        nome_n = eng_norm(nome)
        pessoa = pessoas[pessoas["nome_norm"] == nome_n]
        if pessoa.empty:
            pessoa = pessoas[pessoas["nome_norm"].str.contains(nome_n.split()[0])]
        pos = str(pessoa.iloc[0]["Posicao"]).upper().strip() if not pessoa.empty else ""
        if pos == "DIRETOR":
            result = calc_bonus_diretor_q3(nome)
        else:
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
_nova_base_lock = __import__("threading").Lock()

def _load_nova_base_supabase() -> pd.DataFrame:
    """Fetch all rows from Supabase nova_base table."""
    url = f"{SUPABASE_URL}/rest/v1/nova_base"
    headers = _supabase_headers()
    all_rows = []
    page_size = 1000
    offset = 0
    client = httpx.Client(timeout=30)
    while True:
        r = client.get(f"{url}?select=*&order=id&offset={offset}&limit={page_size}", headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"Supabase error {r.status_code}: {r.text[:200]}")
        data = r.json()
        all_rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    client.close()
    print(f"[nova_base] loaded {len(all_rows)} rows from Supabase")
    df = pd.DataFrame(all_rows)
    # Linhas Budget vivem na mesma tabela mas NAO passam pelo pipeline
    # de rateio/enriquecimento. Sao consumidas apenas pelo endpoint
    # /api/budget-vs-realizado via _load_budget_supabase().
    if "fonte" in df.columns:
        df = df[df["fonte"].astype(str) != "Budget"].copy()
    return df


def _load_budget_supabase() -> pd.DataFrame:
    """Fetch apenas as linhas fonte='Budget' da nova_base."""
    url = f"{SUPABASE_URL}/rest/v1/nova_base"
    headers = _supabase_headers()
    all_rows = []
    page_size = 1000
    offset = 0
    client = httpx.Client(timeout=30)
    while True:
        r = client.get(f"{url}?select=periodo,vertical,nome_cliente,receita,custo_rateado,valor_liquido&fonte=eq.Budget&order=id&offset={offset}&limit={page_size}", headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"Supabase error {r.status_code}: {r.text[:200]}")
        data = r.json()
        all_rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    client.close()
    return pd.DataFrame(all_rows)


_pessoal_cache: dict = {"map_nome": None, "map_id": None}

def _norm_pessoa_nome(s):
    """Normalizacao completa: upper, sem acentos, colapsa espacos."""
    import unicodedata, re as _re
    if not isinstance(s, str) or not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return _re.sub(r"\s+", " ", s).strip().upper()


def _carregar_pessoal_depara() -> tuple[dict, dict]:
    """Carrega o de-para pessoal (nome/id → cpf) e cacheia. Fontes:
    1) pessoal_depara.csv (CSV historico)
    2) tabela `pessoas` no Supabase (master CPF) — sobrescreve conflitos.
    Normalizacao: NFKD + upper + collapse spaces (casa com acentos/typos).
    """
    if _pessoal_cache["map_nome"] is not None:
        return _pessoal_cache["map_nome"], _pessoal_cache["map_id"]
    import re as _re

    map_nome: dict = {}
    map_id: dict = {}

    # 1) CSV
    path = os.path.join(_BASE_DIR, "pessoal_depara.csv")
    if os.path.exists(path):
        p = pd.read_csv(path, dtype=str).dropna(subset=["cpf"])
        p["nome_norm"] = p["nome"].apply(_norm_pessoa_nome)
        p["id"] = p["id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        p["cpf_digits"] = p["cpf"].astype(str).str.replace(r"[^\d]", "", regex=True)
        p = p[p["cpf_digits"].str.len() >= 11]
        map_nome.update(p.drop_duplicates("nome_norm").set_index("nome_norm")["cpf_digits"].to_dict())
        map_id.update(p.drop_duplicates("id").set_index("id")["cpf_digits"].to_dict())

    # 2) Supabase pessoas (master) — sobrescreve
    # Inclui nome, razao_social (PJ) e variantes truncadas (32-40 chars)
    # pra casar com nomes que vieram truncados nos uploads originais.
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = _supabase_headers()
            all_rows = []
            off = 0
            with httpx.Client(timeout=30) as c:
                while True:
                    r = c.get(f"{SUPABASE_URL}/rest/v1/pessoas?select=cpf,nome,razao_social&offset={off}&limit=1000", headers=headers)
                    if r.status_code != 200:
                        break
                    data = r.json()
                    all_rows.extend(data)
                    if len(data) < 1000:
                        break
                    off += 1000
            for row in all_rows:
                cpf = _re.sub(r"[^\d]", "", str(row.get("cpf") or ""))
                if len(cpf) < 11:
                    continue
                nome_n = _norm_pessoa_nome(row.get("nome") or "")
                if nome_n:
                    map_nome[nome_n] = cpf
                rs_n = _norm_pessoa_nome(row.get("razao_social") or "")
                if rs_n:
                    map_nome[rs_n] = cpf
                    # Variantes truncadas (uploads originais cortaram em 32-40 chars)
                    for L in (32, 33, 34, 35, 36, 37, 38, 39, 40):
                        if len(rs_n) > L:
                            trunc = rs_n[:L].rstrip()
                            if trunc not in map_nome:
                                map_nome[trunc] = cpf
        except Exception as e:
            print(f"[pessoas table] {e}")

    _pessoal_cache["map_nome"] = map_nome
    _pessoal_cache["map_id"] = map_id
    print(f"[pessoal_depara] {len(map_nome)} nomes, {len(map_id)} ids carregados (CSV+pessoas)")
    return map_nome, map_id


# Mapa Profit Center -> Apuracao (NG / Ecossistema)
# Baseado em DC001-DC042 (cadastro Profit Centers). DC001 (Squads), DC002 (Dedicated
# Teams), DC005 (Open-X) sao NG. Demais sao Ecossistema. Tambem aceita o nome.
_APURACAO_NG_CODES = {"DC001", "DC002", "DC005"}
_APURACAO_NG_NAMES = {"Squads", "Dedicated Teams", "Open-X"}
_APURACAO_ECOSSISTEMA_CODES = {f"DC{i:03d}" for i in range(3, 43)} - _APURACAO_NG_CODES
_APURACAO_ECOSSISTEMA_NAMES = {
    "Software Factory", "E-commerce", "Licensing Microsoft", "Imagine",
    "Hyperautomation", "Licensing Hyper", "Hyper Cloud Dev Plat", "Hyper Data Prot Comp",
    "Strat Consult (Dojo)", "Data Consult (Dojo)", "Product (Dojo)", "Web Analytics",
    "Project Lead", "SEO", "Creative", "Performance", "Social & Content", "CRM",
    "Rev Ops", "Marketplace", "Open Innovation", "CVB", "CVC", "Intrapreneurship",
    "Creat. Problem Solv.", "FC Consult. New Rev", "Dig. & App Innov.", "Infrastructure",
    "Data & AI (SGA)", "Security", "Partners", "Modern work", "FinOps", "Business Unit",
    "Back Office", "Data Prof.Serv.Dojo", "FC Consult. B. Sales", "FC Consult. Strategy",
    "AI Factory",
}


def _adicionar_apuracao(df: pd.DataFrame) -> pd.DataFrame:
    """Coluna virtual `apuracao` (NG / Ecossistema) baseada em no_hierarquia.
    Aceita formatos: "DC001", "DC001 Squads", "Squads".
    """
    if "no_hierarquia" not in df.columns:
        df["apuracao"] = ""
        return df
    nh = df["no_hierarquia"].fillna("").astype(str).str.strip()
    # Extrai DC code do inicio quando presente (cobre "DC001" e "DC001 Squads")
    dc_extr = nh.str.extract(r"^(DC\d{3})", expand=False).fillna("")
    ap = pd.Series("", index=df.index)
    # NG: bate por code (extraido) OR por nome puro
    ap[dc_extr.isin(_APURACAO_NG_CODES) | nh.isin(_APURACAO_NG_NAMES)] = "NG"
    # Ecossistema: idem
    ap[dc_extr.isin(_APURACAO_ECOSSISTEMA_CODES) | nh.isin(_APURACAO_ECOSSISTEMA_NAMES)] = "Ecossistema"
    df["apuracao"] = ap
    return df


# Carteira Hyper — clientes que devem ter vertical = "Hyper".
# Inclui nomes brutos da lista FP&A + variantes canonicas que aparecem na base
# apos a unificacao de aliases. Aplicado SOMENTE em linhas cuja vertical atual
# e "Others" — clientes ja em BU definida (BU Finance, BU Retail, etc.) sao
# mantidos como estao.
HYPER_CLIENTES = {
    # Lista crua FP&A (uppercase, sem espaços extras)
    "ALGAR", "ALVEAN", "IBM", "MARISTA", "MULTIPLAN", "MULTIPLAN EMPREENDIMENTOS IMOB S/A",
    "NUCLEA", "TD SYNNEX", "TOKIO MARINE", "ULTRA", "ULTRAPAR PARTICIPACOES S/A",
    "BV", "BANCO BV", "BANCO VOTORANTIM S.A.", "BS2", "CPFL ENERGIA", "CPFL PAULISTA",
    "CREFISA", "DANONE", "FC HYPER", "GRU", "GRUPO CASAS BAHIA", "IRANI", "LIGGA TELECOM",
    "NEXA RESOURCES", "PARAISO GOLD", "RED HAT BRASIL LTDA", "REDHAT", "TELEFONICA",
    "UNIMED NACIONAL", "UNIMED CURITIBA", "UNIMED", "CIRION", "DURATEX", "DURATEX S.A.",
    "DEXCO", "ELECTROLUX", "EVOLUA", "FIS", "GRUPO ELFA", "HDI", "INTERCEMENT",
    "KYNDRYL", "KYNDRYL BRASIL SERVICOS LTDA.", "OLX", "PORTICO", "SMILES", "SOMPO",
    "ZENVIA", "MARFRIG", "BRF", "BRASIL FOODS (BRF)", "EQUINIX", "RUMO", "BRASILPREV",
    "CVC BRASIL", "INGRAM", "VIGOR", "ODONTOPREV", "ODONTOPREV S.A.", "PRIVALIA",
    "RODOBENS", "GRUPO RODOBENS", "HEXIS", "MERCADO LIVRE", "COPERSUCAR", "RIACHUELO",
    "VLI", "OURIBANK", "MUFG", "BANCO MUFG", "FCAMARA", "GRUPO FCAMARA", "COBAP",
    "TOYOTA", "AB INBEV", "VIA VAREJO", "DEL TORO", "INTEGRATION", "BANCO VOLKSWAGEN",
    "GRUPO HYPERAUTOMATION", "AMBIPAR", "CIATECH", "LINKCALL",
    # Canonicos pos-alias (como aparecem na base atualmente)
    "ALGAR TELECOM S/A", "AMBIPAR PARTICIPACOES E EMPREENDIMENTOS",
    "ANHEUSER-BUSCH INBEV NV", "BANCO BS2 S.A.", "BANCO MUFG BRASIL S.A.", "BRF S.A.",
    "CASAS BAHIA", "CIRION TECHNOLOGIES DO BRASIL LTDA", "DEL TORO LOAN SERVICING, INC",
    "DANONE - AI STRATEGY", "ELECTROLUX DO BRASIL S/A",
    "EQUINIX DO BRASIL SOLUCOES DE TECNOLOGIA", "FC HYPERAUTOMATION CONSULTORIA LTDA",
    "FCAMARA CONSULTORIA E FORMACAO EM INFORM", "FIDELITY / FIS SOLUCOES",
    "GRU AIRPORT", "GRUPO CASAS BAHIA S.A.", "IRANI PAPEL E EMBALAGEM S.A.", "LIGGA",
    "LINKCALL SERVICOS DE CALL CENTER S.A", "MERCADO LIVRE /MERCADO.PAGO",
    "MULTIPLAN EMPREENDIMENTOS IMOBILIARIOS S", "PARAISO GOLD LOTEAMENTOS",
    "RODOBENS ADMINISTRADORA DE CONSORCIOS LT", "RUMO S.A.", "TELEFONICA BRASIL S.A.",
    "TOKIO MARINE SEGURADORA S.A.", "VIGOR ALIMENTOS S.A", "VLI MULTIMODAL S.A.",
    "ZENVIA MOBILE",
}


def _reclassificar_hyper(df: pd.DataFrame) -> pd.DataFrame:
    """1) Cliente-consistency: se algum row do cliente tem BU explicita
       (BU Finance/Health/Logistics/Multisector/Retail/Others), propaga essa
       BU pras outras linhas do MESMO cliente — a BU explicita ganha sobre
       Hyper e Others. Respeita o que veio da planilha de origem.
    2) HYPER list: clientes que ainda estao em "Others" (sem nenhuma BU
       explicita em lugar nenhum) e estao na carteira Hyper -> "Hyper".
    """
    if "nome_cliente" not in df.columns or "vertical" not in df.columns:
        return df
    BU_DEF = {"BU Finance", "BU Health", "BU Logistics",
              "BU Multisector", "BU Retail", "BU Others"}
    nc = df["nome_cliente"].fillna("").astype(str).str.upper().str.strip()
    v  = df["vertical"].fillna("").astype(str).str.strip()

    # 1) Propaga BU explicita por cliente
    explicit_rows = df[v.isin(BU_DEF)]
    if not explicit_rows.empty:
        explicit_by_cli = (explicit_rows.groupby("nome_cliente")["vertical"]
                           .agg(lambda s: s.mode().iloc[0] if len(s.mode()) else s.iloc[0]))
        mapped = df["nome_cliente"].map(explicit_by_cli)
        mask_prop = mapped.notna() & ~v.isin(BU_DEF)
        if mask_prop.any():
            df.loc[mask_prop, "vertical"] = mapped[mask_prop]

    # 2) Aplica HYPER nos que sobraram em Others (clientes da carteira sem
    #    nenhuma BU explicita em lugar nenhum)
    v2 = df["vertical"].fillna("").astype(str).str.strip()
    mask = nc.isin(HYPER_CLIENTES) & v2.str.lower().eq("others")
    if mask.any():
        df.loc[mask, "vertical"] = "Hyper"
    return df


def _aplicar_vertical_por_pep(df: pd.DataFrame) -> pd.DataFrame:
    """Deriva a vertical (BU) a partir do PEP (projeto) e, como fallback, do cliente.
    O projeto define a BU — nao o cadastro da pessoa.
    Precedencia: pep_vertical (mais especifico) > clientes (fallback) > cadastro.
    Linhas sem PEP e sem cliente mapeado mantem a vertical atual.
    """
    import unicodedata, re
    VERT_MAP = {
        "Finance": "BU Finance", "Retail": "BU Retail", "Health": "BU Health",
        "Multisector": "BU Multisector", "Logistics": "BU Logistics",
        "Grupo Mult": "BU Logistics",
    }

    def _norm(s):
        if not isinstance(s, str):
            return ""
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"\s+", " ", s).strip().upper()

    # Versao "nucleo": tira pontuacao, sufixos corporativos e codigos finais
    # (ex: "GRUPO CASAS BAHIA S.A." e "GRUPO CASAS BAHIA S.A" viram a mesma chave)
    _SUFIXOS = re.compile(r"\b(S\.?\s?A\.?|S/?A|LTDA|EIRELI|ME|EPP|SA)\b", re.IGNORECASE)
    def _core(s):
        s = _norm(s)
        s = re.sub(r"\s*-\s*\d[\d\-/.]*$", "", s)  # remove sufixo " - 0001-51"
        s = _SUFIXOS.sub("", s)
        s = re.sub(r"[^A-Z0-9 ]", "", s)
        return re.sub(r"\s+", " ", s).strip()

    # 1. Fallback por cliente: usa abas `clientes` E `budget` do parametros.xlsx.
    #    Match: exato > nucleo > prefixo (nome curto do mapa e inicio do nome longo).
    try:
        cli_map = {}       # match exato (norm)
        cli_core_map = {}  # match por nucleo
        prefix_list = []   # [(core_curto, bu)] pra match por prefixo

        def _add(nome_raw, bu):
            for parte in str(nome_raw or "").split("|"):
                nome = _norm(parte)
                if nome:
                    cli_map.setdefault(nome, bu)
                core = _core(parte)
                if core and len(core) >= 4:
                    cli_core_map.setdefault(core, bu)

        # aba clientes
        try:
            cl = read_sheet_cached("clientes", dtype=str)
            for _, r in cl.iterrows():
                bu_raw = str(r.get("bu") or "").strip()
                if not bu_raw or bu_raw.lower().startswith("health nao"):
                    continue
                bu = VERT_MAP.get(bu_raw, bu_raw)
                _add(r.get("nome_cliente"), bu)
                _add(r.get("nome_base"), bu)
        except Exception as e:
            print(f"[clientes sheet] {e}")
        # aba budget (cliente -> bs)
        try:
            bg = read_sheet_cached("budget", dtype=str)
            for _, r in bg.drop_duplicates("cliente").iterrows():
                bu_raw = str(r.get("bs") or "").strip()
                if not bu_raw or bu_raw.lower().startswith("health nao"):
                    continue
                bu = VERT_MAP.get(bu_raw, bu_raw)
                _add(r.get("cliente"), bu)
        except Exception as e:
            print(f"[budget sheet] {e}")

        # lista pra prefixo: nucleos com >= 6 chars, mais longos primeiro
        prefix_list = sorted(
            ((c, b) for c, b in cli_core_map.items() if len(c) >= 6),
            key=lambda x: -len(x[0]),
        )

        def _resolve(nome):
            n = _norm(nome)
            if n in cli_map:
                return cli_map[n]
            c = _core(nome)
            if c in cli_core_map:
                return cli_core_map[c]
            # prefixo: nome do mapa e inicio do nome da base (com fronteira de palavra)
            for mcore, bu in prefix_list:
                if c == mcore or c.startswith(mcore + " "):
                    return bu
            return None

        if cli_map and "nome_cliente" in df.columns:
            # resolve por valor distinto (rapido)
            distintos = df["nome_cliente"].fillna("").unique()
            resol = {nc: _resolve(nc) for nc in distintos}
            override = df["nome_cliente"].fillna("").map(resol)
            # NAO sobrepoe BU explicita da linha de origem (planilha) — so
            # preenche onde a vertical esta vazia/Others.
            _BU_DEF = {"BU Finance", "BU Health", "BU Logistics",
                       "BU Multisector", "BU Retail", "BU Others"}
            v_cur = df["vertical"].fillna("").astype(str).str.strip()
            mask_apply = override.notna() & ~v_cur.isin(_BU_DEF)
            df.loc[mask_apply, "vertical"] = override[mask_apply]
    except Exception as e:
        print(f"[vertical_por_cliente] falhou: {e}")

    # 2. PEP override (mais especifico — prevalece sobre o fallback de cliente)
    if "pep_base" not in df.columns and "pep" not in df.columns:
        return df
    try:
        pv = read_sheet_cached("pep_vertical", dtype=str).dropna(subset=["pep", "vertical"])
        pv_map = {}
        for _, r in pv.iterrows():
            pep = str(r["pep"]).strip()
            v = str(r["vertical"]).strip()
            if pep:
                pv_map[pep] = VERT_MAP.get(v, v)
        for col in ("pep_base", "pep"):
            if col not in df.columns:
                continue
            key = df[col].fillna("").astype(str).str.strip()
            override = key.map(pv_map)
            df.loc[override.notna(), "vertical"] = override[override.notna()]
    except Exception as e:
        print(f"[vertical_por_pep] falhou: {e}")

    # 3. Consistencia por cliente: 1 cliente = 1 BU. Se o cliente tem alguma
    #    linha com BU oficial, a BU dominante e aplicada em TODAS as linhas dele.
    try:
        BUS_OK = {"BU Finance", "BU Retail", "BU Health", "BU Multisector", "BU Logistics"}
        if "nome_cliente" in df.columns:
            cli = df["nome_cliente"].fillna("").astype(str).str.strip()
            vv = df["vertical"].fillna("").astype(str).str.strip()
            mask_ok = vv.isin(BUS_OK) & cli.ne("") & ~cli.isin(["0", "nan"])
            if mask_ok.any():
                dom = (df.loc[mask_ok]
                       .assign(_c=cli[mask_ok], _v=vv[mask_ok])
                       .groupby("_c")["_v"]
                       .agg(lambda s: s.mode().iloc[0]))
                dom_map = dom.to_dict()
                cli_bu = cli.map(dom_map)
                # Preserva BU explicita da linha de origem (planilha): so aplica
                # a BU dominante onde a linha esta vazia/Others.
                aplica = (cli_bu.notna() & cli.ne("") & ~cli.isin(["0", "nan"])
                          & ~vv.isin(BUS_OK))
                df.loc[aplica, "vertical"] = cli_bu[aplica]
    except Exception as e:
        print(f"[vertical_consistencia_cliente] falhou: {e}")

    # 4. Clientes que devem ficar SEM BU (decisao de negocio) — vertical em branco.
    try:
        if "nome_cliente" in df.columns:
            nc_norm = df["nome_cliente"].fillna("").astype(str).apply(
                lambda s: re.sub(r"\s+", " ", str(s)).strip().upper())
            sem_bu = nc_norm.str.contains("DISTRITO", na=False)
            df.loc[sem_bu, "vertical"] = ""
    except Exception as e:
        print(f"[vertical_sem_bu] falhou: {e}")

    # 5. Override: lista de clientes que pertencem a "Hyper" (FCamara Hyper).
    # NAO sobrepoe BU oficial — so muda quando o cliente esta sem BU (Others,
    # vazio, etc.). Se o dado de origem (racional/planilha) diz BU Multisector,
    # essa BU ganha sobre o override Hyper.
    try:
        if "nome_cliente" in df.columns:
            nc_hy = df["nome_cliente"].fillna("").astype(str).apply(
                lambda s: re.sub(r"\s+", " ", str(s)).strip().upper())
            CLIENTES_HYPER = {
                "AB INBEV",
                "ALGAR", "ALGAR TELECOM", "ALGAR TELECOM S/A",
                "ALVEAN",
                "AMBIPAR", "AMBIPAR PARTICIPACOES E EMPREENDIMENTOS",
                "BANCO BV", "BANCO VOTORANTIM S.A.", "BV",
                "BANCO MUFG", "BANCO MUFG BRASIL S.A.", "MUFG",
                "BANCO VOLKSWAGEN",
                "BRASILPREV",
                "BRF", "BRASIL FOODS (BRF)",
                "BS2",
                "CIATECH",
                "CIRION", "CIRION TECHNOLOGIES DO BRASIL LTDA",
                "COBAP",
                "COPERSUCAR",
                "CPFL ENERGIA", "CPFL PAULISTA",
                "CREFISA",
                "CVC BRASIL",
                "DANONE",
                "DEL TORO", "DEL TORO LOAN SERVICING, INC",
                "DEXCO", "DURATEX", "DURATEX S.A.",
                "ELECTROLUX", "ELECTROLUX DO BRASIL S/A",
                "EQUINIX",
                "EVOLUA",
                "FC HYPER",
                "FCAMARA", "GRUPO FCAMARA",
                "FIS",
                "GRU",
                "GRUPO CASAS BAHIA", "GRUPO CASAS BAHIA S.A.",
                "GRUPO ELFA",
                "GRUPO HYPERAUTOMATION",
                "GRUPO RODOBENS", "RODOBENS",
                "HDI",
                "HEXIS",
                "IBM", "IBM BRASIL-INDUSTRIA MAQUINAS E SER",
                "INGRAM",
                "INTEGRATION",
                "INTERCEMENT",
                "IRANI", "IRANI PAPEL E EMBALAGEM S.A.",
                "KYNDRYL", "KYNDRYL BRASIL SERVICOS LTDA.",
                "LIGGA", "LIGGA TELECOM",
                "LINKCALL", "LINKCALL SERVICOS DE CALL CENTER S.A",
                "MARFRIG",
                "MARISTA",
                "MERCADO LIVRE", "MERCADO LIVRE /MERCADO.PAGO",
                "MULTIPLAN", "MULTIPLAN EMPREENDIMENTOS IMOB S/A",
                "MULTIPLAN EMPREENDIMENTOS IMOBILIARIOS S",
                "NEXA RESOURCES",
                "NUCLEA", "CIP / NUCLEA", "CIP S.A.",
                "ODONTOPREV", "ODONTOPREV S.A.",
                "OLX",
                "OURIBANK",
                "PARAISO GOLD",
                "PORTICO",
                "PRIVALIA",
                "REDHAT", "RED HAT", "RED HAT BRASIL LTDA",
                "RIACHUELO",
                "RUMO", "RUMO S.A.",
                "SMILES",
                "SOMPO",
                "TD SYNNEX", "TD SYNNEX BRASIL LTDA",
                "TELEFONICA",
                "TOKIO MARINE", "TOKIO MARINE SEGURADORA S.A.",
                "TOYOTA",
                "ULTRA", "GRUPO ULTRA", "ULTRAPAR PARTICIPACOES S/A",
                "UNIMED", "UNIMED CURITIBA", "UNIMED NACIONAL",
                "VIA VAREJO",
                "VIGOR",
                "VLI",
                "ZENVIA",
            }
            _BU_DEF = {"BU Finance","BU Health","BU Logistics",
                       "BU Multisector","BU Retail","BU Others"}
            v_cur = df["vertical"].fillna("").astype(str).str.strip()
            df.loc[nc_hy.isin(CLIENTES_HYPER) & ~v_cur.isin(_BU_DEF), "vertical"] = "Hyper"
    except Exception as e:
        print(f"[vertical_hyper] falhou: {e}")

    # 6. Locks finais: clientes onde a BU eh decisao de negocio absoluta
    #    (sobrescreve qualquer override de PEP/cadastro).
    try:
        if "nome_cliente" in df.columns:
            nc_lock = df["nome_cliente"].fillna("").astype(str).apply(
                lambda s: re.sub(r"\s+", " ", str(s)).strip().upper())
            df.loc[nc_lock.str.contains("TRANSUNION", na=False), "vertical"] = "BU Finance"
    except Exception as e:
        print(f"[vertical_locks] falhou: {e}")
    return df


def _adicionar_fonte_familia(df: pd.DataFrame) -> pd.DataFrame:
    """Cria coluna virtual `fonte_familia` agrupando arquivos individuais em famílias:
    - Mapa Pessoas
    - Custo Gerencial
    - Custo Project
    - Racionais
    """
    if "fonte_dados" not in df.columns:
        df["fonte_familia"] = ""
        return df
    fd = df["fonte_dados"].fillna("").astype(str)
    fonte_col = df.get("fonte", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str)
    familia = pd.Series("", index=df.index)
    familia[fd.str.startswith("Mapa Pessoas", na=False)] = "Mapa Pessoas"
    familia[fd.str.startswith("Custo Gerencial", na=False) | fd.str.startswith("Gerencial V", na=False)] = "Custo Gerencial"
    familia[fd.str.startswith("custo_project", na=False)] = "Custo Project"
    # Tudo que veio com fonte=racionais e nao bateu acima vai pra Racionais
    mask_rac = (familia == "") & (fonte_col == "racionais")
    familia[mask_rac] = "Racionais"
    # Resto (Hyper, SGA, DOJO, Custo Socios, etc.): usa o proprio nome da fonte,
    # pra cada uma virar uma opcao filtravel (antes caía tudo em "Outros").
    _resto = familia == ""
    familia[_resto] = fonte_col[_resto].where(fonte_col[_resto].str.strip() != "", "Outros")
    # PJ e CLT viram familias proprias (pelo fonte), pra permitir filtrar separado.
    familia[fonte_col == "PJs"]  = "PJs"
    familia[fonte_col == "CLTs"] = "CLTs"
    df["fonte_familia"] = familia
    return df


def _enriquecer_dados_pessoa(df: pd.DataFrame) -> pd.DataFrame:
    """Propaga campos cadastrais (tipo_contrato, billable_category, area, macro_area,
    funcao) entre todas as linhas da mesma pessoa.

    Prioridade: Mapa Pessoas (CLTs/PJs) > demais fontes. Em caso de conflito, mantém
    o valor de Mapa Pessoas.

    Uma pessoa cadastrada como CLT/FP&A/Backoffice no Mapa Pessoas aparece com
    esses campos em TODAS as suas linhas, mesmo nas outras fontes.
    """
    import unicodedata

    # Aliases de nome de cliente — variantes que são o mesmo cliente.
    # Chave = nome normalizado (UPPER, sem espaços extras); valor = nome canônico.
    NOME_CLIENTE_ALIAS = {
        "CARTOS": "CARTOS",
        "CARTOS SOCIEDADE DE CREDITO DIRETO": "CARTOS",
        "CARTOS SOCIEDADE DE CREDITO DIRETO S.A.": "CARTOS",
        "CBMM": "CBMM",
        "COMPANHIA BRASILEIRA DE METALURGIA E MIN": "CBMM",
        "COMPANHIA BRASILEIRA DE METALURGIA E MINERACAO": "CBMM",
        "11406-RIACHUELO": "Riachuelo",
        "LOJAS RIACHUELO SA": "Riachuelo",
        "RIACHUELO": "Riachuelo",
        "DEDICATED TEAMS BIRMINGHAM": "BIRMINGHAM BANK",
        "SQUAD BIRMINGHAM BANK": "BIRMINGHAM BANK",
        "MANDIC": "Mandic",
        "ALOCACAO MANDIC": "Mandic",
        "SOCIEDADE REGIONAL DE ENSINO E SAUD": "Mandic",
        "SOCIEDADE REGIONAL DE ENSINO E SAUDE LTD": "Mandic",
        "SOCIEDADE REGIONAL DE ENSINO E SAUDE LTDA": "Mandic",
        "SADA": "SADA TRANSPORTES E ARMAZENAGENS LTDA",
        "SADA TRANSPORTES": "SADA TRANSPORTES E ARMAZENAGENS LTDA",
        "SADA TRANSPORTES E ARMAZENAGENS LTD": "SADA TRANSPORTES E ARMAZENAGENS LTDA",
        "SADA TRANSPORTES E ARMAZENAGENS LTDA": "SADA TRANSPORTES E ARMAZENAGENS LTDA",
        "M33 CONSULTORIA, MEDICINA E GESTAO": "M33 CONSULTORIA, MEDICINA E GESTAO LTDA",
        "M33 CONSULTORIA, MEDICINA E GESTAO LTDA": "M33 CONSULTORIA, MEDICINA E GESTAO LTDA",
        "RAIA DROGASIL S/A - 0001-51": "RAIA DROGASIL S/A",
        "RAIA DROGASIL S/A": "RAIA DROGASIL S/A",
        "STRADA PAY INSTITUICAO DE PAGAMENTO": "STRADA PAY INSTITUICAO DE PAGAMENTO LTDA",
        "STRADA PAY INSTITUICAO DE PAGAMENTO LTDA": "STRADA PAY INSTITUICAO DE PAGAMENTO LTDA",
        "DANONE": "DANONE",
        "DANONE LTDA": "DANONE",
        "TRANSUNION": "TransUnion",
        "TRANSUNION BRASIL SISTEMAS EM INFOR": "TransUnion",
        "TRANSUNION BRASIL SISTEMAS EM INFORMATIC": "TransUnion",
        "BANCO BV": "BANCO VOTORANTIM S.A.",
        "ODONTOPREV": "ODONTOPREV S.A.",
        "ODONTOPREV S.A.": "ODONTOPREV S.A.",
        "ODONTOPREV - TESTES ALWAYS ON": "ODONTOPREV S.A.",
        "ALGAR TELECOM S/A": "ALGAR TELECOM S/A",
        "ALGAR TELECOM": "ALGAR TELECOM S/A",
        "AMPM": "AmPm",
        "BANCO INTER S.A": "BANCO INTER S.A.",
        "BANCO INTER": "BANCO INTER S.A.",
        "ELECTROLUX DO BRASIL S/A": "ELECTROLUX DO BRASIL S/A",
        "GRUPO CASAS BAHIA S.A": "GRUPO CASAS BAHIA S.A.",
        "GRUPO CASAS BAHIA S.A.": "GRUPO CASAS BAHIA S.A.",
        "KLABIN": "KLABIN S.A.",
        "KLABIN S.A.": "KLABIN S.A.",
        "RED HAT BRASIL LTDA": "RED HAT BRASIL LTDA",
        "RED HAT": "RED HAT BRASIL LTDA",
        "RENNER": "RENNER",
        "RUMO": "RUMO S.A.",
        "RUMO S.A": "RUMO S.A.",
        "RUMO S.A.": "RUMO S.A.",
        # Pares receita-side <-> custo-side unificados (estudo de coerencia 2026-05)
        "CIRION": "CIRION TECHNOLOGIES DO BRASIL LTDA",
        "CIRION TECHNOLOGIES DO BRASIL LTDA": "CIRION TECHNOLOGIES DO BRASIL LTDA",
        "FUTEBOLCARD - TRANSFORMATION": "FUTEBOLCARD SISTEMAS LTDA",
        "FUTEBOLCARD SISTEMAS LTDA": "FUTEBOLCARD SISTEMAS LTDA",
        "DEL TORO - FL 01 - US/AZ": "DEL TORO LOAN SERVICING, INC",
        "DEL TORO LOAN SERVICING, INC": "DEL TORO LOAN SERVICING, INC",
        "BANCO DE TOKYO-MITSUBISHI UFJ BRASIL S/A": "BANCO MUFG BRASIL S.A.",
        "BANCO MUFG BRASIL S.A.": "BANCO MUFG BRASIL S.A.",
        "GRUPO ULTRA": "ULTRAPAR PARTICIPACOES S/A",
        "ULTRAPAR PARTICIPACOES S/A": "ULTRAPAR PARTICIPACOES S/A",
        "DEXCO": "DEXCO",
        "DURATEX S.A.": "DEXCO",
        "GRANI AMICI INDUSTRIA E COMERCIO DE": "GRANI AMICI INDUSTRIA E COMERCIO DE ALIM",
        "GRANI AMICI INDUSTRIA E COMERCIO DE ALIM": "GRANI AMICI INDUSTRIA E COMERCIO DE ALIM",
        "MULTIPLAN": "MULTIPLAN EMPREENDIMENTOS IMOBILIARIOS S",
        "MULTIPLAN EMPREENDIMENTOS IMOBILIARIOS S": "MULTIPLAN EMPREENDIMENTOS IMOBILIARIOS S",
        "VR BENEFICIOS E SERVICOS DE PROCESS": "VR BENEFICIOS E SERVICOS DE PROCESSAMENT",
        "VR BENEFICIOS E SERVICOS DE PROCESSAMENT": "VR BENEFICIOS E SERVICOS DE PROCESSAMENT",
        "FUN BRANDS": "FUN BRANDS LLC",
        "FUN BRANDS LLC": "FUN BRANDS LLC",
        "OBVIO BRASIL": "OBVIO BRASIL SOFTWARE E SERVICOS LTDA",
        "OBVIO BRASIL SOFTWARE E SERVICOS LTDA": "OBVIO BRASIL SOFTWARE E SERVICOS LTDA",
        "IRANI": "IRANI PAPEL E EMBALAGEM S.A.",
        "IRANI PAPEL E EMBALAGEM S.A.": "IRANI PAPEL E EMBALAGEM S.A.",
        "RIMINI STREET BRAZIL SERVICOS DE TE": "RIMINI STREET BRAZIL SERVICOS DE TECNOLO",
        "RIMINI STREET BRAZIL SERVICOS DE TECNOLO": "RIMINI STREET BRAZIL SERVICOS DE TECNOLO",
        "TOKIO MARINE": "TOKIO MARINE SEGURADORA S.A.",
        "TOKIO MARINE SEGURADORA S.A.": "TOKIO MARINE SEGURADORA S.A.",
        "CIP / NUCLEA": "CIP S.A.",
        "CIP S.A.": "CIP S.A.",
        "COOPERATIVA CENTRAL DOS PRODUTORES": "COOPERATIVA CENTRAL DOS PRODUTORES RURAI",
        "COOPERATIVA CENTRAL DOS PRODUTORES RURAI": "COOPERATIVA CENTRAL DOS PRODUTORES RURAI",
        # Unimeds: unifica variantes DENTRO de cada cidade (mantem cidades separadas)
        "UNIMED BELO HORIZONTE": "UNIMED BELO HORIZONTE",
        "UNIMED BELO HORIZONTE COOPERATIVA DE TRA": "UNIMED BELO HORIZONTE",
        "UNIMED BELO HORIZONTE COOPERATIVA D": "UNIMED BELO HORIZONTE",
        "UNIMED": "UNIMED NACIONAL",
        "UNIMED CURITIBA": "UNIMED CURITIBA",
        "UNIMED CURITIBA - SOCIEDADE COOPERA": "UNIMED CURITIBA",
        "UNIMED CURITIBA - SOCIEDADE COOPERATIVA": "UNIMED CURITIBA",
        "UNIMED NACIONAL": "UNIMED NACIONAL",
        "UNIMED NACIONAL - COOPERATIVA CENTRAL": "UNIMED NACIONAL",
        "UNIMED DO ESTADO DE SAO PAULO": "UNIMED DO ESTADO DE SAO PAULO",
        "UNIMED DO ESTADO DE SAO PAULO - FED": "UNIMED DO ESTADO DE SAO PAULO",
        "UNIMED DO ESTADO DE SAO PAULO - FEDERACA": "UNIMED DO ESTADO DE SAO PAULO",
    }
    if "nome_cliente" in df.columns:
        _nc = (df["nome_cliente"].fillna("").astype(str)
               .str.strip().str.replace(r"\s+", " ", regex=True))
        _nck = _nc.str.upper()
        df["nome_cliente"] = _nck.map(NOME_CLIENTE_ALIAS).fillna(_nc)
        # FutebolCard tem variante com encoding (Monetização) — casa por prefixo.
        df.loc[df["nome_cliente"].astype(str).str.upper().str.startswith("FUTEBOLCARD"),
               "nome_cliente"] = "FUTEBOLCARD SISTEMAS LTDA"

    # Aliases de nome de empresa — variantes da mesma empresa em grafias diferentes.
    EMPRESA_ALIAS = {
        "BETA-I": "BETA-I",
        "BETAI":  "BETA-I",
        "DFENSE": "Dfense",
        "DFENSE (VIPERX)": "Dfense",
    }
    if "empresa" in df.columns:
        _e  = df["empresa"].fillna("").astype(str).str.strip()
        _ek = _e.str.upper()
        df["empresa"] = _ek.map(EMPRESA_ALIAS).fillna(_e)

    if "nome_pessoa" not in df.columns:
        return df

    def _norm(s):
        s = s.fillna("").astype(str).str.upper().str.strip()
        s = s.str.replace(r"\s+", " ", regex=True)
        s = s.apply(lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("ascii") if x else x)
        # Remove prefixo numerico (CPF/CNPJ na frente do nome): "56.934.070 NOME" -> "NOME"
        s = s.str.replace(r"^[\d./\-]+\s+", "", regex=True)
        # Normaliza " DO SANTOS"/" DA SANTOS"/etc -> " DOS SANTOS"/" DAS SANTOS"
        # (typo recorrente: Orange usa "do Santos", outras fontes "dos Santos")
        s = s.str.replace(r"\bDO SANTOS\b", "DOS SANTOS", regex=True)
        return s

    nome_norm = _norm(df["nome_pessoa"])
    df["_pessoa_key"] = nome_norm

    # Aliases manuais nome_pessoa — casos que a heuristica nao pega
    # (ex: nome curto com 2 palavras vs nome longo com 3+).
    NOME_PESSOA_ALIAS = {
        # Truncamentos (corte em 32-36 chars no upload original)
        "ALINE NAYARA PEREIRA DE LIMA GOME": "ALINE NAYARA PEREIRA DE LIMA GOMES",
        "ALLESSON RODRIGO CAVALCANTE DA SI": "ALLESSON RODRIGO CAVALCANTE DA SILVA",
        "ANA CRISTINA CONCEICAO MALVEIRA N": "ANA CRISTINA CONCEICAO MALVEIRA NOGUEIRA",
        "ANA PAULA RODRIGUES PAIVA FERREIR": "ANA PAULA RODRIGUES PAIVA FERREIRA",
        "CAIO CEZAR BARBOSA DA SILVA BATIS": "CAIO CEZAR BARBOSA DA SILVA BATISTA",
        "CICERO ALYSSON DO NASCIMENTO ARAU": "CICERO ALYSSON DO NASCIMENTO ARAUJO",
        "DANIEL ARISTOTELIS ASSUNCAO DA SI": "DANIEL ARISTOTELIS ASSUNCAO DA SILVA",
        "ERIBERTO SANTANA FLORENCIO DE LIM": "ERIBERTO SANTANA FLORENCIO DE LIMA",
        "FERNANDO ANTONIO PARAISO CAVALCAN": "FERNANDO ANTONIO PARAISO CAVALCANTI",
        "FERNANDO JOSE ALVES DA SILVA JUNI": "FERNANDO JOSE ALVES DA SILVA JUNIOR",
        "GABRIELLA MARIA BACK BEBIANO MONT": "GABRIELLA MARIA BACK BEBIANO MONTINI",
        "GABRIELLY VITORIA RODRIGUES DOS S": "GABRIELLY VITORIA RODRIGUES DOS SANTOS",
        "GISLAINE CRISTINA RIBEIRO MENEGAT": "GISLAINE CRISTINA RIBEIRO MENEGATTI",
        "GUILHERME ISSAMU NASCIMENTO KISHI": "GUILHERME ISSAMU NASCIMENTO KISHIDA",
        "HENRIQUE ANTONIO CONTADOR PANTARO": "HENRIQUE ANTONIO CONTADOR PANTAROTO",
        "ISABELLE DE ARAUJO RODRIGUES VIEI": "ISABELLE DE ARAUJO RODRIGUES VIEIRA",
        "JAMILLE RENATA FERREIRA PEREIRA R": "JAMILLE RENATA FERREIRA PEREIRA RICHTER",
        "JENNIFER PALOMA DE MORAES MARCIAN": "JENNIFER PALOMA DE MORAES MARCIANO",
        "JERONIMO DOS REIS CORDEIRO DE PAI": "JERONIMO DOS REIS CORDEIRO DE PAIVA",
        "JOAO BATISTA OLIVEIRA DE SOUZA JU": "JOAO BATISTA OLIVEIRA DE SOUZA JUNIOR",
        "JOAO OCTAVIO TOGNI ZAMBON MANTOVA": "JOAO OCTAVIO TOGNI ZAMBON MANTOVANI",
        "JONATAN CRISTOFER TEIXEIRA ALBUQU": "JONATAN CRISTOFER TEIXEIRA ALBUQUERQUE",
        "JUDSON KERLLER ALVES MORAIS JUNIO": "JUDSON KERLLER ALVES MORAIS JUNIOR",
        "KAISA FERNANDA PEREIRA DE ALMEIDA SANTIA": "KAISA FERNANDA PEREIRA DE ALMEIDA SANTIAGO",
        "MARCIA ANDREA LOPES DE OLIVEIRA E": "MARCIA ANDREA LOPES DE OLIVEIRA EDEL",
        "MARIA GABRIELA QUINTAO NEUBERT FE": "MARIA GABRIELA QUINTAO NEUBERT FERNANDES",
        "MARIANA DA CONCEICAO ALVES DA SIL": "MARIANA DA CONCEICAO ALVES DA SILVA",
        "MATHEUS HENRIQUE VALENTIM FERNAND": "MATHEUS HENRIQUE VALENTIM FERNANDES",
        "MAURICIO ANTUNES NASCIMENTO DOS S": "MAURICIO ANTUNES NASCIMENTO DOS SANTOS",
        "PABLO APARECIDO TEIXEIRA DE OLIVE": "PABLO APARECIDO TEIXEIRA DE OLIVEIRA",
        "PAULA CUNHA MEDEIROS DE ALMEIDA A": "PAULA CUNHA MEDEIROS DE ALMEIDA ALCALA",
        "PAULO DE ALMEIDA COSTA NONATO FIL": "PAULO DE ALMEIDA COSTA NONATO FILHO",
        "PEDRO HENRIQUE DALMAZO GARCIA BAR": "PEDRO HENRIQUE DALMAZO GARCIA BARRETO",
        "RAFAEL MARTINS CORDEIRO DOS SANTO": "RAFAEL MARTINS CORDEIRO DOS SANTOS",
        "RIAN DE OLIVEIRA NORONHA RODRIGUE": "RIAN DE OLIVEIRA NORONHA RODRIGUES",
        "RODRIGO RODRIGUEZ F DE OLIVEIRA S": "RODRIGO RODRIGUEZ F DE OLIVEIRA SILVA",
        "SUZANA CRISTINA PEREIRA DE OLIVEI": "SUZANA CRISTINA PEREIRA DE OLIVEIRA",
        "THARSIS LAMIN LUMUMBA BOA MORTE Q": "THARSIS LAMIN LUMUMBA BOA MORTE QUEIROZ",
        "VINICIUS MATHEUS SOUZA OLIVEIRA S": "VINICIUS MATHEUS SOUZA OLIVEIRA SANTOS",
        "VINICIUS PEREIRA AMARAL DOS SANTO": "VINICIUS PEREIRA AMARAL DOS SANTOS",
        "VINICIUS RICARDO DA SILVA FERREIR": "VINICIUS RICARDO DA SILVA FERREIRA",
        "WALTER DO ESPIRITO SANTO SOUZA FI": "WALTER DO ESPIRITO SANTO SOUZA FILHO",
        "WELLINGTON LUIZ BENEDITO OSTEMBER": "WELLINGTON LUIZ BENEDITO OSTEMBERG",

        # JR / JUNIOR
        "JOAO FELIX MEDEIROS JR": "JOAO FELIX MEDEIROS JUNIOR",
        "MARIO CESAR MIRANDA JR": "MARIO CESAR MIRANDA JUNIOR",
        "PAULO CESAR DE ALMEIDA FERREIRA JR": "PAULO CEZAR DE ALMEIDA FERREIRA JUNIOR",
        "PAULO CEZAR DE ALMEIDA FERREIRA JR": "PAULO CEZAR DE ALMEIDA FERREIRA JUNIOR",
        "PAULO CEZAR DE ALMEIDA FERREIRA J": "PAULO CEZAR DE ALMEIDA FERREIRA JUNIOR",

        # Typos / variantes de grafia
        "ALAN VILAS BOAS MORELLI": "ALAN VILLAS BOAS MORELLI",
        "ALEXANDRE WILLIAN DA SILVA": "ALEXANDRE WILLIAM DA SILVA",
        "BRUNO PASSOS MOARES": "BRUNO PASSOS MORAES",
        "FELIPE DE ASSUNCAO ARAUJO": "FELIPE DE ASSUMPCAO ARAUJO",
        "FELIPE LOBO DE OLIVEIRA VALIM": "FELIPE LOBO DE OLIVEIRA VALLIM",
        "GUSTAVO ALBURQUERQUE LIMA": "GUSTAVO ALBUQUERQUE LIMA",
        "IGOR MOREIRA DELESPOTI": "IGOR MOREIRA DELESPOSTI",
        "JOAO CARLOS MAZIEIRO": "JOAO CARLOS MAZIERO",
        "JOSE RICARDO DAMACENO DOS REIS": "JOSE RICARDO DAMASCENO DOS REIS",
        "KAIQUE SPAGNOL TOFOLI": "KAIQUE SPAGNOL TOFFOLI",
        "LARISSA CHARADIA DA SILVA": "LARISSA CHIARADIA DA SILVA",
        "LEONARDO DA SIVA PIPOLI": "LEONARDO DA SILVA PIPOLI",
        "LEONARDO SOUZA CARVALHO": "LEONARDO SOUSA CARVALHO",
        "LETICIA DANIELE PEROTI": "LETICIA DANIELE PEROTTI",
        "LINHA SETE SOLUAAES LTDA": "LINHA SETE SOLUCOES LTDA",
        "MARCELO QUADRELI OINHEIRO": "MARCELO QUADRELLI PINHEIRO",
        "MATHEUS MAGALHAES BASBOSA CAMPELO": "MATHEUS MAGALHAES BARBOSA CAMPELO",
        "PATRICK ALAN CUSTODIO": "PATRICK ALLAN CUSTODIO",
        "PEDRO SIQUIRA NETO": "PEDRO SIQUEIRA NETO",
        "PEDRO VIEIRA DE SOUZA NETO": "PEDRO VIEIRA DE SOUSA NETO",
        "TATIANE CORREA CAMILO": "TATIANE CORREIA CAMILO",
        "THIAGO RAMA DA SIVA": "THIAGO RAMA DA SILVA",
        "VITOR SANDER BARREIROS DE OLIVERA": "VITOR SANDER BARREIROS DE OLIVEIRA",
        "WANDER WILLIAN DE OLIVEIRA": "WANDER WILLIAM DE OLIVEIRA",
        "WELLINGTON BORGES DE SOUZA": "WELLINGTON BORGES DE SOUSA",

        # Apostrofe
        "ALEXANDRE AZEVEDO D'AMOEDO E SILVA": "ALEXANDRE AZEVEDO DAMOEDO E SILVA",

        # TDMs com variantes PJ (CNPJ/sufixo) -> nome canonico CLT
        "RAFAEL MACEDO": "RAFAEL MACEDO ROZALINO",
        "FERNANDO PEREIRA LISBOA TECNOLOGIA": "FERNANDO PEREIRA LISBOA",
        "LEONARDO BARBETTA DE OLIVEIRA TECNO": "LEONARDO BARBETTA DE OLIVEIRA",
        "JAMIL DIAS COSTA - ME": "JAMIL DIAS COSTA",
        "LEANDRO DE BRITO SISTEMAS": "LEANDRO DE BRITO",
        "FABIANO DA SILVA REMIAO MONTEIRO": "FABIANO DA SILVA REMIAO MONTEIRO",

        # Nome curto / abreviado vs completo
        "ANA CAROLINA TEORODO": "ANA CAROLINA TEODORO",
        "ANDSON LOURENCO": "ANDSON LOURENCO ALVES",
        "CATHARINA GAISSLER": "CATHARINA GAISSLER SANTOS",
        "MARCELA AN": "MARCELA AN.",
        "MATHEUS ANVERSA": "MATHEUS ANVERSA VIERA",
        "RAMON CAMPOS SILVA": "RAMON CAMPOS SILVA-SERVICOS",
        "ROSANGELA DANTAS": "ROSANGELA DANTAS LIMA",
        "STEPHANI BOECHAT": "STEPHANI BOECHAT ROCHA",
        "LUCIANE BALLE": "LUCIANE BALLE LTDA",
        "ANALISTA PLENO": "ANALISTA PLENO (GRC)",
    }
    df["_pessoa_key"] = df["_pessoa_key"].map(lambda x: NOME_PESSOA_ALIAS.get(x, x))
    nome_norm = df["_pessoa_key"]

    # Unificação de variantes de nome: nome curto que é prefixo (palavra-a-palavra)
    # de nome mais longo é considerado a mesma pessoa.
    # Exemplo: "JAMILLE RENATA FERREIRA PEREIRA" → "JAMILLE RENATA FERREIRA PEREIRA RICHTER"
    # Proteção contra homônimos: só unifica se CPFs não conflitam.
    cpf_d = df.get("cpf", pd.Series([""] * len(df), index=df.index)).astype(str).str.replace(r"[^\d]", "", regex=True)
    nomes_unicos = [n for n in df["_pessoa_key"].dropna().unique() if n != ""]
    # Indexa por primeiras 3 palavras
    prefix_idx: dict = {}
    for nome in nomes_unicos:
        palavras = nome.split()
        if len(palavras) >= 3:
            prefix3 = " ".join(palavras[:3])
            prefix_idx.setdefault(prefix3, []).append(nome)

    canonicos: dict = {}
    for prefix3, nomes_grupo in prefix_idx.items():
        if len(nomes_grupo) <= 1:
            continue
        nomes_sorted = sorted(nomes_grupo, key=lambda n: -len(n.split()))
        canonico = nomes_sorted[0]
        palavras_canon = canonico.split()
        # Coleta CPFs únicos das pessoas do grupo
        cpfs_grupo = set()
        for n in nomes_grupo:
            cpfs_n = cpf_d[df["_pessoa_key"] == n]
            cpfs_grupo |= set(cpfs_n[cpfs_n.str.len() >= 11].unique())
        # Se >1 CPF distinto, NÃO unifica (homônimos com CPFs diferentes)
        if len(cpfs_grupo) > 1:
            continue
        for nome in nomes_sorted[1:]:
            palavras = nome.split()
            if palavras_canon[:len(palavras)] == palavras:
                canonicos[nome] = canonico

    # Regra extra: nomes com mesmo número de palavras que diferem APENAS na última,
    # onde uma das últimas é abreviação (1-2 letras, prefixo da outra).
    # Ex: "JAMILLE RENATA FERREIRA PEREIRA R" + "...PEREIRA RICHTER" → mesma pessoa
    for prefix3, nomes_grupo in prefix_idx.items():
        if len(nomes_grupo) <= 1:
            continue
        # Agrupa por número de palavras
        for nome_a in nomes_grupo:
            for nome_b in nomes_grupo:
                if nome_a >= nome_b:
                    continue
                pa, pb = nome_a.split(), nome_b.split()
                if len(pa) != len(pb) or len(pa) < 3:
                    continue
                if pa[:-1] != pb[:-1]:
                    continue
                ultima_a, ultima_b = pa[-1], pb[-1]
                # Uma é abreviação da outra (1-2 letras E prefixo)
                if len(ultima_a) <= 2 and ultima_b.startswith(ultima_a):
                    canonicos[nome_a] = nome_b
                elif len(ultima_b) <= 2 and ultima_a.startswith(ultima_b):
                    canonicos[nome_b] = nome_a

    # Regra extra: nomes que ficam idênticos ao remover conectores
    # (DOS/DAS/DA/DE/DO/E) são a mesma pessoa.
    # Ex: "GABRIEL RAMOS DOS SANTOS" == "GABRIEL RAMOS SANTOS".
    _CONNS = {"DOS", "DAS", "DA", "DE", "DO", "E"}
    strip_idx: dict = {}
    for nome in nomes_unicos:
        nucleo = " ".join(p for p in nome.split() if p not in _CONNS)
        if len(nucleo.split()) >= 3:
            strip_idx.setdefault(nucleo, []).append(nome)
    for nucleo, grupo in strip_idx.items():
        if len(grupo) <= 1:
            continue
        cpfs_grupo = set()
        for n in grupo:
            cpfs_n = cpf_d[df["_pessoa_key"] == n]
            cpfs_grupo |= set(cpfs_n[cpfs_n.str.len() >= 11].unique())
        if len(cpfs_grupo) > 1:
            continue
        canonico = max(grupo, key=len)  # grafia mais completa
        for n in grupo:
            if n != canonico:
                canonicos[n] = canonico

    # Regra extra: pos-strip de conectores, unifica nomes onde a ultima
    # palavra de um e prefixo da outra (>= 4 chars) e as demais palavras batem.
    # Trata truncamento do tipo "DOS SANTO" vs "DOS SANTOS".
    strip_first3_idx: dict = {}
    for nome in nomes_unicos:
        nucleo = " ".join(p for p in nome.split() if p not in _CONNS)
        palavras = nucleo.split()
        if len(palavras) >= 3:
            chave = (" ".join(palavras[:-1]), palavras[-1][:4])
            strip_first3_idx.setdefault(chave, []).append(nome)
    for chave, grupo in strip_first3_idx.items():
        if len(grupo) <= 1:
            continue
        cpfs_grupo = set()
        for n in grupo:
            cpfs_n = cpf_d[df["_pessoa_key"] == n]
            cpfs_grupo |= set(cpfs_n[cpfs_n.str.len() >= 11].unique())
        if len(cpfs_grupo) > 1:
            continue
        canonico = max(grupo, key=len)
        for n in grupo:
            if n != canonico:
                canonicos[n] = canonico

    if canonicos:
        # Resolve transitividade: A → B, B → C ⇒ A → C
        for k in list(canonicos.keys()):
            v = canonicos[k]
            while v in canonicos and canonicos[v] != v:
                v = canonicos[v]
            canonicos[k] = v
        df["_pessoa_key"] = df["_pessoa_key"].map(lambda x: canonicos.get(x, x))
        nome_norm = df["_pessoa_key"]
        print(f"[unificar_nomes] {len(canonicos)} variantes de nome unificadas")

    # Sócios (pessoa em Custo Socios) → tipo_contrato="Socio" em TODAS as linhas dela.
    # Prioridade absoluta sobre CLT/PJ porque Sócio é regime de remuneração distinto.
    if "tipo_contrato" in df.columns:
        socios_keys = set(df.loc[df["fonte"].astype(str) == "Custo Socios", "_pessoa_key"]
                          .dropna().unique())
        socios_keys.discard("")
        if socios_keys:
            df.loc[df["_pessoa_key"].isin(socios_keys), "tipo_contrato"] = "Socio"

    # Resolve tipo_contrato="CLT/PJ" (ambíguo, 173 linhas / 35 pessoas):
    # - Se em outras linhas a pessoa só aparece como CLT → vira CLT
    # - Se só como PJ → vira PJ
    # - Se aparece como ambos → mantém "CLT/PJ" (conflito real, ex: 28 alternantes)
    if "tipo_contrato" in df.columns:
        tc_str = df["tipo_contrato"].fillna("").astype(str).str.strip()
        mask_def = tc_str.isin(["CLT", "PJ"])
        tipos_por_pessoa = (df[mask_def & (df["_pessoa_key"] != "")]
                            .groupby("_pessoa_key")["tipo_contrato"]
                            .agg(lambda s: set(s.astype(str).str.strip())))
        so_clt_keys = set(tipos_por_pessoa[tipos_por_pessoa == frozenset({"CLT"})].index) | \
                      set(tipos_por_pessoa[tipos_por_pessoa.apply(lambda x: x == {"CLT"})].index)
        so_pj_keys  = set(tipos_por_pessoa[tipos_por_pessoa.apply(lambda x: x == {"PJ"})].index)
        mask_ambiguo = (tc_str == "CLT/PJ")
        df.loc[mask_ambiguo & df["_pessoa_key"].isin(so_clt_keys), "tipo_contrato"] = "CLT"
        df.loc[mask_ambiguo & df["_pessoa_key"].isin(so_pj_keys), "tipo_contrato"] = "PJ"
        # Pessoas com ambos {CLT, PJ} mantém "CLT/PJ"

    campos = ["tipo_contrato", "billable_category", "classificacao", "area", "macro_area", "funcao"]
    fontes_mapa = ["CLTs", "PJs"]

    for campo in campos:
        if campo not in df.columns:
            continue
        tem_valor = df[campo].notna() & (df[campo].astype(str).str.strip() != "") & (df["_pessoa_key"] != "")
        is_mapa = df["fonte"].astype(str).isin(fontes_mapa) & tem_valor
        # Prioridade Mapa
        mapa_dict = (df[is_mapa].drop_duplicates("_pessoa_key")
                     .set_index("_pessoa_key")[campo].to_dict())
        # Fallback outras fontes
        outras_dict = (df[tem_valor & ~is_mapa].drop_duplicates("_pessoa_key")
                       .set_index("_pessoa_key")[campo].to_dict())
        # Mescla: outras primeiro, Mapa sobrescreve (prioridade)
        valor_dict = {**outras_dict, **mapa_dict}
        valor_dict.pop("", None)

        valor_propagado = nome_norm.map(valor_dict)
        mask_vazio = df[campo].isna() | (df[campo].astype(str).str.strip() == "")
        df.loc[mask_vazio, campo] = valor_propagado[mask_vazio]

    # Propagacao POR PERIODO (campos que variam mes a mes): nome_cliente, pep, pep_base, vertical.
    # Prioridade: racionais (autoridade de PEP+cliente) > CLTs/PJs (Mapa) > demais.
    campos_periodo = ["nome_cliente", "pep", "pep_base", "vertical"]
    if "periodo" in df.columns:
        per_str = df["periodo"].fillna("").astype(str)
        df["_pk"] = df["_pessoa_key"] + "|" + per_str
        for campo in campos_periodo:
            if campo not in df.columns:
                continue
            tem_valor = df[campo].notna() & (df[campo].astype(str).str.strip() != "") & (df["_pessoa_key"] != "") & (per_str != "")
            is_rac  = (df["fonte"].astype(str) == "racionais") & tem_valor
            is_mapa = df["fonte"].astype(str).isin(fontes_mapa) & tem_valor
            rac_dict   = df[is_rac].drop_duplicates("_pk").set_index("_pk")[campo].to_dict()
            mapa_dict  = df[is_mapa].drop_duplicates("_pk").set_index("_pk")[campo].to_dict()
            outras_dict = df[tem_valor & ~is_rac & ~is_mapa].drop_duplicates("_pk").set_index("_pk")[campo].to_dict()
            # Mescla: outras < mapa < racionais (precedencia)
            valor_dict = {**outras_dict, **mapa_dict, **rac_dict}
            valor_dict.pop("", None)
            valor_propagado = df["_pk"].map(valor_dict)
            mask_vazio = df[campo].isna() | (df[campo].astype(str).str.strip() == "")
            df.loc[mask_vazio, campo] = valor_propagado[mask_vazio]
        df.drop(columns=["_pk"], inplace=True, errors="ignore")

    # Inferência: billable → custo, non-billable → despesa (onde classificacao está vazia)
    if "classificacao" in df.columns and "billable_category" in df.columns:
        bc = df["billable_category"].fillna("").astype(str).str.strip().str.lower()
        cl_vazio = df["classificacao"].isna() | (df["classificacao"].astype(str).str.strip() == "")
        df.loc[cl_vazio & (bc == "billable"), "classificacao"] = "custo"
        df.loc[cl_vazio & (bc == "non-billable"), "classificacao"] = "despesa"

    # Inferência: pessoa atrelada a PEP em alguma linha → todas as linhas dela = custo
    # (sobrepõe inferência por macro_area, mas só onde classificacao ainda vazia)
    if "classificacao" in df.columns and "pep" in df.columns:
        pep_str = df["pep"].fillna("").astype(str).str.strip()
        # Pessoas que têm PEP em alguma linha
        pessoas_com_pep = set(df.loc[pep_str.ne("") & pep_str.ne("nan") & (df["_pessoa_key"] != ""), "_pessoa_key"].unique())
        pessoas_com_pep.discard("")
        if pessoas_com_pep:
            cl_vazio = df["classificacao"].isna() | (df["classificacao"].astype(str).str.strip() == "")
            mask = cl_vazio & df["_pessoa_key"].isin(pessoas_com_pep)
            df.loc[mask, "classificacao"] = "custo"

    # Inferência por macro_area (onde ainda está vazia)
    if "classificacao" in df.columns and "macro_area" in df.columns:
        ma = df["macro_area"].fillna("").astype(str).str.strip()
        cl_vazio = df["classificacao"].isna() | (df["classificacao"].astype(str).str.strip() == "")
        # Toda macro_area indica centro de custo (nao gera receita por si). custo só
        # vem via PEP atrelado ou billable=billable explicito (regras anteriores).
        despesa_areas = {"Backoffice", "Sales", "Go To Market", "Executive Leadership",
                         "Internal Systems", "Delivery"}
        custo_areas: set = set()
        df.loc[cl_vazio & ma.isin(despesa_areas), "classificacao"] = "despesa"
        df.loc[cl_vazio & ma.isin(custo_areas), "classificacao"] = "custo"

    # Sócios (pessoa em Custo Socios em alguma linha) → despesa em TODAS suas linhas vazias
    if "classificacao" in df.columns and "fonte" in df.columns:
        socios_keys = set(df.loc[df["fonte"].astype(str) == "Custo Socios", "_pessoa_key"]
                          .dropna().unique())
        socios_keys.discard("")
        if socios_keys:
            cl_vazio = df["classificacao"].isna() | (df["classificacao"].astype(str).str.strip() == "")
            df.loc[cl_vazio & df["_pessoa_key"].isin(socios_keys), "classificacao"] = "despesa"

    # Override: cadastro do Mapa Pessoas - Mar26 (mais atualizado que o Jan26 importado).
    # 16 pessoas tiveram macro_area/billable corrigidos retroativamente. Aplicado como
    # override final sobre TODAS as linhas dessas pessoas.
    for nome_alvo, macro_corr, bill_corr in CORRECOES_PESSOAS:
        mask = df["_pessoa_key"] == nome_alvo
        if not mask.any():
            continue
        if macro_corr and "macro_area" in df.columns:
            df.loc[mask, "macro_area"] = macro_corr
        if bill_corr and "billable_category" in df.columns:
            df.loc[mask, "billable_category"] = bill_corr
            if "classificacao" in df.columns:
                nova_classif = "despesa" if bill_corr == "non-billable" else "custo"
                df.loc[mask, "classificacao"] = nova_classif

    # Override: time Sales Hyper teve "BU Hyper - Sales" / "Aliancas" renomeado para
    # "Sales Hyper" no Mar26 (reorganizacao de centro de lucro).
    if "centro_lucro" in df.columns:
        mask_sh = df["_pessoa_key"].isin(CENTRO_CUSTO_SALES_HYPER)
        if mask_sh.any():
            df.loc[mask_sh, "centro_lucro"] = "Sales Hyper"

    # Override: empresa generica "FCamara Brasil" no Jan26 deve ser BR02/BR07/BR09 (Mar26).
    # COMPANY_NAMES re-mapeia para nome de display ("BR02 FCamara", etc).
    if "empresa" in df.columns:
        empresa_mapeada = df["_pessoa_key"].map(MAPPING_EMPRESA)
        emp_str = df["empresa"].fillna("").astype(str).str.strip()
        mask_generica = emp_str.isin(["FCamara Brasil", "FCAMARA BRASIL", ""]) & empresa_mapeada.notna()
        if mask_generica.any():
            df.loc[mask_generica, "empresa"] = empresa_mapeada[mask_generica].map(COMPANY_NAMES).fillna(empresa_mapeada[mask_generica])

    # Reescreve nome_pessoa para uma grafia única por pessoa unificada, pra que
    # o rateio e os agrupamentos (que usam nome_pessoa cru) tratem as variantes
    # como a mesma pessoa. Display = grafia original mais frequente da pessoa.
    if "_pessoa_key" in df.columns:
        _orig = df["nome_pessoa"].fillna("").astype(str)
        def _disp_nome(s: pd.Series) -> str:
            nz = s[s.str.strip() != ""]
            m = nz.mode()
            return m.iloc[0] if len(m) else ""
        _disp = _orig.groupby(df["_pessoa_key"]).agg(_disp_nome)
        _mapped = df["_pessoa_key"].map(_disp)
        df["nome_pessoa"] = _mapped.where(
            _mapped.fillna("").astype(str).str.strip() != "", df["nome_pessoa"]
        )

    df = df.drop(columns=["_pessoa_key"], errors="ignore")
    return df


def _aplicar_rateio_custos(df: pd.DataFrame) -> pd.DataFrame:
    """Rateia custos de CLTs/PJs proporcionalmente às horas apontadas em 'racionais' (por PEP).

    Pra cada pessoa × período:
      - soma custo em CLTs/PJs → custo_total_pessoa
      - soma horas em racionais → horas_total_pessoa
      - em cada linha de racionais da pessoa, aloca: custo_total × (horas_linha / horas_total)
      - zera o custo_rateado das linhas CLT/PJ originais (evita double-count)

    Adiciona coluna `tag_rateio` explicando cada caso.
    """
    import numpy as np
    df = df.copy()

    if "tag_rateio" not in df.columns:
        df["tag_rateio"] = ""

    if "fonte" not in df.columns:
        return df

    # Custo de CLT: nos periodos cobertos pelo Mapa Pessoas (fonte CLTs), o
    # valor oficial vem do Mapa (custo_gerencial_sap) — e a fonte custo_gerencial
    # (export SAP) zera nesses periodos. Fora deles (ex.: 2025), custo_gerencial
    # continua sendo o custo. Custo PJ vem da PROPRIA fonte PJs (valor_liquido).
    # custo_project NAO e fonte de custo — entra so como horas no rateio.
    if "custo_rateado" in df.columns:
        # PJs: custo = -valor_liquido (valor a pagar do PJ)
        mask_pjs = df["fonte"].astype(str) == "PJs"
        if mask_pjs.any() and "valor_liquido" in df.columns:
            _vl = pd.to_numeric(df["valor_liquido"], errors="coerce").fillna(0)
            df.loc[mask_pjs, "custo_rateado"] = -_vl[mask_pjs].abs()
        _clt_mask = df["fonte"].astype(str) == "CLTs"
        if "custo_gerencial_sap" in df.columns and _clt_mask.any():
            _per = df["periodo"].astype(str)
            _periodos_mapa = set(_per[_clt_mask].unique())
            _cgsap = pd.to_numeric(df["custo_gerencial_sap"], errors="coerce").fillna(0).abs()
            df.loc[_clt_mask, "custo_rateado"] = -_cgsap[_clt_mask]
            _cg_mask = df["fonte"].astype(str) == "custo_gerencial"
            df.loc[_cg_mask & _per.isin(_periodos_mapa), "custo_rateado"] = 0
        else:
            df.loc[_clt_mask, "custo_rateado"] = 0

    # Snapshot do custo NA ORIGEM, antes do rateio mover qualquer coisa.
    # custo_fonte = custo bruto na linha de origem (toda fonte exceto racionais
    # e custo_project, que são DESTINOS do rateio). O rateio mexe só em
    # custo_rateado — custo_fonte fica intacto, pra conciliar por fonte
    # (soma custo_fonte por fonte_familia = planilha de origem).
    df["custo_fonte"] = 0.0
    if "custo_rateado" in df.columns:
        _src_mask = ~df["fonte"].astype(str).isin(["racionais", "custo_project"])
        df.loc[_src_mask, "custo_fonte"] = pd.to_numeric(
            df.loc[_src_mask, "custo_rateado"], errors="coerce").fillna(0)

    # Normaliza 3 identificadores por linha: CPF (só dígitos), nome uppercase, numero_pessoal
    cpf_raw = df.get("cpf", pd.Series([""] * len(df), index=df.index)).astype(str)
    cpf_digits = cpf_raw.str.replace(r"[^\d]", "", regex=True)
    df["_cpf"] = np.where(cpf_digits.str.len() >= 11, cpf_digits, "")

    # Enriquece CPF via de-para Pessoal (nome → cpf, id → cpf)
    # Essencial pra custo_gerencial que só tem nome+id, sem CPF
    map_nome_cpf, map_id_cpf = _carregar_pessoal_depara()
    if map_nome_cpf or map_id_cpf:
        # Usa normalizacao completa (NFKD + upper + collapse spaces) pra casar
        # com a depara mesmo com acentos/typos/double-space.
        nome_raw_serie = df.get("nome_pessoa", pd.Series([""] * len(df), index=df.index))
        nome_pre = nome_raw_serie.apply(_norm_pessoa_nome)
        id_pre = df.get("numero_pessoal", pd.Series([""] * len(df), index=df.index)).astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        cpf_from_nome = nome_pre.map(map_nome_cpf).fillna("")
        cpf_from_id   = id_pre.map(map_id_cpf).fillna("")
        df["_cpf"] = np.where(df["_cpf"] == "", cpf_from_nome, df["_cpf"])
        df["_cpf"] = np.where(df["_cpf"] == "", cpf_from_id, df["_cpf"])

    # Enriquece billable_category via cruzamento por nome com fontes que têm a coluna
    # (custo_gerencial não tem billable; CLTs/PJs/racionais têm)
    if "billable_category" in df.columns:
        nome_pre2 = df.get("nome_pessoa", pd.Series([""] * len(df), index=df.index)).astype(str).str.upper().str.strip()
        tem_bc = df["billable_category"].notna() & (df["billable_category"].astype(str).str.strip() != "")
        bc_source = df[tem_bc & df["fonte"].astype(str).isin(["CLTs", "PJs", "racionais", "custo_project"])][["nome_pessoa", "billable_category"]].copy()
        bc_source["_n"] = bc_source["nome_pessoa"].astype(str).str.upper().str.strip()
        bc_map = bc_source.drop_duplicates("_n").set_index("_n")["billable_category"].to_dict()
        bc_preenchido = nome_pre2.map(bc_map)
        df["billable_category"] = df["billable_category"].where(tem_bc, bc_preenchido)
    nome_raw = df.get("nome_pessoa", pd.Series([""] * len(df), index=df.index)).astype(str).str.upper().str.strip()
    df["_nome"] = np.where(nome_raw.isin(["", "NAN", "NONE"]), "", nome_raw)
    id_raw = df.get("numero_pessoal", pd.Series([""] * len(df), index=df.index)).astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["_id"] = np.where(id_raw.isin(["", "nan", "NaN", "None"]), "", id_raw)
    df["_periodo_str"] = df["periodo"].astype(str)

    # Lookup nome→cpf (pra casar linhas sem CPF com linhas que têm CPF+nome da mesma pessoa)
    nome_has_cpf = df[(df["_cpf"] != "") & (df["_nome"] != "")]
    nome_lookup = (nome_has_cpf.groupby(["_periodo_str", "_nome"])["_cpf"].first()
                   .rename("_mapped_cpf").reset_index())
    df = df.merge(nome_lookup, on=["_periodo_str", "_nome"], how="left")
    df["_mapped_cpf"] = df["_mapped_cpf"].fillna("")

    # Cascata: CPF próprio → CPF via nome → nome → id
    df["_pk"] = np.where(
        df["_cpf"] != "", "cpf:" + df["_cpf"],
        np.where(df["_mapped_cpf"] != "", "cpf:" + df["_mapped_cpf"],
            np.where(df["_nome"] != "", "nome:" + df["_nome"],
                np.where(df["_id"] != "", "id:" + df["_id"], None)
            )
        )
    )

    # Persistente: CPF enriquecido com prefixo BRCPF (padrao master Orange)
    # — usado pelo sync da calculada e demais views.
    _cpf_d = np.where(df["_cpf"] != "", df["_cpf"], df["_mapped_cpf"])
    df["cpf"] = np.where(_cpf_d != "", "BRCPF" + _cpf_d.astype(str), "")

    # ─── Rateio proporcional ─────────────────────────────────────────────
    # Ideia: custo_real_pessoa (Custo Gerencial SAP pra CLT, valor_liquido pra PJ)
    # é distribuído proporcionalmente às horas apontadas em cada PEP via custo_project.
    #
    # custo_pep = custo_total_pessoa × (horas_pep / horas_totais_apontadas)
    #
    # custo_project.taxa_hora é bugado (valores placeholder quando cadastro falta)
    # então usamos apenas as HORAS dele, não a taxa.

    is_cp = df["fonte"].astype(str) == "custo_project"
    is_rac = df["fonte"].astype(str) == "racionais"
    is_orange = df["fonte"].astype(str) == "base Orange"
    # Orange so participa do rateio se a linha tem nome_cliente (senao migrar
    # custo CLT pra Orange sem cliente piora o "sem cliente").
    _has_cli = df.get("nome_cliente", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip().ne("")
    is_orange_cli = is_orange & _has_cli

    # 1. Custo total por pessoa × período:
    #    - CLT: vem de custo_gerencial (planilha SAP — só de CLTs)
    #    - PJ:  vem da PROPRIA fonte PJs (valor_liquido). Antes nao entrava no
    #           rateio, agora entra: PJ custo se distribui pelas horas
    #           apontadas em racional/Orange (igual CLT).
    # TDMs participam do rateio padrao se tiverem racional/Orange (com horas).
    # Quem nao tem, fica com custo na linha CLT/PJ original e e redistribuido
    # via _aplicar_rateio_tdm (% receita BU).
    is_custo_ger = df["fonte"].astype(str).isin(["custo_gerencial", "CLTs", "PJs"]) & df["_pk"].notna()
    custo_ger_pessoa = (df[is_custo_ger]
                        .groupby(["_pk", "_periodo_str"])["custo_rateado"].sum()
                        .rename("_custo_total").reset_index())

    # custo_project NAO e fonte de custo (custo PJ vem da fonte PJs).
    # Entra so como HORAS no rateio — entao _custo_cp_raw = 0.
    df["_custo_cp_raw"] = 0.0
    custo_cp_pessoa = (df[is_cp & df["_pk"].notna()]
                       .groupby(["_pk", "_periodo_str"])["_custo_cp_raw"].sum()
                       .rename("_custo_total_cp").reset_index())

    df = df.merge(custo_ger_pessoa, on=["_pk", "_periodo_str"], how="left")
    df["_custo_total"] = df["_custo_total"].fillna(0)
    df = df.merge(custo_cp_pessoa, on=["_pk", "_periodo_str"], how="left")
    df["_custo_total_cp"] = df["_custo_total_cp"].fillna(0)

    # Se nao tem custo_gerencial (CLT), cai no custo_project (PJ)
    # Pra CLTs que aparecem em custo_project com taxa fake, custo_gerencial > 0 ganha
    df["_custo_total"] = np.where(
        df["_custo_total"] == 0,
        df["_custo_total_cp"],
        df["_custo_total"],
    )

    # Marca pessoa-periodo que tem custo_gerencial (CLT)
    custo_ger_keys = custo_ger_pessoa[["_pk", "_periodo_str"]].drop_duplicates()
    custo_ger_keys["_eh_clt"] = True
    df = df.merge(custo_ger_keys, on=["_pk", "_periodo_str"], how="left")
    df["_eh_clt"] = df["_eh_clt"].fillna(False)

    # is_custo_total_primary: linha é a fonte de custo daquela pessoa-período.
    # - custo_gerencial/CLTs sempre é primary (CLT)
    # - PJs eh primary (PJ — valor_liquido eh o custo)
    # - custo_project é primary SÓ se a pessoa-período NÃO é CLT nem tem PJ
    is_custo_total_primary = df["_pk"].notna() & (
        (df["fonte"].astype(str).isin(["custo_gerencial", "CLTs", "PJs"])) |
        ((df["fonte"].astype(str) == "custo_project") & ~df["_eh_clt"])
    )

    # Fonte de horas pro rateio: racional é a fonte PRIMÁRIA (mais confiável).
    # custo_project entra só pra pessoa-período que NÃO tem racional — pega o
    # apontamento de horas dela pra distribuir o custo nos PEPs onde trabalhou.
    rac_keys = df.loc[is_rac & df["_pk"].notna(), ["_pk", "_periodo_str"]].drop_duplicates()
    rac_keys["_tem_rac"] = True
    df = df.merge(rac_keys, on=["_pk", "_periodo_str"], how="left")
    df["_tem_rac"] = df["_tem_rac"].fillna(False).astype(bool)

    # NOVA REGRA: per-PEP. Racional tem prioridade; Orange-cli complementa
    # apenas pra (pessoa, periodo, PEP) que NAO tem racional. Usa string-key
    # + set check (sem merge novo, memoria leve).
    _pep_k3 = (df["_pk"].fillna("").astype(str) + "|"
               + df["_periodo_str"].fillna("").astype(str) + "|"
               + df["pep"].fillna("").astype(str))
    _rac_pep_set = set(_pep_k3[is_rac & df["_pk"].notna()])
    is_orange_eligible = is_orange_cli & ~_pep_k3.isin(_rac_pep_set)

    # Fonte de horas: racional (primario), cp como fallback se pessoa sem racional,
    # Orange-eligible (linha com cliente, PEP sem racional naquela pessoa-periodo).
    is_horas_src = is_rac | (is_cp & ~df["_tem_rac"]) | is_orange_eligible
    # Destinos do rateio (linhas que recebem custo): racional + Orange-eligible.
    is_alloc_target = is_rac | is_orange_eligible

    # 2. Horas apontadas totais por pessoa × período (custo_project, ou racionais
    #    como fallback quando não há custo_project no mês)
    horas_totais = (df[is_horas_src & df["_pk"].notna()]
                    .groupby(["_pk", "_periodo_str"])["horas"].sum()
                    .rename("_horas_tot").reset_index())
    df = df.merge(horas_totais, on=["_pk", "_periodo_str"], how="left")
    df["_horas_tot"] = df["_horas_tot"].fillna(0)

    # 3. Horas do PEP por pessoa × período
    horas_por_pep = (df[is_horas_src & df["_pk"].notna()]
                     .groupby(["_pk", "_periodo_str", "pep"])["horas"].sum()
                     .rename("_horas_pep").reset_index())
    df = df.merge(horas_por_pep, on=["_pk", "_periodo_str", "pep"], how="left")
    df["_horas_pep"] = df["_horas_pep"].fillna(0)

    # Zera horas em linhas de custo_project que NAO sao a fonte de horas do
    # rateio (i.e., a pessoa tem racional, entao cp eh apenas backup SAP
    # ignorado). Evita "phantom horas" no breakdown da Workers tab.
    df.loc[is_cp & ~is_horas_src, "horas"] = 0

    # 3b. Horas por PEP dos destinos do rateio (racional + Orange-eligible) —
    #     denominador pra split quando ha multiplas linhas no mesmo PEP.
    horas_dest_por_pep = (df[is_alloc_target & df["_pk"].notna()]
                          .groupby(["_pk", "_periodo_str", "pep"])["horas"].sum()
                          .rename("_horas_dest_pep").reset_index())
    df = df.merge(horas_dest_por_pep, on=["_pk", "_periodo_str", "pep"], how="left")
    df["_horas_dest_pep"] = df["_horas_dest_pep"].fillna(0)

    # 4. Aloca custo nas linhas de racionais E Orange-eligible.
    # custo_pep_total = custo_total × (horas_pep / horas_tot)  -- fatia do PEP
    # custo_linha     = custo_pep_total × (linha_horas / horas_dest_no_pep)  -- split dentro do PEP
    mask_rac_aloca = is_alloc_target & (df["_horas_tot"] > 0) & (df["_custo_total"] != 0) & (df["_horas_pep"] > 0)
    horas_linha = pd.to_numeric(df["horas"], errors="coerce").fillna(0)
    share_pep         = np.where(df["_horas_tot"]      > 0, df["_horas_pep"] / df["_horas_tot"],     0.0)
    share_within_pep  = np.where(df["_horas_dest_pep"] > 0, horas_linha       / df["_horas_dest_pep"], 1.0)
    custo_alocado = np.where(
        mask_rac_aloca,
        df["_custo_total"] * share_pep * share_within_pep,
        0.0,
    )
    df.loc[mask_rac_aloca, "custo_rateado"] = custo_alocado[mask_rac_aloca]
    df.loc[mask_rac_aloca & is_rac, "tag_rateio"] = (
        "Rateio (racional): " + horas_linha[mask_rac_aloca & is_rac].round(1).astype(str) + "h"
    )
    df.loc[mask_rac_aloca & is_orange_eligible, "tag_rateio"] = (
        "Rateio (Orange): " + horas_linha[mask_rac_aloca & is_orange_eligible].round(1).astype(str) + "h"
    )
    df.loc[is_alloc_target & ~mask_rac_aloca, "tag_rateio"] = "Receita/aponta sem custo atrelado"

    # Marca pessoa-periodo cujo custo foi efetivamente rateado.
    pessoa_rateada = df[mask_rac_aloca].groupby(["_pk", "_periodo_str"]).size().reset_index()
    if len(pessoa_rateada) > 0:
        pessoa_rateada["_foi_rateado"] = True
        df = df.merge(pessoa_rateada[["_pk", "_periodo_str", "_foi_rateado"]], on=["_pk", "_periodo_str"], how="left")
    else:
        df["_foi_rateado"] = False
    df["_foi_rateado"] = df["_foi_rateado"].fillna(False)

    # Soma do custo efetivamente alocado a racionais, por pessoa-periodo.
    aloc_tot = (df[mask_rac_aloca].groupby(["_pk", "_periodo_str"])["custo_rateado"]
                .sum().rename("_aloc_tot").reset_index())
    df = df.merge(aloc_tot, on=["_pk", "_periodo_str"], how="left")
    df["_aloc_tot"] = df["_aloc_tot"].fillna(0.0)

    # 5. Linha primary (CLT/PJ): mantém o RESIDUAL = custo_total − alocado.
    # Se a pessoa foi rateada em todos os PEPs, residual ≈ 0. Se foi rateada só
    # em parte (PEPs sem racional pra receber), o restante NÃO some — fica aqui.
    _ct = pd.to_numeric(df["_custo_total"], errors="coerce").fillna(0.0)
    _resid_frac = ((_ct - df["_aloc_tot"]) / _ct).where(_ct != 0, 1.0)
    _cur_primary = pd.to_numeric(df["custo_rateado"], errors="coerce").fillna(0.0)
    _new_primary = pd.Series(
        np.where(df["_foi_rateado"], _cur_primary * _resid_frac, _cur_primary),
        index=df.index,
    )
    df.loc[is_custo_total_primary, "custo_rateado"] = _new_primary[is_custo_total_primary]
    df.loc[is_custo_total_primary & df["_foi_rateado"], "tag_rateio"] = "Custo rateado aos PEPs (residual de PEP sem racional fica aqui)"
    df.loc[is_custo_total_primary & ~df["_foi_rateado"], "tag_rateio"] = "Custo nao rateado (pessoa sem racional no periodo)"

    # 6. Zera custo nas linhas de custo_project conforme caso:
    # - Pessoa é CLT (tem custo_gerencial): custo do projeto já está em gerencial → zera
    # - Pessoa é PJ rateado (foi distribuido pra racionais): zera (custo está em racional)
    # - Pessoa é PJ sem racional matching: mantém custo na linha (residual de PJ)

    df.loc[is_cp & df["_eh_clt"], "custo_rateado"] = 0
    df.loc[is_cp & df["_eh_clt"], "tag_rateio"] = "Fonte de horas (CLT — custo está em custo_gerencial)"

    df.loc[is_cp & ~df["_eh_clt"] & df["_foi_rateado"], "custo_rateado"] = 0
    df.loc[is_cp & ~df["_eh_clt"] & df["_foi_rateado"], "tag_rateio"] = "PJ — custo distribuído via rateio"

    mask_cp_pj_residual = is_cp & ~df["_eh_clt"] & ~df["_foi_rateado"]
    df.loc[mask_cp_pj_residual, "custo_rateado"] = df.loc[mask_cp_pj_residual, "_custo_cp_raw"]
    df.loc[mask_cp_pj_residual, "tag_rateio"] = "PJ — custo na linha custo_project (sem racional matching)"

    # 7. CLT sem racional mas com horas em custo_project: o custo_gerencial
    # é alocado às linhas de custo_project (que carregam PEP e cliente),
    # proporcional às horas apontadas. Sem isso o custo ficaria órfão na
    # linha custo_gerencial (que não tem PEP nem cliente).
    mask_cp_clt_aloca = (
        is_cp & df["_eh_clt"] & ~df["_foi_rateado"] & (df["_horas_tot"] > 0)
    )
    if mask_cp_clt_aloca.any():
        horas_cp = pd.to_numeric(df["horas"], errors="coerce").fillna(0)
        share_cp = np.where(df["_horas_tot"] > 0, horas_cp / df["_horas_tot"], 0.0)
        df.loc[mask_cp_clt_aloca, "custo_rateado"] = (
            df.loc[mask_cp_clt_aloca, "_custo_total"].astype(float)
            * share_cp[mask_cp_clt_aloca]
        )
        df.loc[mask_cp_clt_aloca, "tag_rateio"] = "CLT sem racional — custo do PEP alocado via horas apontadas"
        # zera a linha custo_gerencial dessas pessoas (custo migrou pro custo_project)
        cp_keys = df.loc[mask_cp_clt_aloca, ["_pk", "_periodo_str"]].drop_duplicates()
        cp_keys["_cp_alocado"] = True
        df = df.merge(cp_keys, on=["_pk", "_periodo_str"], how="left")
        df["_cp_alocado"] = df["_cp_alocado"].fillna(False).astype(bool)
        mask_ger_zera = is_custo_total_primary & df["_cp_alocado"]
        df.loc[mask_ger_zera, "custo_rateado"] = 0
        df.loc[mask_ger_zera, "tag_rateio"] = "Custo alocado às linhas de custo_project (horas apontadas)"
        if "valor_liquido" in df.columns:
            df.loc[mask_ger_zera, "valor_liquido"] = 0
            df.loc[mask_cp_clt_aloca, "valor_liquido"] = (
                df.loc[mask_cp_clt_aloca, "receita"].fillna(0)
                + df.loc[mask_cp_clt_aloca, "custo_rateado"].fillna(0)
            )

    # Recalcula margem e valor_liquido
    df["margem"] = df["receita"].fillna(0) + df["custo_rateado"].fillna(0)
    if "valor_liquido" in df.columns:
        # racionais e fontes de custo (custo_gerencial/CLTs): valor_liquido = margem
        mask_vl_recalc = df["fonte"].astype(str).isin(
            ["racionais", "custo_gerencial", "CLTs"])
        df.loc[mask_vl_recalc, "valor_liquido"] = df.loc[mask_vl_recalc, "margem"]

    df = df.drop(columns=[
        "_pk", "_periodo_str", "_custo_total", "_custo_total_cp", "_custo_cp_raw",
        "_horas_tot", "_horas_pep", "_horas_dest_pep", "_cpf", "_nome", "_id", "_mapped_cpf",
        "_eh_clt", "_foi_rateado", "_cp_alocado", "_tem_rac", "_aloc_tot",
    ], errors="ignore")
    return df


def _aplicar_rateio_100h(df: pd.DataFrame) -> pd.DataFrame:
    """Pessoas com >100h em um cliente (via racional) num mes:
    100% do custo no(s) cliente(s) com >100h. Se >100h em multiplos clientes,
    split proporcional entre eles. Se nenhum cliente passou de 100h, mantem
    rateio padrao (esta funcao nao mexe).

    Roda APOS rateio_custos / rateio_tdm. Captura custo_rateado de todas as
    linhas da pessoa/periodo, zera, e gera linhas fonte='rateio_100h'.
    """
    import numpy as np
    if not {"nome_pessoa", "periodo", "nome_cliente", "fonte", "horas", "custo_rateado"}.issubset(df.columns):
        return df

    rac_mask = df["fonte"].astype(str) == "racionais"
    if not rac_mask.any():
        return df

    nome = df["nome_pessoa"].fillna("").astype(str).str.strip().str.upper()
    per = df["periodo"].astype(str)
    cli = df["nome_cliente"].fillna("").astype(str).str.strip()
    horas_n = pd.to_numeric(df["horas"], errors="coerce").fillna(0)

    rac_df = pd.DataFrame({
        "_nm": nome[rac_mask],
        "_per": per[rac_mask],
        "_cli": cli[rac_mask],
        "_h": horas_n[rac_mask],
    })
    rac_df = rac_df[
        rac_df["_nm"].ne("")
        & rac_df["_cli"].ne("")
        & ~rac_df["_cli"].isin(["0", "nan"])
        & (rac_df["_h"] > 0)
    ]
    if rac_df.empty:
        return df

    h_por_cli = rac_df.groupby(["_nm", "_per", "_cli"], as_index=False)["_h"].sum()
    h_alto = h_por_cli[h_por_cli["_h"] > 100]
    if h_alto.empty:
        return df

    # shares por (nome, periodo): proporcional entre clientes >100h
    shares_map = {}
    for (nm_v, per_v), grp in h_alto.groupby(["_nm", "_per"]):
        total = grp["_h"].sum()
        if total <= 0:
            continue
        shares_map[(nm_v, per_v)] = [(c, float(h) / float(total)) for c, h in zip(grp["_cli"], grp["_h"])]

    custo_n = pd.to_numeric(df["custo_rateado"], errors="coerce").fillna(0.0)
    new_rows = []
    indices_to_zero = []

    for (nm_v, per_v), shares in shares_map.items():
        mask_pp = (nome == nm_v) & (per == per_v)
        if not mask_pp.any():
            continue
        idx_pp = df.index[mask_pp]
        total_custo = float(custo_n.loc[idx_pp].sum())
        if total_custo == 0:
            continue
        ref_row = df.loc[idx_pp[0]]
        for cli_v, share in shares:
            share_cost = total_custo * share
            new_rows.append({
                "fonte": "rateio_100h",
                "fonte_dados": "Rateio >100h",
                "periodo": per_v,
                "nome_pessoa": ref_row.get("nome_pessoa"),
                "cpf": ref_row.get("cpf"),
                "nome_cliente": cli_v,
                "vertical": ref_row.get("vertical"),
                "empresa": ref_row.get("empresa"),
                "macro_area": ref_row.get("macro_area"),
                "classificacao": "custo",
                "tipo_contrato": ref_row.get("tipo_contrato"),
                "custo_rateado": share_cost,
                "receita": 0.0,
                "horas": 0.0,
                "valor_liquido": share_cost,
                "margem": share_cost,
                "custo_fonte": 0.0,
                "tag_rateio": f"Rateio >100h: {share*100:.1f}% ({cli_v})",
            })
        indices_to_zero.extend(idx_pp.tolist())

    if not new_rows:
        return df

    df.loc[indices_to_zero, "custo_rateado"] = 0.0
    if "margem" in df.columns:
        rec_n = pd.to_numeric(df.loc[indices_to_zero, "receita"], errors="coerce").fillna(0.0)
        df.loc[indices_to_zero, "margem"] = rec_n.values

    new_df = pd.DataFrame(new_rows)
    for c in df.columns:
        if c not in new_df.columns:
            new_df[c] = None
    new_df = new_df[df.columns]
    return pd.concat([df, new_df], ignore_index=True)


def _aplicar_rateio_tdm(df: pd.DataFrame) -> pd.DataFrame:
    """TDMs (macro_area='TDM'): rateia custo pelos clientes da BU por % receita
    racionais (mesmo mes). Cria linhas fonte='rateio_tdm' por cliente e zera
    custo_rateado nas linhas TDM originais.
    """
    import numpy as np
    if not {"macro_area", "vertical", "custo_rateado", "fonte", "periodo"}.issubset(df.columns):
        return df

    tdm_mask = (
        df["macro_area"].fillna("").astype(str).str.strip().str.upper() == "TDM"
    ) & df["fonte"].astype(str).isin(["CLTs", "PJs"])
    if not tdm_mask.any():
        return df

    custo_col = pd.to_numeric(df["custo_rateado"], errors="coerce").fillna(0.0)
    tdm_idx = df.index[tdm_mask & (custo_col.abs() > 0)]
    if len(tdm_idx) == 0:
        return df

    # Receita racionais por (BU, periodo, cliente)
    rec_col = pd.to_numeric(df["receita"], errors="coerce").fillna(0.0)
    cli_col = df["nome_cliente"].fillna("").astype(str).str.strip()
    rac_mask = (
        (df["fonte"].astype(str) == "racionais")
        & (rec_col > 0)
        & cli_col.ne("")
        & ~cli_col.isin(["0", "nan"])
    )
    if not rac_mask.any():
        return df
    rac_df = pd.DataFrame({
        "vertical": df.loc[rac_mask, "vertical"].fillna("").astype(str),
        "periodo": df.loc[rac_mask, "periodo"].astype(str),
        "nome_cliente": cli_col[rac_mask],
        "_rec": rec_col[rac_mask],
    })
    rec_bu_cli = rac_df.groupby(["vertical", "periodo", "nome_cliente"], as_index=False)["_rec"].sum()
    rec_bu = rec_bu_cli.groupby(["vertical", "periodo"], as_index=False)["_rec"].sum().rename(columns={"_rec": "_rec_bu"})
    rec_bu_cli = rec_bu_cli.merge(rec_bu, on=["vertical", "periodo"])
    rec_bu_cli["_share"] = rec_bu_cli["_rec"] / rec_bu_cli["_rec_bu"]

    # Pra cada (BU, periodo) que tem TDM custo, lookup das fatias.
    rec_lookup = {}
    for (bu, per), grp in rec_bu_cli.groupby(["vertical", "periodo"]):
        rec_lookup[(bu, per)] = list(zip(grp["nome_cliente"], grp["_share"]))

    new_rows = []
    distrib_idx = []
    for i in tdm_idx:
        row = df.loc[i]
        bu = str(row.get("vertical") or "")
        per = str(row.get("periodo") or "")
        fatias = rec_lookup.get((bu, per))
        if not fatias:
            continue  # BU/periodo sem receita: deixa custo na linha original
        custo_abs = float(abs(custo_col.loc[i]))
        for cli, share in fatias:
            share_cost = -custo_abs * float(share)
            new_rows.append({
                "fonte": "rateio_tdm",
                "fonte_dados": "Rateio TDM",
                "periodo": per,
                "nome_pessoa": row.get("nome_pessoa"),
                "cpf": row.get("cpf"),
                "nome_cliente": cli,
                "vertical": bu,
                "empresa": row.get("empresa"),
                "macro_area": "TDM",
                "classificacao": "custo",
                "tipo_contrato": row.get("tipo_contrato"),
                "custo_rateado": share_cost,
                "receita": 0.0,
                "horas": 0.0,
                "valor_liquido": share_cost,
                "margem": share_cost,
                "custo_fonte": 0.0,
                "tag_rateio": f"Rateio TDM (% receita BU): {share*100:.1f}%",
            })
        distrib_idx.append(i)

    if not distrib_idx:
        return df

    # Zera custo nas linhas TDM cujo custo foi distribuido
    df.loc[distrib_idx, "custo_rateado"] = 0.0
    df.loc[distrib_idx, "margem"] = 0.0
    df.loc[distrib_idx, "tag_rateio"] = "TDM — custo distribuido pelos clientes da BU"
    if "valor_liquido" in df.columns:
        df.loc[distrib_idx, "valor_liquido"] = 0.0

    new_df = pd.DataFrame(new_rows)
    for c in df.columns:
        if c not in new_df.columns:
            new_df[c] = None
    new_df = new_df[df.columns]
    return pd.concat([df, new_df], ignore_index=True)


def _get_nova_base() -> pd.DataFrame:
    if _cache["nova_base"] is not None:
        return _cache["nova_base"]
    with _nova_base_lock:
        if _cache["nova_base"] is not None:
            return _cache["nova_base"]

        # Tenta Supabase primeiro; fallback para CSV local
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                df = _load_nova_base_supabase()
                NUM_COLS = ["receita", "custo_rateado", "horas", "margem", "valor_liquido", "valor",
                            "taxa_hora", "hour_price", "gross_revenue",
                            "custo_gerencial_sap", "custo_h_hora_extra", "custo_h_sobreaviso"]
                for col in NUM_COLS:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                # Força recálculo do custo_rateado a partir de custo_gerencial_sap
                # (corrige bug historico onde Custo/H Padrão Hora extra — uma TAXA —
                # estava sendo somada como valor, inflando custo em R$100-300/pessoa).
                if "custo_gerencial_sap" in df.columns:
                    import numpy as np
                    custo_ger = df["custo_gerencial_sap"].fillna(0)
                    mask_ger = (custo_ger != 0)
                    df.loc[mask_ger, "custo_rateado"] = -custo_ger[mask_ger]
                # Mapa de Pessoas (fonte=CLTs) NAO deve carregar custo — custo de CLT
                # vem de fonte=custo_gerencial (SAP). PJs mantem custo (eh a fonte do PJ).
                if "fonte" in df.columns:
                    mask_clt_mapa = df["fonte"].astype(str) == "CLTs"
                    for col in ("custo_rateado", "valor_liquido", "margem"):
                        if col in df.columns:
                            df.loc[mask_clt_mapa, col] = 0
                if "empresa" in df.columns:
                    df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
                if "vertical" in df.columns:
                    df["vertical"] = df["vertical"].replace({"BU Health - Sales": "BU Health"})
                    # Linhas da Hyper sem vertical → Hyper (estrutura/overhead da empresa)
                    if "empresa" in df.columns:
                        mask_hy_sem_bu = (df["empresa"] == "BR07 Hyper") & (df["vertical"].isna() | (df["vertical"].astype(str).str.strip().isin(["", "nan", "None"])))
                        df.loc[mask_hy_sem_bu, "vertical"] = "Hyper"
                df = _adicionar_fonte_familia(df)
                df = _adicionar_apuracao(df)
                df = _enriquecer_dados_pessoa(df)
                df = _aplicar_rateio_custos(df)
                df = _aplicar_vertical_por_pep(df)
                df = _reclassificar_hyper(df)
                df = _aplicar_rateio_100h(df)
                df = _aplicar_rateio_tdm(df)
                _cache["nova_base"] = df
                return _cache["nova_base"]
            except Exception as e:
                print(f"[nova_base] Supabase error, falling back to CSV: {e}")

        xlsx_path = os.path.join(_BASE_DIR, "base_2026.xlsx")
        if not os.path.exists(xlsx_path):
            xlsx_path = os.path.join(_BASE_DIR, "..", "base_2026.xlsx")
        csv_path = os.path.join(_BASE_DIR, "base_2026.csv")
        if not os.path.exists(csv_path):
            csv_path = os.path.join(_BASE_DIR, "..", "base_2026.csv")

        # Lê apenas as colunas usadas pelos endpoints — reduz uso de memória
        NEEDED_COLS = [
            "fonte", "fonte_dados", "periodo", "empresa", "pep", "pep_base",
            "nome_pessoa", "nome_cliente", "tipos", "categoria_bu", "no_hierarquia",
            "vertical", "stream", "agrupador", "area", "macro_area",
            "tipo_contrato", "classificacao", "billable_category",
            "receita", "custo_rateado", "horas", "margem", "valor_liquido", "valor",
            "taxa_hora", "hour_price", "gross_revenue",
            "custo_gerencial_sap", "custo_h_hora_extra", "custo_h_sobreaviso",
        ]
        if os.path.exists(csv_path):
            print(f"[nova_base] loading csv: {csv_path}")
            avail_cols = pd.read_csv(csv_path, nrows=0).columns.tolist()
            use_cols = [c for c in NEEDED_COLS if c in avail_cols]
            df = pd.read_csv(csv_path, usecols=use_cols, dtype=str, low_memory=False)
        elif os.path.exists(xlsx_path):
            print(f"[nova_base] csv não encontrado, lendo xlsx: {xlsx_path}")
            df = pd.read_excel(xlsx_path, sheet_name="base", dtype=str)
        else:
            raise FileNotFoundError(f"base_2026.csv / .xlsx não encontrado em {_BASE_DIR}")

        NUM_COLS = ["receita", "custo_rateado", "horas", "margem", "valor_liquido", "valor",
                    "taxa_hora", "hour_price", "gross_revenue",
                    "custo_gerencial_sap", "custo_h_hora_extra", "custo_h_sobreaviso"]
        for col in NUM_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Mapeia custo para custo_rateado (negativo) onde ainda está zerado.
        # CLTs/custo_gerencial: usa só `custo_gerencial_sap` (valor total do SAP,
        # ja inclui extras/bonus/encargos). NÃO somar Custo/H Padrão Hora extra
        # nem Sobreaviso: esses são TAXAS por hora, não valores.
        # PJs: valor_liquido (positivo = custo).
        import numpy as np
        mask_clt = pd.Series(False, index=df.index)
        mask_pj  = pd.Series(False, index=df.index)
        if "custo_gerencial_sap" in df.columns:
            custo_ger = df["custo_gerencial_sap"].fillna(0)
            # Força override sempre que houver custo_gerencial_sap — corrige o bug historico
            # onde Custo/H Padrão Hora extra (taxa) estava sendo somado como valor.
            mask_clt  = (custo_ger != 0)
            df["custo_rateado"] = np.where(mask_clt, -custo_ger, df["custo_rateado"])
        # PJs: valor_liquido positivo = custo
        if "valor_liquido" in df.columns and "fonte" in df.columns:
            vl = df["valor_liquido"].fillna(0)
            mask_pj = (df["custo_rateado"] == 0) & (df["fonte"].astype(str) == "PJs") & (vl > 0)
            df["custo_rateado"] = np.where(mask_pj, -vl, df["custo_rateado"])

        # Corrige valor_liquido para refletir P&L corretamente:
        # 1. CLTs/PJs: Totalizador/valor_a_pagar estava no valor_liquido como custo positivo (errado)
        #    → sobrescreve com receita + custo_rateado (negativo)
        # 2. Demais linhas sem valor_liquido (custo_gerencial, racionais): preenche com receita + custo_rateado
        if "valor_liquido" in df.columns:
            rec = df["receita"].fillna(0)
            cr  = df["custo_rateado"].fillna(0)
            # Linhas cujo valor_liquido foi contaminado com custo bruto positivo (CLT/PJ)
            df["valor_liquido"] = np.where(
                mask_clt | mask_pj,
                rec + cr,
                df["valor_liquido"]
            )
            # Linhas onde valor_liquido = 0 mas há receita ou custo (custo_gerencial, racionais, etc.)
            vl_zero = df["valor_liquido"] == 0
            has_val = (rec != 0) | (cr != 0)
            df["valor_liquido"] = np.where(
                vl_zero & has_val,
                rec + cr,
                df["valor_liquido"]
            )

        if "empresa" in df.columns:
            df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])
        if "vertical" in df.columns:
            df["vertical"] = df["vertical"].replace({"BU Health - Sales": "BU Health"})
            if "empresa" in df.columns:
                mask_hy_sem_bu = (df["empresa"] == "BR07 Hyper") & (df["vertical"].isna() | (df["vertical"].astype(str).str.strip().isin(["", "nan", "None"])))
                df.loc[mask_hy_sem_bu, "vertical"] = "Hyper"
        # Mapa de Pessoas (fonte=CLTs) NAO deve carregar custo — custo de CLT
        # vem de fonte=custo_gerencial (SAP). PJs mantem custo (eh a fonte do PJ).
        if "fonte" in df.columns:
            mask_clt_mapa = df["fonte"].astype(str) == "CLTs"
            for col in ("custo_rateado", "valor_liquido", "margem"):
                if col in df.columns:
                    df.loc[mask_clt_mapa, col] = 0
        df = _adicionar_fonte_familia(df)
        df = _adicionar_apuracao(df)
        df = _enriquecer_dados_pessoa(df)
        df = _aplicar_rateio_custos(df)
        df = _aplicar_vertical_por_pep(df)
        df = _reclassificar_hyper(df)
        df = _aplicar_rateio_100h(df)
        df = _aplicar_rateio_tdm(df)
        _cache["nova_base"] = df
    return _cache["nova_base"]

@app.post("/api/nova-base/upload")
async def upload_nova_base(user=Depends(get_current_user)):
    """Upload CSV/Excel to replace nova_base data in Supabase."""
    from fastapi import UploadFile, File
    # Re-declare to get file from request
    pass

# Actual upload with File dependency
from fastapi import UploadFile, File as FastFile

_MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024  # default 50MB

# Magic bytes pra validacao real de tipo de arquivo (nao confiar so na extensao)
_FILE_SIGNATURES = {
    "xlsx": b"PK\x03\x04",         # zip-based (xlsx, docx, etc)
    "xls":  b"\xd0\xcf\x11\xe0",   # MS OLE Compound File
}

def _detect_file_type(content: bytes, filename: str) -> str:
    """Retorna 'csv', 'xlsx', 'xls' ou levanta HTTPException."""
    fname = (filename or "").lower()
    head = content[:8]
    if head.startswith(_FILE_SIGNATURES["xlsx"]):
        if not fname.endswith(".xlsx"):
            raise HTTPException(400, "Arquivo é xlsx mas extensão não bate")
        return "xlsx"
    if head.startswith(_FILE_SIGNATURES["xls"]):
        if not fname.endswith(".xls"):
            raise HTTPException(400, "Arquivo é xls mas extensão não bate")
        return "xls"
    # CSV: assume texto. Tenta decodificar pra detectar se é texto válido.
    if fname.endswith(".csv"):
        try:
            content[:1024].decode("utf-8")
        except UnicodeDecodeError:
            try:
                content[:1024].decode("latin-1")
            except UnicodeDecodeError:
                raise HTTPException(400, "Arquivo .csv com encoding inválido")
        return "csv"
    raise HTTPException(400, f"Formato não suportado. Use .csv ou .xlsx")


@app.post("/api/nova-base/upload-file")
async def upload_nova_base_file(
    file: UploadFile = FastFile(...),
    user=Depends(get_current_user)
):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(400, "Supabase not configured")
    import uuid, io, math
    import numpy as np
    content = await file.read()
    if len(content) > _MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"Arquivo muito grande. Limite: {_MAX_UPLOAD_SIZE // 1024 // 1024}MB")
    if len(content) == 0:
        raise HTTPException(400, "Arquivo vazio")
    fname = file.filename or ""
    file_type = _detect_file_type(content, fname)
    if file_type == "csv":
        df = pd.read_csv(io.BytesIO(content), dtype=str, low_memory=False)
    else:
        df = pd.read_excel(io.BytesIO(content), dtype=str)

    # Validate required columns
    required = {"periodo", "empresa", "receita"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"Colunas obrigatórias ausentes: {missing}")

    # Apply same transformations as seed
    NUM_COLS = ["receita", "custo_rateado", "horas", "margem", "valor_liquido", "valor",
                "taxa_hora", "hour_price", "gross_revenue",
                "custo_gerencial_sap", "custo_h_hora_extra", "custo_h_sobreaviso"]
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0

    mask_clt = pd.Series(False, index=df.index)
    mask_pj  = pd.Series(False, index=df.index)
    if "custo_gerencial_sap" in df.columns:
        custo_ger = df["custo_gerencial_sap"].fillna(0)
        custo_ext = df.get("custo_h_hora_extra", pd.Series(0, index=df.index)).fillna(0)
        custo_sob = df.get("custo_h_sobreaviso", pd.Series(0, index=df.index)).fillna(0)
        mask_clt = (df["custo_rateado"] == 0) & (custo_ger != 0)
        df["custo_rateado"] = np.where(mask_clt, -(custo_ger + custo_ext + custo_sob), df["custo_rateado"])
    if "valor_liquido" in df.columns and "fonte" in df.columns:
        vl = df["valor_liquido"].fillna(0)
        mask_pj = (df["custo_rateado"] == 0) & (df["fonte"].astype(str) == "PJs") & (vl > 0)
        df["custo_rateado"] = np.where(mask_pj, -vl, df["custo_rateado"])
    if "valor_liquido" in df.columns:
        rec = df["receita"].fillna(0)
        cr  = df["custo_rateado"].fillna(0)
        df["valor_liquido"] = np.where(mask_clt | mask_pj, rec + cr, df["valor_liquido"])
        vl_zero = df["valor_liquido"] == 0
        has_val = (rec != 0) | (cr != 0)
        df["valor_liquido"] = np.where(vl_zero & has_val, rec + cr, df["valor_liquido"])
    df["margem"] = df["receita"] + df["custo_rateado"]
    if "empresa" in df.columns:
        df["empresa"] = df["empresa"].map(COMPANY_NAMES).fillna(df["empresa"])

    # Clean for JSON
    NEEDED_COLS = [c for c in df.columns if c in [
        "fonte", "fonte_dados", "periodo", "empresa", "pep", "pep_base",
        "nome_pessoa", "nome_cliente", "tipos", "categoria_bu", "no_hierarquia",
        "vertical", "stream", "agrupador", "area", "macro_area",
        "tipo_contrato", "classificacao", "billable_category",
    ] + NUM_COLS]
    df = df[[c for c in NEEDED_COLS if c in df.columns]]
    df = df.where(pd.notnull(df), None)
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = df[c].apply(lambda v: None if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else round(float(v), 2))
    for c in df.columns:
        if c not in NUM_COLS:
            df[c] = df[c].apply(lambda v: str(v).strip() if v is not None else None)

    upload_id = str(uuid.uuid4())
    headers = {**_supabase_headers(), "Prefer": "return=minimal"}
    url = f"{SUPABASE_URL}/rest/v1/nova_base"
    client = httpx.Client(timeout=30)

    # Delete all existing rows
    r = client.delete(f"{url}?id=gt.0", headers=headers)
    if r.status_code not in (200, 204):
        client.close()
        raise HTTPException(500, f"Erro ao limpar dados: {r.text[:200]}")

    # Insert in batches
    batch_size = 500
    rows = df.to_dict(orient="records")
    for row in rows:
        row["upload_id"] = upload_id
        row["uploaded_by"] = user.get("sub", "unknown") if isinstance(user, dict) else "unknown"
    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        r = client.post(url, headers=headers, json=batch)
        if r.status_code not in (200, 201):
            client.close()
            raise HTTPException(500, f"Erro batch {i//batch_size}: {r.text[:200]}")
        inserted += len(batch)
    client.close()

    # Invalidate cache
    _cache["nova_base"] = None

    return {"status": "ok", "rows_inserted": inserted, "upload_id": upload_id, "filename": fname}


def _sync_nova_base_calculada() -> dict:
    """Recalcula a nova_base (com rateio aplicado) e grava na tabela
    `nova_base_calculada` no Supabase — com custo/despesa ja separados.
    Essa tabela e o que o Excel consome (numeros batem 100% com o site).
    """
    import numpy as np
    df = _get_nova_base().copy()

    for col in ["receita", "custo_rateado", "horas", "valor_liquido"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # NAO zera mais a fonte CLTs: agora ela carrega o custo de CLT (residual
    # do rateio). custo_rateado ja vem rateado de _get_nova_base.

    # Split custo / despesa (mesma regra do Resumo)
    has_ma = df["macro_area"].fillna("").astype(str).str.strip().ne("") if "macro_area" in df.columns else pd.Series(False, index=df.index)
    fonte_s = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    is_socio = fonte_s.isin(["Custo Socios", "Custo Sócios"])
    classif = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    expl_desp = classif == "despesa"
    expl_cus = classif == "custo"
    is_despesa = expl_desp | ((~expl_cus) & (has_ma | is_socio))

    df["_custo"] = np.where(~is_despesa, df["custo_rateado"], 0.0)
    df["_despesa"] = np.where(is_despesa, df["custo_rateado"], 0.0)

    from datetime import datetime as _dt, timezone as _tz
    agora = _dt.now(_tz.utc).isoformat()

    def _s(col):
        if col in df.columns:
            return df[col].fillna("").astype(str).str.strip()
        return pd.Series([""] * len(df), index=df.index)

    def _n(col):
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0).round(2)
        return pd.Series([0.0] * len(df), index=df.index)

    out = pd.DataFrame({
        "periodo": _s("periodo"), "empresa": _s("empresa"), "vertical": _s("vertical"),
        "apuracao": _s("apuracao"), "no_hierarquia": _s("no_hierarquia"),
        "macro_area": _s("macro_area"), "area": _s("area"),
        "fonte": _s("fonte"), "fonte_familia": _s("fonte_familia"), "fonte_dados": _s("fonte_dados"),
        "nome_pessoa": _s("nome_pessoa"), "nome_cliente": _s("nome_cliente"),
        "cpf": _s("cpf"),
        "pep": _s("pep"), "pep_base": _s("pep_base"),
        "tipo_contrato": _s("tipo_contrato"), "classificacao": _s("classificacao"),
        "billable_category": _s("billable_category"), "tipos": _s("tipos"), "agrupador": _s("agrupador"),
        "receita": _n("receita"), "custo": df["_custo"].round(2), "despesa": df["_despesa"].round(2),
        "horas": _n("horas"), "valor_liquido": _n("valor_liquido"),
    })
    # Margem Bruta = Receita + Custo (custo direto apenas; despesa NAO entra)
    out["margem"] = (out["receita"] + out["custo"]).round(2)
    out["atualizado_em"] = agora

    records = out.where(pd.notnull(out), None).to_dict(orient="records")

    headers = {
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=minimal",
    }
    base_url = f"{SUPABASE_URL}/rest/v1/nova_base_calculada"
    with httpx.Client(timeout=120) as client:
        # Limpa a tabela
        client.delete(f"{base_url}?id=gt.0", headers=headers)
        # Insere em batches
        BATCH = 500
        inserted = 0
        for i in range(0, len(records), BATCH):
            chunk = records[i:i + BATCH]
            r = client.post(base_url, headers=headers, json=chunk)
            if r.status_code not in (200, 201, 204):
                raise HTTPException(500, f"Erro sync calculada batch {i}: {r.text[:200]}")
            inserted += len(chunk)
    return {"rows": inserted}


@app.post("/api/nova-base/clear-cache")
def clear_nova_base_cache(user=Depends(get_current_user)):
    _cache["nova_base"] = None
    # Recalcula e regrava a tabela nova_base_calculada (consumida pelo Excel)
    try:
        sync = _sync_nova_base_calculada()
        return {"status": "ok", "message": "Cache limpo e nova_base_calculada atualizada.",
                "calculada_rows": sync["rows"]}
    except Exception as e:
        print(f"[clear-cache] sync calculada falhou: {e}")
        return {"status": "ok", "message": "Cache limpo. Sync da tabela calculada falhou.",
                "sync_error": str(e)}

@app.post("/api/nova-base/sync-calculada")
def sync_calculada_endpoint(user=Depends(get_current_user)):
    """Forca regravar a tabela nova_base_calculada (consumida pelo Excel)."""
    sync = _sync_nova_base_calculada()
    return {"status": "ok", "calculada_rows": sync["rows"]}

@app.get("/api/nova-base/filters")
def get_nova_base_filters(user=Depends(get_current_user)):
    from datetime import datetime
    current_period = datetime.now().strftime("%Y-%m")
    df = _get_nova_base()
    df = df[df["periodo"].fillna("").astype(str) <= current_period]
    # Se usuário restrito por BU, filtra o df antes de derivar as opções de filtro
    allowed_bus = get_user_bus(user)
    if allowed_bus and "vertical" in df.columns:
        df = df[df["vertical"].astype(str).str.strip().isin(allowed_bus)]
    # Exclui períodos sem nenhum dado real
    for col in ["receita", "custo_rateado", "valor_liquido", "horas"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    period_totals = df.groupby("periodo")[["receita","custo_rateado","horas"]].sum().abs().sum(axis=1)
    periodos_com_dados = set(period_totals[period_totals > 0].index)
    df = df[df["periodo"].isin(periodos_com_dados)]
    def uniq(col):
        return sorted(df[col].dropna().astype(str).str.strip().unique().tolist()) if col in df.columns else []
    return {
        "periodos":        uniq("periodo"),
        "fontes":          uniq("fonte_familia"),
        "empresas":        uniq("empresa"),
        "macro_areas":     uniq("macro_area"),
        "areas":           uniq("area"),
        "tipos_contrato":  uniq("tipo_contrato"),
        "classificacoes":  uniq("classificacao"),
        "verticais":       uniq("vertical"),
        "apuracoes":       uniq("apuracao"),
        "no_hierarquias":  uniq("no_hierarquia"),
        "clientes":        uniq("nome_cliente"),
    }

@app.get("/api/nova-base/resumo")
def get_nova_base_resumo(
    periodos: str = "",
    empresas: str = "",
    fontes: str = "",
    macro_areas: str = "",
    tipos_contrato: str = "",
    classificacoes: str = "",
    verticais: str = "",
    no_hierarquias: str = "",
    apuracoes: str = "",
    agrupar_por: str = "empresa",
    user=Depends(get_current_user)
):
    from datetime import datetime
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()

    if not periodos:
        current_period = datetime.now().strftime("%Y-%m")
        df = df[df["periodo"].fillna("").astype(str) <= current_period].copy()

    def filt(col, param):
        """Filtra por valores. Sentinel '__blank__' pega linhas vazias/NaN."""
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if vals and col in df.columns:
            col_clean = df[col].fillna("").astype(str).str.strip()
            regular_vals = [v for v in vals if v != "__blank__"]
            mask = pd.Series(False, index=df.index)
            if regular_vals:
                mask = mask | col_clean.isin(regular_vals)
            if "__blank__" in vals:
                mask = mask | (col_clean == "")
            return df[mask].copy()
        return df

    if periodos:       df = filt("periodo", periodos)
    if empresas:       df = filt("empresa", empresas)
    if fontes:         df = filt("fonte_familia", fontes)
    if macro_areas:    df = filt("macro_area", macro_areas)
    if tipos_contrato: df = filt("tipo_contrato", tipos_contrato)
    if classificacoes: df = filt("classificacao", classificacoes)
    if verticais:      df = filt("vertical", verticais)
    if no_hierarquias: df = filt("no_hierarquia", no_hierarquias)
    if apuracoes:      df = filt("apuracao", apuracoes)

    df = df.copy()

    # Coluna virtual "tipo_pessoa" (CLT/PJ/Outros) baseada no Mapa Pessoas Jan/26
    if agrupar_por == "tipo_pessoa":
        # Normalizacao forte: upper, strip, colapsa whitespace, remove acentos
        import unicodedata
        def _norm_nome(s: pd.Series) -> pd.Series:
            s = s.fillna("").astype(str).str.upper().str.strip()
            s = s.str.replace(r"\s+", " ", regex=True)
            s = s.apply(lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("ascii") if x else x)
            return s

        nome_norm = _norm_nome(df["nome_pessoa"])
        clt_nomes = set(_norm_nome(df.loc[df["fonte"].astype(str) == "CLTs", "nome_pessoa"]).unique())
        pj_nomes  = set(_norm_nome(df.loc[df["fonte"].astype(str) == "PJs",  "nome_pessoa"]).unique())
        cg_nomes  = set(_norm_nome(df.loc[df["fonte"].astype(str) == "custo_gerencial", "nome_pessoa"]).unique())
        cp_nomes  = set(_norm_nome(df.loc[df["fonte"].astype(str) == "custo_project", "nome_pessoa"]).unique())
        clt_nomes.discard(""); pj_nomes.discard(""); cg_nomes.discard(""); cp_nomes.discard("")

        df["tipo_pessoa"] = ""
        df.loc[nome_norm.isin(clt_nomes), "tipo_pessoa"] = "CLT"
        df.loc[nome_norm.isin(pj_nomes), "tipo_pessoa"] = "PJ"
        mask_inferir_clt = (df["tipo_pessoa"] == "") & nome_norm.isin(cg_nomes)
        df.loc[mask_inferir_clt, "tipo_pessoa"] = "CLT"
        mask_inferir_pj = (df["tipo_pessoa"] == "") & nome_norm.isin(cp_nomes)
        df.loc[mask_inferir_pj, "tipo_pessoa"] = "PJ"
        df.loc[df["tipo_pessoa"] == "", "tipo_pessoa"] = "Outros"

    group_col = agrupar_por if agrupar_por in df.columns else "empresa"
    for col in ["receita", "custo_rateado", "horas", "valor_liquido", "custo_fonte"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df[group_col] = df[group_col].fillna("").astype(str).str.strip()
    df["periodo"]  = df["periodo"].fillna("").astype(str).str.strip()
    if group_col == "macro_area":
        df.loc[df[group_col] == "", group_col] = "Projetos"
    if group_col == "apuracao":
        df.loc[df[group_col] == "", group_col] = "Sem Apuração"
    if group_col == "vertical":
        _NOT_BU = {"Executive Leadership", "Operations VP", "Sales VP", "Tech VP", "Delivery Play"}
        df = df[~df[group_col].isin(_NOT_BU)]
    df = df[df[group_col].ne("") & df["periodo"].str.match(r"^\d{4}-\d{2}$")].copy()

    # Separa custo (billable, sem macro_area) de despesa (com macro_area). A coluna
    # `custo_rateado` no resumo agrega so o custo direto — despesas (SGA, Backoffice,
    # etc.) nao entram aqui pra nao inflar custo de projeto.
    # Classificacao final: respeita coluna `classificacao` quando preenchida,
    # senao usa inferencia por macro_area + fonte (Custo Socios -> despesa).
    has_ma = df["macro_area"].fillna("").astype(str).str.strip().ne("") if "macro_area" in df.columns else pd.Series(False, index=df.index)
    fonte_str = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    is_socio = fonte_str.isin(["Custo Socios", "Custo Sócios"])
    classif_str = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    explicit_desp = classif_str == "despesa"
    explicit_cus  = classif_str == "custo"
    # Despesa = explicito OU (sem classif explicita E (com macro_area OU socio))
    is_despesa = explicit_desp | ((~explicit_cus) & (has_ma | is_socio))
    df["_custo_direto"] = df["custo_rateado"].where(~is_despesa, 0)
    df["_horas_direto"] = df["horas"].where(~is_despesa, 0)
    df["_despesa"]      = df["custo_rateado"].where(is_despesa, 0)

    agg = df.groupby([group_col, "periodo"], as_index=False).agg(
        receita       = ("receita",       "sum"),
        custo_rateado = ("_custo_direto", "sum"),
        despesa       = ("_despesa",      "sum"),
        horas         = ("_horas_direto", "sum"),
        valor_liquido = ("valor_liquido", "sum"),
        custo_fonte   = ("custo_fonte",   "sum"),
    )
    agg = agg.rename(columns={group_col: "grupo"})

    # Remove grupos sem nenhum dado real (ex: empresas que só têm Custo Socios,
    # como Distrito, Mult, Avanti — receita=0, custo=0, horas=0 em todos os periodos)
    grupo_totals = agg.groupby("grupo")[["receita","custo_rateado","horas"]].sum().abs().sum(axis=1)
    grupos_com_dados = grupo_totals[grupo_totals > 0].index
    agg = agg[agg["grupo"].isin(grupos_com_dados)]

    # Remove períodos sem nenhum dado real (todos os valores zerados)
    if not periodos:
        periodo_totals = agg.groupby("periodo")[["receita","custo_rateado","horas"]].sum().abs().sum(axis=1)
        periodos_com_dados = periodo_totals[periodo_totals > 0].index
        agg = agg[agg["periodo"].isin(periodos_com_dados)]

    return _sanitize(agg.to_dict(orient="records"))

@app.get("/api/budget-vs-realizado")
def get_budget_vs_realizado(
    verticais: str = "", clientes: str = "",
    user=Depends(get_current_user)
):
    """Budget 2026 (fonte=Budget) vs Realizado 2026 (nova_base sem Budget).
    Retorna agregado por (periodo, vertical, nome_cliente).
    Custo armazenado como negativo; LB / Receita positivos.
    """
    import numpy as np
    verticais = enforce_bu_filter(user, verticais)

    # === Budget ===
    bud = _load_budget_supabase()
    if bud.empty:
        bud = pd.DataFrame(columns=["periodo", "vertical", "nome_cliente", "receita", "custo_rateado", "valor_liquido"])
    bud = bud.rename(columns={"custo_rateado": "custo", "valor_liquido": "lb"})
    for c in ("receita", "custo", "lb"):
        bud[c] = pd.to_numeric(bud[c], errors="coerce").fillna(0)
    bud["nome_cliente"] = bud["nome_cliente"].fillna("").astype(str).str.strip()
    bud["vertical"] = bud["vertical"].fillna("").astype(str).str.strip()

    # === Realizado ===
    df = _get_nova_base().copy()
    df = df[df["periodo"].fillna("").astype(str).str.startswith("2026-")]
    for c in ("receita", "custo_rateado", "valor_liquido"):
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Separa custo (somente custo direto, exclui despesa)
    has_ma = df.get("macro_area", pd.Series("", index=df.index)).fillna("").astype(str).str.strip().ne("")
    classif = df.get("classificacao", pd.Series("", index=df.index)).fillna("").astype(str).str.strip().str.lower()
    expl_desp = classif == "despesa"
    expl_cus = classif == "custo"
    is_despesa = expl_desp | ((~expl_cus) & has_ma)
    df["_custo"] = np.where(~is_despesa, df["custo_rateado"], 0.0)
    # LB realizado = receita + custo (custo negativo)
    df["_lb"] = df["receita"] + df["_custo"]

    real = df.groupby(["periodo", "vertical", "nome_cliente"], dropna=False).agg(
        real_receita=("receita", "sum"),
        real_custo=("_custo", "sum"),
        real_lb=("_lb", "sum"),
    ).reset_index()
    real["nome_cliente"] = real["nome_cliente"].fillna("").astype(str).str.strip()
    real["vertical"] = real["vertical"].fillna("").astype(str).str.strip()

    # join outer
    bud_agg = bud.groupby(["periodo", "vertical", "nome_cliente"], dropna=False).agg(
        bud_receita=("receita", "sum"),
        bud_custo=("custo", "sum"),
        bud_lb=("lb", "sum"),
    ).reset_index()

    merged = pd.merge(
        bud_agg, real,
        on=["periodo", "vertical", "nome_cliente"], how="outer"
    ).fillna(0)

    # Filtros
    vert_list = [v.strip() for v in verticais.split(",") if v.strip()]
    if vert_list:
        merged = merged[merged["vertical"].isin(vert_list)]
    cli_list = [c.strip() for c in clientes.split(",") if c.strip()]
    if cli_list:
        merged = merged[merged["nome_cliente"].isin(cli_list)]

    for c in ("bud_receita", "bud_custo", "bud_lb", "real_receita", "real_custo", "real_lb"):
        merged[c] = merged[c].round(2)

    return {
        "rows": merged.to_dict(orient="records"),
        "verticais_disponiveis": sorted([v for v in merged["vertical"].dropna().unique().tolist() if v]),
        "clientes_disponiveis": sorted([c for c in merged["nome_cliente"].dropna().unique().tolist() if c]),
    }


@app.get("/api/nova-base/margem/clientes")
def get_nova_base_margem_clientes(
    periodos: str = "", empresas: str = "", verticais: str = "", fontes: str = "",
    apuracoes: str = "", no_hierarquias: str = "",
    breakdown: bool = False,
    user=Depends(get_current_user)
):
    from datetime import datetime
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()
    if not periodos:
        df = df[df["periodo"].fillna("").astype(str) <= datetime.now().strftime("%Y-%m")]
    else:
        df = df[df["periodo"].isin([v.strip() for v in periodos.split(",")])]

    def _filt_with_blank(col: str, param: str) -> pd.DataFrame:
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if not vals or col not in df.columns:
            return df
        col_clean = df[col].fillna("").astype(str).str.strip()
        regular = [v for v in vals if v != "__blank__"]
        mask = pd.Series(False, index=df.index)
        if regular:
            mask = mask | col_clean.isin(regular)
        if "__blank__" in vals:
            mask = mask | (col_clean == "")
        return df[mask].copy()

    if empresas:
        df = _filt_with_blank("empresa", empresas)
    if verticais:
        df = _filt_with_blank("vertical", verticais)
    if fontes:
        df = _filt_with_blank("fonte_familia", fontes)
    if apuracoes:
        df = _filt_with_blank("apuracao", apuracoes)
    if no_hierarquias:
        df = _filt_with_blank("no_hierarquia", no_hierarquias)
    for col in ["receita", "custo_rateado", "horas", "valor_liquido"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df = df[df["nome_cliente"].fillna("").astype(str).str.strip().ne("")]
    # Margem Bruta = Receita + Custo direto (despesa NAO entra).
    _ma = df["macro_area"].fillna("").astype(str).str.strip().ne("") if "macro_area" in df.columns else pd.Series(False, index=df.index)
    _fs = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    _socio = _fs.isin(["Custo Socios", "Custo Sócios"])
    _cl = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    _is_desp = (_cl == "despesa") | ((_cl != "custo") & (_ma | _socio))
    df["custo_rateado"] = df["custo_rateado"].where(~_is_desp, 0)
    df["margem"] = df["receita"] + df["custo_rateado"]
    def _moda_cli(s):
        nz = s[s.fillna("").astype(str).str.strip().ne("")]
        m = nz.mode()
        return m.iloc[0] if len(m) else ""
    for _c in ("vertical", "no_hierarquia"):
        if _c not in df.columns:
            df[_c] = ""
    group_keys = ["nome_cliente", "periodo"] if breakdown else ["nome_cliente"]
    agg = df.groupby(group_keys, as_index=False).agg(
        receita        = ("receita",       "sum"),
        custo_rateado  = ("custo_rateado", "sum"),
        horas          = ("horas",         "sum"),
        margem         = ("margem",        "sum"),
        vertical       = ("vertical",      _moda_cli),
        no_hierarquia  = ("no_hierarquia", _moda_cli),
    )
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    # Normalmente lista clientes com receita; mas se há filtro de fonte
    # (ex.: só PJs, que não têm receita), mantém também os de custo.
    if fontes:
        agg = agg[(agg["receita"].abs() > 0.01) | (agg["custo_rateado"].abs() > 0.01)]
    else:
        agg = agg[agg["receita"].abs() > 0.01]
    agg = agg[agg["nome_cliente"].astype(str).str.strip().ne("0")]
    agg = agg.sort_values("receita", ascending=False)
    return _sanitize(agg.to_dict(orient="records"))


@app.get("/api/nova-base/margem/cliente-detalhe")
def get_nova_base_margem_cliente_detalhe(
    nome_cliente: str = "",
    periodos: str = "", empresas: str = "", verticais: str = "", fontes: str = "",
    apuracoes: str = "", no_hierarquias: str = "",
    breakdown: bool = False,
    user=Depends(get_current_user)
):
    from datetime import datetime
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()
    if not periodos:
        df = df[df["periodo"].fillna("").astype(str) <= datetime.now().strftime("%Y-%m")]
    else:
        df = df[df["periodo"].isin([v.strip() for v in periodos.split(",")])]

    def _filt_with_blank(col: str, param: str) -> pd.DataFrame:
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if not vals or col not in df.columns: return df
        col_clean = df[col].fillna("").astype(str).str.strip()
        regular = [v for v in vals if v != "__blank__"]
        mask = pd.Series(False, index=df.index)
        if regular: mask = mask | col_clean.isin(regular)
        if "__blank__" in vals: mask = mask | (col_clean == "")
        return df[mask].copy()

    if empresas:       df = _filt_with_blank("empresa", empresas)
    if verticais:      df = _filt_with_blank("vertical", verticais)
    if fontes:         df = _filt_with_blank("fonte_familia", fontes)
    if apuracoes:      df = _filt_with_blank("apuracao", apuracoes)
    if no_hierarquias: df = _filt_with_blank("no_hierarquia", no_hierarquias)
    for col in ["receita", "custo_rateado", "horas"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if nome_cliente:
        df = df[df["nome_cliente"].fillna("").astype(str).str.upper().str.strip() == nome_cliente.upper().strip()]
    # Margem Bruta = Receita + Custo direto (despesa NAO entra).
    _ma = df["macro_area"].fillna("").astype(str).str.strip().ne("") if "macro_area" in df.columns else pd.Series(False, index=df.index)
    _fs = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    _socio = _fs.isin(["Custo Socios", "Custo Sócios"])
    _cl = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    _is_desp = (_cl == "despesa") | ((_cl != "custo") & (_ma | _socio))
    df["custo_rateado"] = df["custo_rateado"].where(~_is_desp, 0)
    df["margem"] = df["receita"] + df["custo_rateado"]
    # pep_base ja vem propagado pelo backend (custo_gerencial/custo_project herdam
    # o PEP do racional da mesma pessoa+periodo). Usa essa coluna — NAO recompoe
    # de `pep` (que e vazio em custo_gerencial e excluiria o custo da visao).
    if "pep_base" not in df.columns:
        df["pep_base"] = df.get("pep", pd.Series("", index=df.index)).astype(str).str.split(".").str[0]
    df["pep_base"] = df["pep_base"].fillna("").astype(str).str.strip()
    # Linhas sem PEP (custo orfao — pessoa sem projeto atribuido) NAO sao
    # descartadas: viram um grupo "(sem PEP)" pra a visao por projeto bater
    # com o total do cliente na lista de clientes.
    _sem_pep = ~(df["pep_base"].str.len().gt(0) & ~df["pep_base"].str.lower().isin(["nan", "none", "0", "<na>"]))
    # Se o cliente tem exatamente 1 PEP real ATIVO (com receita ou custo), o
    # custo sem PEP é desse projeto.
    _act = df[~_sem_pep].groupby("pep_base")[["receita", "custo_rateado"]].sum()
    _reais = sorted(_act[(_act["receita"].round(2) != 0) | (_act["custo_rateado"].round(2) != 0)].index)
    if nome_cliente and len(_reais) == 1:
        df.loc[_sem_pep, "pep_base"] = _reais[0]
    else:
        df.loc[_sem_pep, "pep_base"] = "(sem PEP)"
    # Agrupa SO por PEP (+ periodo se breakdown) — 1 linha por projeto.
    # empresa/vertical viram a moda (valor dominante) pra nao fragmentar.
    group_keys = ["pep_base"] + (["periodo"] if breakdown else [])
    for k in group_keys:
        if k in df.columns:
            df[k] = df[k].fillna("")

    def _moda(s):
        m = s[s.astype(str).str.strip().ne("")].mode()
        return m.iloc[0] if len(m) else ""

    agg = df.groupby(group_keys, as_index=False).agg(
        empresa       = ("empresa",       _moda),
        vertical      = ("vertical",      _moda),
        receita       = ("receita",       "sum"),
        custo_rateado = ("custo_rateado", "sum"),
        horas         = ("horas",         "sum"),
        margem        = ("margem",        "sum"),
    )
    # Remove PEPs zerados (so horas, sem receita nem custo) — ruido na visao de margem
    agg = agg[(agg["receita"].round(2) != 0) | (agg["custo_rateado"].round(2) != 0)]
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    agg = agg.rename(columns={"pep_base": "pep"})
    sort_cols = ["periodo", "receita"] if breakdown else ["receita"]
    agg = agg.sort_values(sort_cols, ascending=[True, False] if breakdown else False)
    return _sanitize(agg.to_dict(orient="records"))


@app.get("/api/nova-base/margem/projeto-pessoas")
def get_nova_base_margem_projeto_pessoas(
    nome_cliente: str = "", pep: str = "",
    periodos: str = "", empresas: str = "", verticais: str = "", fontes: str = "",
    apuracoes: str = "", no_hierarquias: str = "", breakdown: bool = False,
    user=Depends(get_current_user)
):
    """Margem por pessoa dentro de um PEP/projeto de um cliente."""
    from datetime import datetime
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()
    if not periodos:
        df = df[df["periodo"].fillna("").astype(str) <= datetime.now().strftime("%Y-%m")]
    else:
        df = df[df["periodo"].isin([v.strip() for v in periodos.split(",")])]

    def _filt_with_blank(col: str, param: str) -> pd.DataFrame:
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if not vals or col not in df.columns: return df
        col_clean = df[col].fillna("").astype(str).str.strip()
        regular = [v for v in vals if v != "__blank__"]
        mask = pd.Series(False, index=df.index)
        if regular: mask = mask | col_clean.isin(regular)
        if "__blank__" in vals: mask = mask | (col_clean == "")
        return df[mask].copy()

    if empresas:       df = _filt_with_blank("empresa", empresas)
    if verticais:      df = _filt_with_blank("vertical", verticais)
    if fontes:         df = _filt_with_blank("fonte_familia", fontes)
    if apuracoes:      df = _filt_with_blank("apuracao", apuracoes)
    if no_hierarquias: df = _filt_with_blank("no_hierarquia", no_hierarquias)
    for col in ["receita", "custo_rateado", "horas"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if nome_cliente:
        df = df[df["nome_cliente"].fillna("").astype(str).str.upper().str.strip() == nome_cliente.upper().strip()]
    # pep_base ja vem propagado (custo_gerencial herda do racional) — usa a coluna
    if "pep_base" not in df.columns:
        df["pep_base"] = df.get("pep", pd.Series("", index=df.index)).astype(str).str.split(".").str[0]
    df["pep_base"] = df["pep_base"].fillna("").astype(str).str.strip()
    if pep:
        _blank = ~(df["pep_base"].str.len().gt(0) & ~df["pep_base"].str.lower().isin(["nan", "none", "0", "<na>"]))
        if pep.strip().lower() == "(sem pep)":
            df = df[_blank]
        else:
            _alvo = df["pep_base"].str.upper() == pep.upper().strip()
            # Cliente com 1 PEP só ativo: custo sem PEP entra nesse projeto.
            _act = df[~_blank].assign(_pu=df.loc[~_blank, "pep_base"].str.upper()) \
                              .groupby("_pu")[["receita", "custo_rateado"]].sum()
            _reais = sorted(_act[(_act["receita"].round(2) != 0) | (_act["custo_rateado"].round(2) != 0)].index)
            if nome_cliente and len(_reais) == 1 and _reais[0] == pep.upper().strip():
                df = df[_alvo | _blank]
            else:
                df = df[_alvo]
    # Margem Bruta = Receita + Custo direto (despesa NAO entra)
    _ma = df["macro_area"].fillna("").astype(str).str.strip().ne("") if "macro_area" in df.columns else pd.Series(False, index=df.index)
    _fs = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    _socio = _fs.isin(["Custo Socios", "Custo Sócios"])
    _cl = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    _is_desp = (_cl == "despesa") | ((_cl != "custo") & (_ma | _socio))
    df["custo_rateado"] = df["custo_rateado"].where(~_is_desp, 0)
    df["margem"] = df["receita"] + df["custo_rateado"]
    df["nome_pessoa"] = df["nome_pessoa"].fillna("").astype(str).str.strip()
    df = df[df["nome_pessoa"].ne("")]
    for c in ("empresa", "fonte"):
        if c in df.columns:
            df[c] = df[c].fillna("")

    def _moda(s):
        m = s[s.astype(str).str.strip().ne("")].mode()
        return m.iloc[0] if len(m) else ""

    # 1 linha por pessoa (receita do racional + custo da fonte PJs/custo_gerencial somados)
    group_cols = ["nome_pessoa", "periodo"] if breakdown else ["nome_pessoa"]
    if breakdown and "periodo" in df.columns:
        df["periodo"] = df["periodo"].fillna("").astype(str)
    agg = df.groupby(group_cols, as_index=False).agg(
        empresa       = ("empresa",       _moda),
        fonte         = ("fonte",         _moda),
        receita       = ("receita",       "sum"),
        custo_rateado = ("custo_rateado", "sum"),
        horas         = ("horas",         "sum"),
        margem        = ("margem",        "sum"),
    )
    # Remove pessoas zeradas (so horas, sem receita nem custo)
    agg = agg[(agg["receita"].round(2) != 0) | (agg["custo_rateado"].round(2) != 0)]
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    sort_cols = ["nome_pessoa", "periodo"] if breakdown else ["receita"]
    agg = agg.sort_values(sort_cols, ascending=False if not breakdown else [True, True])
    return _sanitize(agg.to_dict(orient="records"))


@app.get("/api/nova-base/margem/pessoa-clientes")
def get_nova_base_margem_pessoa_clientes(
    nome_pessoa: str = "",
    periodos: str = "", empresas: str = "", verticais: str = "", fontes: str = "",
    apuracoes: str = "", no_hierarquias: str = "", breakdown: bool = False,
    user=Depends(get_current_user)
):
    """Receita/custo de uma pessoa, quebrado por cliente (e opcionalmente por mês)."""
    from datetime import datetime
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()
    if not periodos:
        df = df[df["periodo"].fillna("").astype(str) <= datetime.now().strftime("%Y-%m")]
    else:
        df = df[df["periodo"].isin([v.strip() for v in periodos.split(",")])]

    def _filt_with_blank(col: str, param: str) -> pd.DataFrame:
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if not vals or col not in df.columns: return df
        col_clean = df[col].fillna("").astype(str).str.strip()
        regular = [v for v in vals if v != "__blank__"]
        mask = pd.Series(False, index=df.index)
        if regular: mask = mask | col_clean.isin(regular)
        if "__blank__" in vals: mask = mask | (col_clean == "")
        return df[mask].copy()

    if empresas:       df = _filt_with_blank("empresa", empresas)
    if verticais:      df = _filt_with_blank("vertical", verticais)
    if fontes:         df = _filt_with_blank("fonte_familia", fontes)
    if apuracoes:      df = _filt_with_blank("apuracao", apuracoes)
    if no_hierarquias: df = _filt_with_blank("no_hierarquia", no_hierarquias)
    for col in ["receita", "custo_rateado", "horas"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if nome_pessoa:
        df = df[df["nome_pessoa"].fillna("").astype(str).str.upper().str.strip() == nome_pessoa.upper().strip()]
    # Margem Bruta = Receita + Custo direto (despesa NAO entra)
    _ma = df["macro_area"].fillna("").astype(str).str.strip().ne("") if "macro_area" in df.columns else pd.Series(False, index=df.index)
    _fs = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    _socio = _fs.isin(["Custo Socios", "Custo Sócios"])
    _cl = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    _is_desp = (_cl == "despesa") | ((_cl != "custo") & (_ma | _socio))
    df["custo_rateado"] = df["custo_rateado"].where(~_is_desp, 0)
    df["margem"] = df["receita"] + df["custo_rateado"]
    df["nome_cliente"] = df["nome_cliente"].fillna("").astype(str).str.strip()
    df.loc[df["nome_cliente"].eq(""), "nome_cliente"] = "(sem cliente)"

    group_cols = ["nome_cliente", "periodo"] if breakdown else ["nome_cliente"]
    if breakdown and "periodo" in df.columns:
        df["periodo"] = df["periodo"].fillna("").astype(str)
    agg = df.groupby(group_cols, as_index=False).agg(
        receita       = ("receita",       "sum"),
        custo_rateado = ("custo_rateado", "sum"),
        horas         = ("horas",         "sum"),
        margem        = ("margem",        "sum"),
    )
    agg = agg[(agg["receita"].round(2) != 0) | (agg["custo_rateado"].round(2) != 0)]
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    sort_cols = ["nome_cliente", "periodo"] if breakdown else ["receita"]
    agg = agg.sort_values(sort_cols, ascending=False if not breakdown else [True, True])
    return _sanitize(agg.to_dict(orient="records"))


@app.get("/api/nova-base/download")
def download_nova_base(user=Depends(get_current_user)):
    """Baixa base completa como Excel."""
    import io
    from fastapi.responses import StreamingResponse
    df = _get_nova_base().copy()
    allowed_bus = get_user_bus(user)
    if allowed_bus and "vertical" in df.columns:
        df = df[df["vertical"].astype(str).str.strip().isin(allowed_bus)]
    cols = [c for c in [
        "fonte", "periodo", "empresa", "pep", "pep_base", "nome_pessoa",
        "nome_cliente", "tipo_contrato", "classificacao", "categoria_bu",
        "vertical", "area", "macro_area",
        "receita", "custo_rateado", "horas", "margem", "valor_liquido",
    ] if c in df.columns]
    df = df[cols]
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="Nova Base", engine="openpyxl")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=nova_base_completa.xlsx"},
    )

@app.get("/api/nova-base/pivot")
def get_nova_base_pivot(
    rows: str = "",
    cols: str = "",
    metric: str = "",
    metrics: str = "",
    agg: str = "sum",
    search: str = "",
    periodos: str = "",
    fontes: str = "",
    empresas: str = "",
    macro_areas: str = "",
    tipos_contrato: str = "",
    classificacoes: str = "",
    verticais: str = "",
    apuracoes: str = "",
    no_hierarquias: str = "",
    agrupadores_pl: str = "",
    user=Depends(get_current_user),
):
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()
    df = df[df["fonte"].astype(str) != "de para"]

    # Derive agrupador_pl from fonte/macro_area/receita
    fonte_s = df["fonte"].fillna("").astype(str).str.strip()
    ma_s = df["macro_area"].fillna("").astype(str).str.strip() if "macro_area" in df.columns else pd.Series("", index=df.index)
    rec_s = pd.to_numeric(df["receita"], errors="coerce").fillna(0)
    apl = pd.Series("Outros", index=df.index)
    apl[(fonte_s == "custo_gerencial") & (ma_s != "")] = "Despesa"
    apl[(fonte_s == "custo_gerencial") & (ma_s == "")] = "Custo Direto"
    apl[rec_s > 0] = "Receita"
    df["agrupador_pl"] = apl

    def filt(col, param):
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if vals and col in df.columns:
            col_clean = df[col].fillna("").astype(str).str.strip()
            regular_vals = [v for v in vals if v != "__blank__"]
            mask = pd.Series(False, index=df.index)
            if regular_vals:
                mask = mask | col_clean.isin(regular_vals)
            if "__blank__" in vals:
                mask = mask | (col_clean == "")
            return df[mask].copy()
        return df

    if periodos:        df = filt("periodo", periodos)
    if fontes:          df = filt("fonte_familia", fontes)
    if empresas:        df = filt("empresa", empresas)
    if macro_areas:     df = filt("macro_area", macro_areas)
    if tipos_contrato:  df = filt("tipo_contrato", tipos_contrato)
    if classificacoes:  df = filt("classificacao", classificacoes)
    if verticais:       df = filt("vertical", verticais)
    if apuracoes:       df = filt("apuracao", apuracoes)
    if no_hierarquias:  df = filt("no_hierarquia", no_hierarquias)
    if agrupadores_pl:  df = filt("agrupador_pl", agrupadores_pl)

    # Busca textual em campos chave
    if search:
        q = search.strip().lower()
        if q:
            search_cols = ["nome_pessoa", "nome_cliente", "pep_base", "pep", "empresa",
                           "fonte", "fonte_dados", "fonte_familia", "vertical", "macro_area"]
            mask = pd.Series(False, index=df.index)
            for c in search_cols:
                if c in df.columns:
                    mask = mask | df[c].fillna("").astype(str).str.lower().str.contains(q, regex=False)
            df = df[mask]

    ALLOWED_DIMS = {
        "periodo", "empresa", "fonte", "fonte_familia", "macro_area", "area",
        "tipo_contrato", "classificacao", "vertical", "apuracao", "no_hierarquia",
        "nome_cliente", "pep_base", "nome_pessoa", "centro_lucro", "billable_category",
        "agrupador_pl",
    }
    row_dims = [r.strip() for r in rows.split(",") if r.strip() in ALLOWED_DIMS and r.strip() in df.columns]
    col_dims = [c.strip() for c in cols.split(",") if c.strip() in ALLOWED_DIMS and c.strip() in df.columns]

    # Lista de metricas. Aceita CSV em `metrics`, ou single `metric` (backward compat).
    ALLOWED_METRICS = {"receita", "custo_rateado", "horas", "valor_liquido", "count"}
    raw_metrics = [m.strip() for m in metrics.split(",") if m.strip()] if metrics else ([metric] if metric else ["receita"])
    metric_list = [m for m in raw_metrics if m in ALLOWED_METRICS]
    if not metric_list:
        metric_list = ["receita"]

    for m in metric_list:
        col_name = f"_v_{m}"
        if m == "count":
            df[col_name] = 1
        elif m in df.columns:
            df[col_name] = pd.to_numeric(df[m], errors="coerce").fillna(0)
        else:
            df[col_name] = 0

    for d in row_dims + col_dims:
        df[d] = df[d].fillna("").astype(str).str.strip().replace("", "(Vazio)")

    val_cols = [f"_v_{m}" for m in metric_list]

    group_keys = row_dims + col_dims
    if not group_keys:
        record = {}
        for m, vc in zip(metric_list, val_cols):
            if agg == "avg":
                record[vc] = float(df[vc].mean()) if len(df) else 0.0
            elif agg == "count":
                record[vc] = float(len(df))
            else:
                record[vc] = float(df[vc].sum())
        return _sanitize({
            "rows": row_dims, "cols": col_dims, "metrics": metric_list, "agg": agg,
            "data": [record], "total_rows": len(df),
        })

    if agg == "avg":
        g = df.groupby(group_keys, dropna=False)[val_cols].mean().reset_index()
    elif agg == "count":
        g = df.groupby(group_keys, dropna=False)[val_cols].count().reset_index()
    else:
        g = df.groupby(group_keys, dropna=False)[val_cols].sum().reset_index()

    return _sanitize({
        "rows": row_dims, "cols": col_dims, "metrics": metric_list, "agg": agg,
        "data": g.to_dict(orient="records"), "total_rows": len(df),
    })

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
    apuracoes: str = "",
    no_hierarquias: str = "",
    nome_cliente: str = "",
    clientes: str = "",
    tipo_pessoa: str = "",
    metric: str = "",
    search: str = "",
    user=Depends(get_current_user)
):
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()

    # Remove fonte "de para" da Base Detalhada — sao mapeamentos auxiliares, nao dados.
    df = df[df["fonte"].astype(str) != "de para"]

    def filt(col, param):
        """Filtra por valores. Sentinel '__blank__' pega linhas vazias/NaN."""
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if vals and col in df.columns:
            col_clean = df[col].fillna("").astype(str).str.strip()
            regular_vals = [v for v in vals if v != "__blank__"]
            mask = pd.Series(False, index=df.index)
            if regular_vals:
                mask = mask | col_clean.isin(regular_vals)
            if "__blank__" in vals:
                mask = mask | (col_clean == "")
            return df[mask].copy()
        return df

    if periodos:       df = filt("periodo", periodos)
    if fontes:         df = filt("fonte_familia", fontes)
    if empresas:       df = filt("empresa", empresas)
    if macro_areas:    df = filt("macro_area", macro_areas)
    if areas:          df = filt("area", areas)
    if tipos_contrato: df = filt("tipo_contrato", tipos_contrato)
    if classificacoes: df = filt("classificacao", classificacoes)
    if verticais:      df = filt("vertical", verticais)
    if apuracoes:      df = filt("apuracao", apuracoes)
    if no_hierarquias: df = filt("no_hierarquia", no_hierarquias)
    if clientes:       df = filt("nome_cliente", clientes)

    # Busca textual server-side em vários campos (case-insensitive)
    if search:
        q = search.strip().lower()
        if q:
            search_cols = ["nome_pessoa", "nome_cliente", "pep_base", "pep", "empresa",
                           "fonte", "fonte_dados", "fonte_familia", "area", "macro_area", "vertical", "tipo_contrato"]
            mask = pd.Series(False, index=df.index)
            for c in search_cols:
                if c in df.columns:
                    mask = mask | df[c].fillna("").astype(str).str.lower().str.contains(q, regex=False)
            df = df[mask]

    if nome_cliente:
        df = df[df["nome_cliente"].fillna("").astype(str).str.upper().str.strip() == nome_cliente.upper().strip()]
    if tipo_pessoa:
        # Classifica e filtra por tipo (CLT/PJ/Outros) — mesma lógica do resumo
        import unicodedata
        def _norm_nome2(s: pd.Series) -> pd.Series:
            s = s.fillna("").astype(str).str.upper().str.strip()
            s = s.str.replace(r"\s+", " ", regex=True)
            s = s.apply(lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("ascii") if x else x)
            return s
        df_full = _get_nova_base()
        clt_nomes = set(_norm_nome2(df_full.loc[df_full["fonte"].astype(str) == "CLTs", "nome_pessoa"]).unique())
        pj_nomes  = set(_norm_nome2(df_full.loc[df_full["fonte"].astype(str) == "PJs",  "nome_pessoa"]).unique())
        cg_nomes  = set(_norm_nome2(df_full.loc[df_full["fonte"].astype(str) == "custo_gerencial", "nome_pessoa"]).unique())
        cp_nomes  = set(_norm_nome2(df_full.loc[df_full["fonte"].astype(str) == "custo_project", "nome_pessoa"]).unique())
        for s in (clt_nomes, pj_nomes, cg_nomes, cp_nomes):
            s.discard("")
        nome_norm = _norm_nome2(df["nome_pessoa"])
        tp = pd.Series("", index=df.index)
        tp[nome_norm.isin(clt_nomes)] = "CLT"
        tp[nome_norm.isin(pj_nomes)] = "PJ"
        tp[(tp == "") & nome_norm.isin(cg_nomes)] = "CLT"
        tp[(tp == "") & nome_norm.isin(cp_nomes)] = "PJ"
        tp[tp == ""] = "Outros"
        vals_tp = [v.strip() for v in tipo_pessoa.split(",") if v.strip()]
        df = df[tp.isin(vals_tp)]
    # Filtra por métrica: só linhas que contribuem pra aquele número.
    # Alinhado com a logica do Resumo (respeita classificacao explicita).
    if "macro_area" in df.columns:
        _ma = df["macro_area"].fillna("").astype(str).str.strip().ne("")
    else:
        _ma = pd.Series(False, index=df.index)
    _fonte_s = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    _is_socio = _fonte_s.isin(["Custo Socios", "Custo Sócios"])
    _classif = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    _expl_desp = _classif == "despesa"
    _expl_cus  = _classif == "custo"
    _is_despesa = _expl_desp | ((~_expl_cus) & (_ma | _is_socio))

    if metric == "receita":
        df = df[pd.to_numeric(df["receita"], errors="coerce").fillna(0) != 0]
    elif metric == "custo" or metric == "custo_rateado":
        df = df[(pd.to_numeric(df["custo_rateado"], errors="coerce").fillna(0) != 0) & (~_is_despesa)]
    elif metric == "despesa":
        df = df[(pd.to_numeric(df["custo_rateado"], errors="coerce").fillna(0) != 0) & _is_despesa]
    elif metric == "horas":
        df = df[pd.to_numeric(df["horas"], errors="coerce").fillna(0) != 0]
    elif metric == "valor_liquido":
        df = df[pd.to_numeric(df["valor_liquido"], errors="coerce").fillna(0) != 0]

    MAX = 5000
    total = len(df)
    df = df.head(MAX)

    cols_show = [
        "fonte_familia", "fonte", "fonte_dados", "periodo", "empresa", "pep_base", "nome_pessoa",
        "nome_cliente", "tipo_contrato", "classificacao", "area",
        "no_hierarquia", "macro_area", "vertical", "apuracao", "tipos", "agrupador",
        "receita", "custo_rateado", "horas", "margem",
        "valor_liquido", "taxa_hora", "billable_category", "tag_rateio", "Comentarios",
    ]
    cols_show = [c for c in cols_show if c in df.columns]
    return _sanitize({"total": total, "truncated": total > MAX, "rows": df[cols_show].to_dict(orient="records")})


def _split_custo_despesa(df: pd.DataFrame) -> tuple:
    """Retorna (custo_series, despesa_series, is_despesa_mask) com mesma logica
    do _sync_nova_base_calculada (despesa = macro_area filled ou Socios, exceto
    se classificacao explicita == 'custo')."""
    import numpy as np
    has_ma = df.get("macro_area", pd.Series("", index=df.index)).fillna("").astype(str).str.strip().ne("")
    fonte_s = df.get("fonte", pd.Series("", index=df.index)).fillna("").astype(str).str.strip()
    is_socio = fonte_s.isin(["Custo Socios", "Custo Sócios"])
    classif = df.get("classificacao", pd.Series("", index=df.index)).fillna("").astype(str).str.strip().str.lower()
    is_despesa = (classif == "despesa") | ((classif != "custo") & (has_ma | is_socio))
    custo_raw = pd.to_numeric(df["custo_rateado"], errors="coerce").fillna(0)
    return (
        np.where(~is_despesa, custo_raw, 0.0),
        np.where(is_despesa, custo_raw, 0.0),
        is_despesa,
    )


def _load_pessoas_lookup() -> dict:
    """CPF (digits) -> dict com nome, contrato, razao_social, cnpj, email."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {}
    try:
        headers = _supabase_headers()
        out = {}
        off = 0
        import re as _re
        with httpx.Client(timeout=30) as c:
            while True:
                r = c.get(f"{SUPABASE_URL}/rest/v1/pessoas?select=cpf,nome,email,contrato,razao_social,cnpj&offset={off}&limit=1000", headers=headers)
                if r.status_code != 200:
                    break
                data = r.json()
                for row in data:
                    cpf_d = _re.sub(r"[^\d]", "", str(row.get("cpf") or ""))
                    if len(cpf_d) >= 11:
                        out[cpf_d] = row
                if len(data) < 1000:
                    break
                off += 1000
        return out
    except Exception as e:
        print(f"[pessoas_lookup] {e}")
        return {}


@app.get("/api/workers")
def get_workers(
    periodos: str = "",
    verticais: str = "",
    clientes: str = "",
    user=Depends(get_current_user),
):
    """Lista de pessoas com receita, custo, margem e horas agregados.
    Inclui CPF, contrato, razao_social via JOIN com tabela pessoas.
    Filtro `clientes`: mostra so pessoas que tem alguma linha desses clientes
    (mantem o agregado completo da pessoa).
    """
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()
    if periodos:
        pers = [p.strip() for p in periodos.split(",") if p.strip()]
        if pers:
            df = df[df["periodo"].astype(str).isin(pers)]
    else:
        from datetime import datetime
        df = df[df["periodo"].fillna("").astype(str) <= datetime.now().strftime("%Y-%m")]
    if verticais:
        verts = [v.strip() for v in verticais.split(",") if v.strip()]
        if verts:
            df = df[df["vertical"].astype(str).isin(verts)]
    if clientes:
        cli_list = [c.strip() for c in clientes.split(",") if c.strip()]
        if cli_list:
            # Filtra linhas pra o(s) cliente(s) — os agregados refletem so o que
            # esta atribuido a esses clientes.
            df = df[df["nome_cliente"].astype(str).isin(cli_list)]

    df = df[df["nome_pessoa"].fillna("").astype(str).str.strip().ne("")]
    for c in ("receita", "custo_rateado", "horas"):
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    custo_s, _, _ = _split_custo_despesa(df)
    df["_custo"] = custo_s
    if "cpf" not in df.columns:
        df["cpf"] = ""

    agg = df.groupby("nome_pessoa").agg(
        receita=("receita", "sum"),
        custo=("_custo", "sum"),
        horas=("horas", "sum"),
        tipo_contrato=("tipo_contrato", lambda s: s.dropna().mode().iloc[0] if len(s.dropna().mode()) else ""),
        vertical=("vertical", lambda s: s.dropna().mode().iloc[0] if len(s.dropna().mode()) else ""),
        n_clientes=("nome_cliente", lambda s: s.fillna("").astype(str).str.strip().replace("", pd.NA).nunique()),
        cpf=("cpf", lambda s: s.dropna().astype(str).replace("", pd.NA).dropna().mode().iloc[0] if len(s.dropna().astype(str).replace("", pd.NA).dropna()) else ""),
    ).reset_index()

    # JOIN com pessoas (CPF -> contrato, razao_social, cnpj). Strippa BRCPF
    # prefix pra casar com as chaves digit-only do _load_pessoas_lookup.
    import re as _re_cpf
    def _cpf_d(c): return _re_cpf.sub(r"\D", "", str(c or ""))
    pessoas = _load_pessoas_lookup()
    agg["contrato"] = agg["cpf"].astype(str).map(lambda c: (pessoas.get(_cpf_d(c), {}) or {}).get("contrato") or "")
    agg["razao_social"] = agg["cpf"].astype(str).map(lambda c: (pessoas.get(_cpf_d(c), {}) or {}).get("razao_social") or "")
    agg["cnpj"] = agg["cpf"].astype(str).map(lambda c: (pessoas.get(_cpf_d(c), {}) or {}).get("cnpj") or "")
    agg["email"] = agg["cpf"].astype(str).map(lambda c: (pessoas.get(_cpf_d(c), {}) or {}).get("email") or "")

    agg["margem"] = agg["receita"] + agg["custo"]
    agg["margem_pct"] = (agg["margem"] / agg["receita"]).where(agg["receita"] != 0, 0).round(4)
    for c in ("receita", "custo", "margem", "horas"):
        agg[c] = agg[c].round(2)
    agg = agg.sort_values("receita", ascending=False)
    return _sanitize({"rows": agg.to_dict(orient="records")})


@app.get("/api/workers/detalhe")
def get_worker_detalhe(
    nome: str,
    periodos: str = "",
    user=Depends(get_current_user),
):
    """Detalhe de uma pessoa: totais por periodo e por cliente.
    Consulta nova_base_calculada direto (rapido, sem pipeline pesado).
    """
    if not nome:
        raise HTTPException(400, "nome obrigatorio")
    # Query direta na calculada — sem .copy() de 29K linhas.
    import urllib.parse
    nome_q = urllib.parse.quote(nome, safe="")
    headers = _supabase_headers()
    select_cols = "periodo,nome_cliente,receita,custo,despesa,horas,fonte,fonte_familia,empresa"
    allowed_bus = get_user_bus(user)
    bu_clause = ""
    if allowed_bus:
        select_cols += ",vertical"
        bus_q = ",".join(f'"{b}"' for b in allowed_bus)
        bu_clause = f"&vertical=in.({urllib.parse.quote(bus_q, safe='(),\"')})"
    params = f"select={select_cols}&nome_pessoa=eq.{nome_q}{bu_clause}"
    rows = []
    off = 0
    with httpx.Client(timeout=30) as c:
        while True:
            r = c.get(f"{SUPABASE_URL}/rest/v1/nova_base_calculada?{params}&offset={off}&limit=1000", headers=headers)
            if r.status_code != 200:
                raise HTTPException(500, f"Supabase err: {r.text[:200]}")
            d = r.json()
            rows += d
            if len(d) < 1000:
                break
            off += 1000
    if not rows:
        return {"nome": nome, "totais": {"horas": 0, "receita": 0, "custo": 0, "margem": 0},
                "por_periodo": [], "por_cliente": []}
    df = pd.DataFrame(rows)
    if periodos:
        pers = [p.strip() for p in periodos.split(",") if p.strip()]
        if pers:
            df = df[df["periodo"].astype(str).isin(pers)]
    if df.empty:
        return {"nome": nome, "totais": {"horas": 0, "receita": 0, "custo": 0, "margem": 0},
                "por_periodo": [], "por_cliente": []}

    for c in ("receita", "custo", "despesa", "horas"):
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["_custo"] = df["custo"]
    df["_cli"] = df["nome_cliente"].fillna("").astype(str).str.strip().replace("", "(sem cliente)")
    df["_fonte"] = df["fonte"].fillna("").astype(str).str.strip()

    tot_receita = float(df["receita"].sum())
    tot_custo = float(df["_custo"].sum())
    tot_despesa = float(df["despesa"].sum()) if "despesa" in df.columns else 0.0
    tot_horas = float(df["horas"].sum())

    # Por periodo
    por_per = df.groupby("periodo").agg(
        horas=("horas", "sum"), receita=("receita", "sum"), custo=("_custo", "sum"),
    ).reset_index()
    por_per["margem"] = por_per["receita"] + por_per["custo"]
    por_per = por_per.sort_values("periodo")

    # Por cliente
    por_cli = df.groupby("_cli").agg(
        horas=("horas", "sum"), receita=("receita", "sum"), custo=("_custo", "sum"),
    ).reset_index().rename(columns={"_cli": "nome_cliente"})
    por_cli["margem"] = por_cli["receita"] + por_cli["custo"]
    por_cli["pct_horas"] = (por_cli["horas"] / tot_horas).round(4) if tot_horas else 0.0
    por_cli = por_cli.sort_values("horas", ascending=False)

    # Por fonte (mostra de onde vem horas/custo/receita — exibe a "engrenagem" do rateio)
    por_fonte = df.groupby("_fonte").agg(
        horas=("horas", "sum"), receita=("receita", "sum"), custo=("_custo", "sum"),
    ).reset_index().rename(columns={"_fonte": "fonte"})
    por_fonte = por_fonte[(por_fonte["horas"] != 0) | (por_fonte["receita"] != 0) | (por_fonte["custo"] != 0)]
    por_fonte = por_fonte.sort_values("custo")  # mais negativo (CLT cgsap) primeiro

    # Por (cliente, fonte) — mostra de onde vieram as horas pra cada cliente
    por_cli_fonte = df.groupby(["_cli", "_fonte"]).agg(
        horas=("horas", "sum"), receita=("receita", "sum"), custo=("_custo", "sum"),
    ).reset_index().rename(columns={"_cli": "nome_cliente", "_fonte": "fonte"})
    por_cli_fonte = por_cli_fonte[
        (por_cli_fonte["horas"] != 0) | (por_cli_fonte["receita"] != 0) | (por_cli_fonte["custo"] != 0)
    ]

    for sub in (por_per, por_cli, por_fonte, por_cli_fonte):
        for c in ("receita", "custo", "margem", "horas"):
            if c in sub.columns:
                sub[c] = sub[c].round(2)

    return _sanitize({
        "nome": nome,
        "totais": {
            "horas": round(tot_horas, 2),
            "receita": round(tot_receita, 2),
            "custo": round(tot_custo, 2),
            "despesa": round(tot_despesa, 2),
            "margem": round(tot_receita + tot_custo, 2),
        },
        "por_periodo": por_per.to_dict(orient="records"),
        "por_cliente": por_cli.to_dict(orient="records"),
        "por_fonte": por_fonte.to_dict(orient="records"),
        "por_cliente_fonte": por_cli_fonte.to_dict(orient="records"),
    })


@app.get("/api/nova-base/dre")
def get_nova_base_dre(
    periodos: str = "",
    empresas: str = "",
    fontes: str = "",
    macro_areas: str = "",
    apuracoes: str = "",
    no_hierarquias: str = "",
    verticais: str = "",
    user=Depends(get_current_user)
):
    try:
        verticais = enforce_bu_filter(user, verticais)
        return _nova_base_dre_logic(periodos, empresas, fontes, macro_areas, apuracoes, no_hierarquias, verticais)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[nova-base/dre] ERRO: {e}\n{tb}")
        return JSONResponse(status_code=500, content={"detail": str(e), "traceback": tb},
                            headers={"Access-Control-Allow-Origin": "*"})

def _nova_base_dre_logic(periodos, empresas, fontes, macro_areas, apuracoes="", no_hierarquias="", verticais=""):
    from datetime import datetime
    df = _get_nova_base().copy()

    # Remove períodos futuros (sem dados reais) — exceto se o usuário filtrou explicitamente
    if not periodos:
        current_period = datetime.now().strftime("%Y-%m")
        df = df[df["periodo"].fillna("").astype(str) <= current_period]

    def filt(col, param):
        """Filtra por valores. Sentinel '__blank__' pega linhas vazias/NaN."""
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if vals and col in df.columns:
            col_clean = df[col].fillna("").astype(str).str.strip()
            regular_vals = [v for v in vals if v != "__blank__"]
            mask = pd.Series(False, index=df.index)
            if regular_vals:
                mask = mask | col_clean.isin(regular_vals)
            if "__blank__" in vals:
                mask = mask | (col_clean == "")
            return df[mask].copy()
        return df

    if periodos:       df = filt("periodo", periodos)
    if empresas:       df = filt("empresa", empresas)
    if fontes:         df = filt("fonte_familia", fontes)
    if apuracoes:      df = filt("apuracao", apuracoes)
    if no_hierarquias: df = filt("no_hierarquia", no_hierarquias)
    if verticais:      df = filt("vertical", verticais)
    # macro_areas filtra só despesas (linhas com macro_area); receita/custo direto não têm macro_area
    _macro_area_filter = [v.strip() for v in macro_areas.split(",") if v.strip()] if macro_areas else []

    df = df.copy()
    for col in ["receita", "custo_rateado", "valor_liquido"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["periodo"] = df["periodo"].fillna("").astype(str).str.strip()
    df = df[df["periodo"].str.match(r"^\d{4}-\d{2}$")].copy()

    if df.empty:
        return {"rows": [], "columns": []}

    # Remove períodos sem nenhum dado real (soma absoluta zero)
    if not periodos:
        period_totals = df.groupby("periodo")[["receita","custo_rateado"]].sum().abs().sum(axis=1)
        periods_with_data = set(period_totals[period_totals > 0].index)
        df = df[df["periodo"].isin(periods_with_data)]

    all_periods = sorted(df["periodo"].unique().tolist())
    columns = all_periods + ["Total"]

    # ── Helpers ────────────────────────────────────────────────────────────────
    def row_vals(piv_row: pd.Series):
        d = {p: float(piv_row[p]) for p in all_periods}
        d["Total"] = float(piv_row.sum())
        return d

    def pct_vals(rec_row: pd.Series, vl_row: pd.Series):
        d = {}
        for p in all_periods:
            rec = float(rec_row[p])
            vl  = float(vl_row[p])
            d[p] = vl / rec if rec else 0.0
        tot_rec = float(rec_row.sum())
        tot_vl  = float(vl_row.sum())
        d["Total"] = tot_vl / tot_rec if tot_rec else 0.0
        return d

    def zero_vals():
        return {c: 0.0 for c in columns}

    # ── Custo x Despesa ───────────────────────────────────────────────────────
    # Custo direto = TODO custo_rateado que não é despesa. Depois do rateio o
    # custo de CLT fica espalhado (custo_gerencial/CLTs residual + racionais +
    # custo_project) e o de PJ na fonte PJs — somar tudo dá o custo total.
    # Despesa = macro_area, sócios ou classificacao explícita 'despesa'.
    df["macro_area"] = df["macro_area"].fillna("").astype(str).str.strip() if "macro_area" in df.columns else ""
    df["_has_ma"] = df["macro_area"].ne("")
    _fonte_s = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    _socio = _fonte_s.isin(["Custo Socios", "Custo Sócios"])
    _cl = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    df["_is_desp"] = (_cl == "despesa") | ((_cl != "custo") & (df["_has_ma"] | _socio))

    # Receita: linhas de receita (racionais), sem macro_area
    df_rec = df[~df["_has_ma"]]
    agg_rec = df_rec.groupby("periodo")["receita"].sum().reindex(all_periods, fill_value=0)

    # Custo direto: tudo que não é despesa
    df_cus = df[~df["_is_desp"]]
    agg_cus = df_cus.groupby("periodo")["custo_rateado"].sum().reindex(all_periods, fill_value=0)

    agg_gp = agg_rec + agg_cus  # custo_rateado já é negativo

    rows = [
        {"name": "Receita",        "is_subtotal": True,  "is_pct": False, "is_group": False, "values": row_vals(agg_rec)},
        {"name": "Custo",          "is_subtotal": False, "is_pct": False, "is_group": False, "values": row_vals(agg_cus)},
        {"name": "Gross Profit",   "is_subtotal": True,  "is_pct": False, "is_group": False, "values": row_vals(agg_gp)},
        {"name": "Gross Margin %", "is_subtotal": True,  "is_pct": True,  "is_group": False, "values": pct_vals(agg_rec, agg_gp)},
    ]

    # ── Despesas: tudo classificado como despesa ──────────────────────────────
    df_desp = df[df["_is_desp"]]
    if _macro_area_filter:
        df_desp = df_desp[df_desp["macro_area"].isin(_macro_area_filter)]
    agg_desp_total = pd.Series(0.0, index=all_periods)
    if not df_desp.empty:
        agg_desp_total = (df_desp.groupby("periodo")["custo_rateado"]
                          .sum().reindex(all_periods, fill_value=0))
        rows.append({"name": "Despesas", "is_subtotal": True, "is_pct": False, "is_group": True, "values": row_vals(agg_desp_total)})
        # Detalhe por macro área (linhas de despesa que têm macro_area)
        df_desp_ma = df_desp[df_desp["_has_ma"]]
        if not df_desp_ma.empty:
            agg_ma_raw = (df_desp_ma.groupby(["macro_area", "periodo"])["custo_rateado"]
                          .sum().reset_index())
            for ma in sorted(agg_ma_raw["macro_area"].unique().tolist()):
                sub_cus = (agg_ma_raw[agg_ma_raw["macro_area"] == ma]
                           .set_index("periodo")["custo_rateado"]
                           .reindex(all_periods, fill_value=0))
                if float(sub_cus.sum()) != 0:
                    rows.append({"name": f"  {ma}", "is_subtotal": False, "is_pct": False, "is_group": False, "values": row_vals(sub_cus)})

    # ── EBITDA: Gross Profit + Despesas (despesa é negativa, somando = subtraindo) ─
    agg_ebitda = agg_gp + agg_desp_total
    rows.append({"name": "EBITDA", "is_subtotal": True, "is_pct": False, "is_group": False, "values": row_vals(agg_ebitda)})

    return _sanitize({"rows": rows, "columns": columns})


@app.get("/api/nova-base/margem-cliente")
def get_nova_base_margem_cliente(
    periodos: str = "",
    empresas: str = "",
    fontes: str = "",
    verticais: str = "",
    macro_areas: str = "",
    tipos_contrato: str = "",
    classificacoes: str = "",
    breakdown: bool = False,
    user=Depends(get_current_user)
):
    from datetime import datetime
    verticais = enforce_bu_filter(user, verticais)
    df = _get_nova_base().copy()

    if not periodos:
        current_period = datetime.now().strftime("%Y-%m")
        df = df[df["periodo"].fillna("").astype(str) <= current_period]

    def filt(col, param):
        """Filtra por valores. Sentinel '__blank__' pega linhas vazias/NaN."""
        vals = [v.strip() for v in param.split(",") if v.strip()]
        if vals and col in df.columns:
            col_clean = df[col].fillna("").astype(str).str.strip()
            regular_vals = [v for v in vals if v != "__blank__"]
            mask = pd.Series(False, index=df.index)
            if regular_vals:
                mask = mask | col_clean.isin(regular_vals)
            if "__blank__" in vals:
                mask = mask | (col_clean == "")
            return df[mask].copy()
        return df

    if periodos:       df = filt("periodo", periodos)
    if empresas:       df = filt("empresa", empresas)
    if fontes:         df = filt("fonte_familia", fontes)
    if verticais:      df = filt("vertical", verticais)
    if macro_areas:    df = filt("macro_area", macro_areas)
    if tipos_contrato: df = filt("tipo_contrato", tipos_contrato)
    if classificacoes: df = filt("classificacao", classificacoes)


    df = df.copy()
    for col in ["receita", "custo_rateado", "horas", "valor_liquido"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Custo (direto) vs Despesa: Margem Bruta usa SO custo direto.
    # despesa = linhas com macro_area, sócios, ou classificacao='despesa'.
    has_ma = df["macro_area"].fillna("").astype(str).str.strip().ne("") if "macro_area" in df.columns else pd.Series(False, index=df.index)
    fonte_s = df["fonte"].fillna("").astype(str).str.strip() if "fonte" in df.columns else pd.Series("", index=df.index)
    is_socio = fonte_s.isin(["Custo Socios", "Custo Sócios"])
    classif = df["classificacao"].fillna("").astype(str).str.strip().str.lower() if "classificacao" in df.columns else pd.Series("", index=df.index)
    expl_desp = classif == "despesa"
    expl_cus = classif == "custo"
    is_despesa = expl_desp | ((~expl_cus) & (has_ma | is_socio))
    df["_custo"] = df["custo_rateado"].where(~is_despesa, 0)

    # Margem Bruta = receita + custo direto (despesa NAO entra)
    df["_margem"] = df["receita"] + df["_custo"]

    # Normaliza campos de agrupamento
    for col in ["nome_cliente", "pep_base", "empresa", "vertical", "fonte", "periodo"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # Filtra linhas sem cliente
    df = df[df["nome_cliente"].ne("")]

    if breakdown:
        group_keys = ["periodo", "pep_base", "nome_cliente", "empresa", "vertical", "fonte"]
    else:
        group_keys = ["pep_base", "nome_cliente", "empresa", "vertical", "fonte"]

    group_keys = [k for k in group_keys if k in df.columns]

    agg = df.groupby(group_keys, as_index=False).agg(
        receita       = ("receita",       "sum"),
        custo_rateado = ("_custo",         "sum"),
        horas         = ("horas",         "sum"),
        margem        = ("_margem",       "sum"),
    )
    agg["margem_pct"] = agg.apply(
        lambda r: r["margem"] / r["receita"] if r["receita"] != 0 else None, axis=1
    )
    agg = agg.sort_values("receita", ascending=False)
    return _sanitize(agg.fillna("").to_dict(orient="records"))

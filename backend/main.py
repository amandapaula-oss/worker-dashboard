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
    if _cache["sap"] is None:
        if not os.path.exists("dados_sap.xlsx"):
            gdown.download(id=SAP_ID, output="dados_sap.xlsx", quiet=False, fuzzy=True)
        df = pd.read_excel("dados_sap.xlsx", usecols=[
            "CompanyCode", "agrupador_fpa", "FiscalPeriod",
            "AmountInCompanyCodeCurrency", "vertical", "ProfitCenter"
        ])
        df["CompanyCode"] = df["CompanyCode"].map(COMPANY_NAMES).fillna(df["CompanyCode"])
        _cache["sap"] = df
    return _cache["sap"]

def get_nexus() -> pd.DataFrame:
    if _cache["nexus"] is None:
        if not os.path.exists("nexus.xlsx"):
            gdown.download(id=NEXUS_ID, output="nexus.xlsx", quiet=False, fuzzy=True)
        df = pd.read_excel("nexus.xlsx", sheet_name="Nexus_Consolidado")
        # Detectar coluna de competência independente de encoding
        comp_col = next((c for c in df.columns if "ompet" in str(c)), None)
        agrup_col = next((c for c in df.columns if "grupador" in str(c)), None)
        keep = ["[Tipo]", "[Empresa]", "[Vertical]", "[Stream]", "[Valor]", "[Moeda]"]
        if comp_col: keep.append(comp_col)
        if agrup_col: keep.append(agrup_col)
        df = df[[c for c in keep if c in df.columns]]
        if agrup_col and agrup_col != "[Agrupador FP&A - COA]":
            df = df.rename(columns={agrup_col: "[Agrupador FP&A - COA]"})
        if comp_col:
            df[comp_col] = pd.to_datetime(df[comp_col], errors="coerce")
            df["Período"] = df[comp_col].dt.to_period("M").astype(str)
            df["Ano"] = df[comp_col].dt.year
            df = df.rename(columns={comp_col: "[Competência]"})
        _cache["nexus"] = df
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
        print("SAP carregado.")
    except Exception as e:
        print(f"Erro ao carregar SAP: {e}")
    try:
        print("Carregando Nexus...")
        get_nexus()
        _ready["nexus"] = True
        print("Nexus carregado. Servidor pronto.")
    except Exception as e:
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
    return {
        "status": "ready",
        "rows": len(df),
        "columns": list(df.columns),
        "tipos": df["[Tipo]"].dropna().unique().tolist(),
        "moedas": df["[Moeda]"].dropna().unique().tolist(),
        "anos": sorted(df["Ano"].dropna().unique().tolist()),
        "sample_tipo": str(df["[Tipo]"].iloc[0]) if len(df) > 0 else None,
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

@app.get("/api/dre")
def get_dre(anos="", tipo="Actual", empresas="", user=Depends(get_current_user)):
    if not _ready["nexus"]:
        raise HTTPException(status_code=503, detail="Nexus ainda carregando, aguarde...")
    df = get_nexus()
    if anos:
        df = df[df["Ano"].isin([int(a) for a in anos.split(",")])]
    if empresas:
        df = df[df["[Empresa]"].isin(empresas.split(","))]
    df = df[(df["[Tipo]"] == tipo) & (df["[Moeda]"] == "BRL")]
    if df.empty:
        return {"rows": [], "columns": []}
    return pl_to_json(compute_pl(df, "Período"))

@app.get("/api/streams")
def get_streams(anos="", tipo="Actual", empresas="", streams="", user=Depends(get_current_user)):
    if not _ready["nexus"]:
        raise HTTPException(status_code=503, detail="Nexus ainda carregando, aguarde...")
    df = get_nexus()
    if anos:
        df = df[df["Ano"].isin([int(a) for a in anos.split(",")])]
    if empresas:
        df = df[df["[Empresa]"].isin(empresas.split(","))]
    if streams:
        df = df[df["[Stream]"].isin(streams.split(","))]
    df = df[(df["[Tipo]"] == tipo) & (df["[Moeda]"] == "BRL")]
    if df.empty:
        return {"rows": [], "columns": []}
    return pl_to_json(compute_pl(df, "[Stream]"))

@app.get("/api/matricial")
def get_matricial(anos="", tipo="Actual", user=Depends(get_current_user)):
    if not _ready["nexus"]:
        raise HTTPException(status_code=503, detail="Nexus ainda carregando, aguarde...")
    df = get_nexus()
    if anos:
        df = df[df["Ano"].isin([int(a) for a in anos.split(",")])]
    df = df[(df["[Tipo]"] == tipo) & (df["[Moeda]"] == "BRL")]
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

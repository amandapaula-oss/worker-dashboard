"""
Consolida arquivos de Custo Gerencial na base_2026.csv.
Dois formatos:
  - "Gerencial V2 *.xlsx"       → Jan/Fev/Mar 2026  (abas: FC, HY, NX, SGA, ND, DOJO)
  - "Custo Gerencial Grupo *.xlsx" → Jun-Dez 2025  (abas: FCAMARA, HYPER, NEXT, NAÇÃO, OMNIK, SGA, DOJO)
"""
import sys, os, re
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
import numpy as np

PASTA   = os.path.join(os.path.dirname(__file__), "2026 dados", "custo gerancial")
BASE_CSV = os.path.join(os.path.dirname(__file__), "base_2026.csv")

# ── Mapeamento empresa (aba → nome padrão) ────────────────────────────────────
EMPRESA_MAP = {
    "FC":      "FCamara",  "FCAMARA":  "FCamara",
    "HY":      "Hyper",    "HYPER":    "Hyper",
    "NX":      "Next",     "NEXT":     "Next",
    "SGA":     "SGA",
    "ND":      "Nação Digital", "NAÇÃO": "Nação Digital",
    "DOJO":    "Dojo",
    "OMNIK":   "Omnik",
}

# ── Mapeamento período a partir do nome do arquivo ────────────────────────────
MESES_PT = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06",
    "julho": "07", "agosto": "08", "setembro": "09",
    "outubro": "10", "novembro": "11", "dezembro": "12",
}

def periodo_from_filename(fname: str) -> str | None:
    fname_l = fname.lower()
    # "Gerencial V2 janeiro 2026.xlsx"
    for mes, num in MESES_PT.items():
        if mes in fname_l:
            ano_m = re.search(r"(20\d\d)", fname)
            ano = ano_m.group(1) if ano_m else "2026"
            return f"{ano}-{num}"
    # "Custo Gerencial Grupo 07.25.xlsx"
    m = re.search(r"(\d{2})\.(\d{2})", fname)
    if m:
        return f"20{m.group(2)}-{m.group(1)}"
    return None

# ── Leitura de uma aba ────────────────────────────────────────────────────────
def _strip_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    return df

def _col(df: pd.DataFrame, *candidates) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    # fuzzy: nome contido
    for c in candidates:
        matches = [col for col in df.columns if c.lower() in col.lower()]
        if matches:
            return matches[0]
    return None

def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)

def parse_v2(xl: pd.ExcelFile, aba: str, periodo: str, empresa: str) -> pd.DataFrame:
    """Formato Gerencial V2 2026: cabeçalho em linha 0, dados a partir linha 1."""
    raw = xl.parse(aba, header=None, dtype=str)
    # Linha 0 = cabeçalho
    raw.columns = [str(v).strip() for v in raw.iloc[0]]
    raw = raw.iloc[1:].reset_index(drop=True)
    # Deduplica colunas repetidas (mantém a primeira ocorrência)
    seen: dict = {}
    new_cols = []
    for c in raw.columns:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}.{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    raw.columns = new_cols
    raw = raw[raw.columns.dropna()]

    nome_col   = _col(raw, "Nome")
    sap_col    = _col(raw, "N° ID SAP", "N°ID SAP")
    sal_col    = _col(raw, "Sal.Base", "Salário", "Salario")
    cust_col   = _col(raw, "Custo Gerencial SAP", "Totalizador")
    horas_col  = _col(raw, "Horas totais", "Total de horas trabalhadas")
    extra_col  = _col(raw, "hora extra", "Hora extra")
    noturno_col= _col(raw, "Adicional Noturno", "Adicional noturno")
    sobre_col  = _col(raw, "Sobreaviso")
    func_col   = _col(raw, "Função", "Funcao", "Cargo")
    local_col  = _col(raw, "Local")
    cad_col    = _col(raw, "Cad.", "Cad")

    if not nome_col or not cust_col:
        return pd.DataFrame()

    rows = raw[raw[nome_col].notna() & (raw[nome_col].str.strip() != "")].copy()

    def g(col): return _num(rows[col]) if col else pd.Series(0, index=rows.index)

    # Horas: pode vir como "168:00" ou "7 days, 0:00:00" ou número
    def parse_horas(series: pd.Series) -> pd.Series:
        result = []
        for v in series:
            v = str(v).strip()
            # "7 days, 3:30:00"
            days_m = re.match(r"(\d+)\s*day[s]?,?\s*(\d+):(\d+)", v)
            if days_m:
                result.append(int(days_m.group(1)) * 24 + int(days_m.group(2)) + int(days_m.group(3)) / 60)
                continue
            # "168:30"
            hm = re.match(r"(\d+):(\d+)", v)
            if hm:
                result.append(int(hm.group(1)) + int(hm.group(2)) / 60)
                continue
            try:
                result.append(float(v))
            except:
                result.append(0.0)
        return pd.Series(result, index=series.index)

    horas_vals = parse_horas(rows[horas_col]) if horas_col else pd.Series(0, index=rows.index)

    n = len(rows)
    def sv(col): return rows[col].str.strip().values if col and col in rows.columns else [""] * n
    return pd.DataFrame({
        "fonte":                     ["custo_gerencial"] * n,
        "fonte_dados":               [os.path.basename(xl.io) if hasattr(xl, "io") else ""] * n,
        "periodo":                   [periodo] * n,
        "empresa":                   [empresa] * n,
        "nome_pessoa":               sv(nome_col),
        "numero_pessoal":            sv(cad_col),
        "sal_base":                  g(sal_col).values,
        "funcao":                    sv(func_col),
        "local":                     sv(local_col),
        "custo_gerencial_sap":       g(cust_col).values,
        "horas_totais_trabalhadas":  horas_vals.values,
        "hora_extra":                g(extra_col).values,
        "adicional_noturno":         g(noturno_col).values,
        "sobreaviso":                g(sobre_col).values,
    })


def parse_grupo(xl: pd.ExcelFile, aba: str, periodo: str, empresa: str) -> pd.DataFrame:
    """Formato Custo Gerencial Grupo 2025: cabeçalho em linha 0 (pandas default)."""
    raw = xl.parse(aba, dtype=str)
    raw = _strip_cols(raw)

    nome_col    = _col(raw, "Nome")
    sap_col     = _col(raw, "N° ID SAP", "N°ID SAP")
    sal_col     = _col(raw, "Salário", "Salario", "Sal.Base")
    cust_col    = _col(raw, "Custo Gerencial SAP")
    horas_col   = _col(raw, "Horas totais")
    extra_col   = _col(raw, "hora extra")
    noturno_col = _col(raw, "Adicional noturno", "Adicional Noturno")
    sobre_col   = _col(raw, "Sobreaviso")
    func_col    = _col(raw, "Cargo", "Função")
    local_col   = _col(raw, "Local")
    cod_col     = _col(raw, "Codigo", "Cad.")

    if not nome_col or not cust_col:
        return pd.DataFrame()

    rows = raw[raw[nome_col].notna() & (raw[nome_col].str.strip() != "")].copy()

    def g(col): return _num(rows[col]) if col else pd.Series(0, index=rows.index)

    def parse_horas(series: pd.Series) -> pd.Series:
        result = []
        for v in series:
            v = str(v).strip()
            days_m = re.match(r"(\d+)\s*day[s]?,?\s*(\d+):(\d+)", v)
            if days_m:
                result.append(int(days_m.group(1)) * 24 + int(days_m.group(2)) + int(days_m.group(3)) / 60)
                continue
            hm = re.match(r"(\d+):(\d+)", v)
            if hm:
                result.append(int(hm.group(1)) + int(hm.group(2)) / 60)
                continue
            try:
                result.append(float(v))
            except:
                result.append(0.0)
        return pd.Series(result, index=series.index)

    horas_vals = parse_horas(rows[horas_col]) if horas_col else pd.Series(0, index=rows.index)

    n = len(rows)
    def sv(col): return rows[col].str.strip().values if col and col in rows.columns else [""] * n
    return pd.DataFrame({
        "fonte":                     ["custo_gerencial"] * n,
        "fonte_dados":               [os.path.basename(xl.io) if hasattr(xl, "io") else ""] * n,
        "periodo":                   [periodo] * n,
        "empresa":                   [empresa] * n,
        "nome_pessoa":               sv(nome_col),
        "numero_pessoal":            sv(cod_col),
        "sal_base":                  g(sal_col).values,
        "funcao":                    sv(func_col),
        "local":                     sv(local_col),
        "custo_gerencial_sap":       g(cust_col).values,
        "horas_totais_trabalhadas":  horas_vals.values,
        "hora_extra":                g(extra_col).values,
        "adicional_noturno":         g(noturno_col).values,
        "sobreaviso":                g(sobre_col).values,
    })


# ── Main ──────────────────────────────────────────────────────────────────────
all_frames = []

for fname in sorted(os.listdir(PASTA)):
    if not fname.endswith(".xlsx"):
        continue
    periodo = periodo_from_filename(fname)
    if not periodo:
        print(f"⚠ Não consegui extrair período de: {fname}")
        continue

    fpath = os.path.join(PASTA, fname)
    xl = pd.ExcelFile(fpath)
    is_v2 = fname.lower().startswith("gerencial v2")

    print(f"\n{fname} → {periodo}")
    for aba in xl.sheet_names:
        empresa = EMPRESA_MAP.get(aba.strip().upper(), aba.strip())
        try:
            if is_v2:
                df_aba = parse_v2(xl, aba, periodo, empresa)
            else:
                df_aba = parse_grupo(xl, aba, periodo, empresa)

            if df_aba.empty:
                print(f"  {aba}: vazio")
                continue

            # Filtra linhas com custo zero
            df_aba = df_aba[df_aba["custo_gerencial_sap"] != 0]
            print(f"  {aba} ({empresa}): {len(df_aba)} pessoas, custo=R${df_aba['custo_gerencial_sap'].sum():,.0f}")
            all_frames.append(df_aba)
        except Exception as e:
            print(f"  {aba}: ERRO — {e}")

if not all_frames:
    print("\nNenhum dado extraído.")
    sys.exit(1)

novo = pd.concat(all_frames, ignore_index=True)
print(f"\nTotal extraído: {len(novo)} linhas")
print(f"Períodos: {sorted(novo['periodo'].unique())}")
print(f"Custo total: R${novo['custo_gerencial_sap'].sum():,.2f}")

# ── Lookup macro_area via Mapa Pessoas ───────────────────────────────────────
MAPA_FILE = os.path.join(os.path.dirname(__file__), "2026 dados", "Mapa Pessoas - Jan26.xlsx")
try:
    xl_mapa = pd.ExcelFile(MAPA_FILE)
    df_clt = xl_mapa.parse("CLTs", dtype=str)
    cad_col  = next(c for c in df_clt.columns if "Cad" in c)
    macro_col = next(c for c in df_clt.columns if "Macro" in c and "rea" in c)
    lookup = (
        df_clt[[cad_col, macro_col]]
        .dropna(subset=[macro_col])
        .assign(**{cad_col: lambda x: x[cad_col].str.strip()})
        .drop_duplicates(subset=[cad_col])
        .rename(columns={cad_col: "numero_pessoal", macro_col: "macro_area"})
    )
    lookup["numero_pessoal"] = lookup["numero_pessoal"].str.strip()
    novo["numero_pessoal"] = novo["numero_pessoal"].astype(str).str.strip()
    novo = novo.merge(lookup, on="numero_pessoal", how="left")
    matched = novo["macro_area"].notna().sum()
    print(f"macro_area classificada: {matched}/{len(novo)} pessoas ({matched/len(novo)*100:.0f}%)")
    print(f"  {novo['macro_area'].value_counts().to_dict()}")
except Exception as e:
    print(f"⚠ Lookup macro_area falhou: {e}")
    novo["macro_area"] = ""

# ── Merge com base_2026.csv ────────────────────────────────────────────────────
print(f"\nCarregando {BASE_CSV}...")
base = pd.read_csv(BASE_CSV, low_memory=False, dtype=str)

# Remove linhas de custo_gerencial já existentes para evitar duplicata
before = len(base)
base = base[base["fonte"] != "custo_gerencial"]
print(f"Base: {before} → {len(base)} linhas (removidas {before-len(base)} antigas de custo_gerencial)")

# Alinha colunas
for col in base.columns:
    if col not in novo.columns:
        novo[col] = ""
novo = novo[[c for c in base.columns if c in novo.columns]]
for col in base.columns:
    if col not in novo.columns:
        novo[col] = ""
novo = novo.reindex(columns=base.columns, fill_value="")

base_final = pd.concat([base, novo], ignore_index=True)
print(f"Base final: {len(base_final)} linhas")

base_final.to_csv(BASE_CSV, index=False, encoding="utf-8")
print(f"✓ Salvo em {BASE_CSV}")

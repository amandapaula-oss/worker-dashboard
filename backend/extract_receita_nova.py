import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import win32com.client as win32
import pandas as pd
import re

FILE = r"C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\NewDashboard\Dados para apuração de metas\Nova pasta\Receita&Represado_2026 - Copia.xlsb"
APURACAO_FILE = r"C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\NewDashboard\Dados para apuração de metas\APURACAO Q4 bd para q4 feito no braço.xlsx"

# Colunas MapaReceita
MAPA_COLS = {
    "empresa":       1,   # A: Cod Empresa
    "projeto":       2,   # B: Projeto
    "tipo":          3,   # C: TipoPRJ
    "pep":           4,   # D: Elemento PEP
    "nome_projeto":  5,   # E: NomePrj
    "cod_cliente":   6,   # F: CodCliente
    "nome_cliente":  7,   # G: NomeCliente
    "centro_lucro":  8,   # H: Centro de Lucro
    "responsavel":   9,   # I: Responsável
    "2025-10":      70,   # BR
    "2025-11":      84,   # CF
    "2025-12":      98,   # CT
}

# Mapeamento Nó hierarquia padrão -> categoria BU
NO_HIERARQUIA_CATEGORIA = {
    "SQUAD_DT":   "Apps",
    "DIGITALMKT": "Demais",
    "IMAGINE":    "Demais",
    "OPENX":      "Apps",
    "CLOUD":      "Cloud/Cyber",
    "DATA":       "Dados",
    "ECOMM":      "Demais",
    "INNOVATION": "Demais",
    "BU":         "Vazio",
    "LICENSING":  "Vazio",
    "HYPER":      "Hyper",
    "MKTPLACE":   "Vazio",
    "BACKOFFICE": "Vazio",
}

# Colunas Base_PlanReal
BP_EMPRESA   = 1   # A
BP_COD_CLI   = 3   # C
BP_NOM_CLI   = 4   # D
BP_PEP       = 8   # H
BP_ANO_MES   = 10  # J
BP_CONTA     = 12  # L
BP_NRPESSOAL = 13  # M
BP_MONTANTE  = 14  # N

# Colunas DePara Consultor
DC_NOME      = 1   # A
DC_NRPESSOAL = 2   # B
DC_NOME_AJ   = 3   # C
DC_CC        = 4   # D
DC_EMPRESA   = 5   # E
DC_CONTRATO  = 7   # G

CONTAS_RECEITA = {'Receita a Faturar', 'Receita nac.produto', 'Receita Serv. Nacion',
                  'Receita de Serviços', 'Receita Reconhecida'}
PERIODOS_Q4   = {202510, 202511, 202512}
PERIODO_LABEL = {202510: '2025-10', 202511: '2025-11', 202512: '2025-12'}

# ── 0. Profit Center lookup (APURACAO xlsx) ────────────────────────────────
print("Lendo Profit Center...")
df_pc = pd.read_excel(APURACAO_FILE, sheet_name="Profit Center")
df_pc["Profit Centers"] = df_pc["Profit Centers"].astype(str).str.strip()
df_pc["no_hierarquia"]  = df_pc["Nó hierarquia padrão"].astype(str).str.strip().replace("nan", "")
df_pc["categoria_bu"]   = df_pc["no_hierarquia"].map(NO_HIERARQUIA_CATEGORIA).fillna("Vazio")
pc_lookup = df_pc.set_index("Profit Centers")[["no_hierarquia","categoria_bu"]].to_dict(orient="index")
print(f"  {len(pc_lookup)} profit centers mapeados")

print("Abrindo arquivo...")
excel = win32.Dispatch("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
wb = excel.Workbooks.Open(FILE)

# ── 1. MapaReceita -> rac_projetos ─────────────────────────────────────────
print("Lendo MapaReceita...")
ws_mapa = wb.Sheets("MapaReceita")
n_rows = ws_mapa.UsedRange.Rows.Count

proj_rows = []
CHUNK = 200
max_col = max(MAPA_COLS.values())

for r_start in range(3, n_rows + 1, CHUNK):
    r_end = min(r_start + CHUNK - 1, n_rows)
    vals = ws_mapa.Range(
        ws_mapa.Cells(r_start, 1),
        ws_mapa.Cells(r_end, max_col)
    ).Value
    if not vals:
        continue
    if not isinstance(vals[0], tuple):
        vals = (vals,)
    for row in vals:
        pep = row[MAPA_COLS["pep"] - 1]
        if not pep or str(pep).strip() in ('', 'None', 'Elemento PEP'):
            continue
        centro_lucro_raw = str(row[MAPA_COLS["centro_lucro"] - 1] or "").strip()
        # Centro de Lucro pode vir como "DC008 (Hyperautomation)" — extrai só o código
        centro_lucro_cod = centro_lucro_raw.split()[0] if centro_lucro_raw else ""
        pc_info      = pc_lookup.get(centro_lucro_cod, {})
        no_hier      = pc_info.get("no_hierarquia", "")
        cat_bu       = pc_info.get("categoria_bu", "Vazio")
        centro_lucro = centro_lucro_raw  # salva o valor completo
        for periodo, col in [("2025-10", 70), ("2025-11", 84), ("2025-12", 98)]:
            val = row[col - 1]
            if val is None or val == 0:
                continue
            proj_rows.append({
                "periodo":       periodo,
                "empresa":       row[MAPA_COLS["empresa"] - 1],
                "pep":           str(pep).strip(),
                "nome_cliente":  row[MAPA_COLS["nome_cliente"] - 1],
                "tipo":          row[MAPA_COLS["tipo"] - 1],
                "centro_lucro":  centro_lucro,
                "no_hierarquia": no_hier,
                "categoria_bu":  cat_bu,
                "valor_liquido": float(val) * -1,  # sinal contábil: negativo = receita
            })

df_proj = pd.DataFrame(proj_rows)
df_proj = df_proj[df_proj["valor_liquido"] != 0]
print(f"  rac_projetos: {len(df_proj)} linhas, {df_proj['pep'].nunique()} PEPs")
print(df_proj.groupby("categoria_bu")["valor_liquido"].sum().sort_values(ascending=False)
      .apply(lambda v: f"R$ {v:,.0f}").to_string())
df_proj.to_csv("rac_projetos.csv", index=False)
print("  Salvo: rac_projetos.csv")

# ── 2. DePara Consultor -> lookup NrPessoal -> nome/empresa ───────────────
print("Lendo DePara Consultor...")
ws_dc = wb.Sheets("DePara Consultor")
n_dc = ws_dc.UsedRange.Rows.Count
dc_vals = ws_dc.Range(ws_dc.Cells(2, 1), ws_dc.Cells(n_dc, 10)).Value
if dc_vals and not isinstance(dc_vals[0], tuple):
    dc_vals = (dc_vals,)

depara = {}
for row in dc_vals:
    if not row:
        continue
    # Bloco 1: cols A-G
    nr = row[DC_NRPESSOAL - 1]
    nome = row[DC_NOME - 1]
    if nr and nome:
        depara[str(int(nr)) if isinstance(nr, float) else str(nr)] = {
            "nome":     str(nome).strip(),
            "empresa":  str(row[DC_EMPRESA - 1] or "").strip(),
            "contrato": str(row[DC_CONTRATO - 1] or "").strip(),
        }

print(f"  DePara: {len(depara)} funcionários mapeados")

# ── 3. Base_PlanReal -> rac_pessoas ───────────────────────────────────────
print("Lendo Base_PlanReal (pode demorar)...")
ws_bp = wb.Sheets("Base_PlanReal")
n_bp = ws_bp.UsedRange.Rows.Count
print(f"  Total linhas: {n_bp}")

pess_rows = []
CHUNK_BP = 500

for r_start in range(2, n_bp + 1, CHUNK_BP):
    r_end = min(r_start + CHUNK_BP - 1, n_bp)
    vals = ws_bp.Range(
        ws_bp.Cells(r_start, 1),
        ws_bp.Cells(r_end, BP_MONTANTE)
    ).Value
    if not vals:
        continue
    if not isinstance(vals[0], tuple):
        vals = (vals,)
    for row in vals:
        ano_mes = row[BP_ANO_MES - 1]
        if not ano_mes:
            continue
        try:
            ano_mes_int = int(ano_mes)
        except:
            continue
        if ano_mes_int not in PERIODOS_Q4:
            continue
        conta = str(row[BP_CONTA - 1] or "").strip()
        if conta not in CONTAS_RECEITA:
            continue
        nr = row[BP_NRPESSOAL - 1]
        if not nr or str(nr).strip() in ('#', '', 'None'):
            continue
        montante = row[BP_MONTANTE - 1]
        if not montante:
            continue
        pep = str(row[BP_PEP - 1] or "").strip()
        nr_str = str(int(nr)) if isinstance(nr, float) else str(nr).strip()
        info = depara.get(nr_str, {})
        pess_rows.append({
            "periodo":     PERIODO_LABEL[ano_mes_int],
            "empresa":     str(row[BP_EMPRESA - 1] or "").strip(),
            "pep":         pep,
            "numero_pessoal": nr_str,
            "nome":        info.get("nome", ""),
            "valor_liquido": float(montante) * -1,
        })
    if r_start % 10000 < CHUNK_BP:
        print(f"  ... {r_start}/{n_bp} linhas processadas, {len(pess_rows)} registros Q4 encontrados")

df_pess = pd.DataFrame(pess_rows)
print(f"  rac_pessoas: {len(df_pess)} linhas, {df_pess['numero_pessoal'].nunique()} pessoas, {df_pess['pep'].nunique()} PEPs")
df_pess.to_csv("rac_pessoas.csv", index=False)
print("  Salvo: rac_pessoas.csv")

wb.Close(False)
excel.Quit()
print("\nConcluido!")

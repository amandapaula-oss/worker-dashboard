import pathlib, pandas as pd, unicodedata, re

def norm_nome(s):
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s

base = list(pathlib.Path("C:/Users/amanda.paula").glob("FCamara*"))[0]
rac_path = (
    base / "FCamara Files - CONTROLADORIA" / "30. FP&A NOVO"
    / "06. Cockpit - Desenvolvimentos" / "NewDashboard"
    / "Dados para apuração de metas" / "RacFinancial_Consolidado.xlsx"
)

te = pd.read_excel(rac_path, sheet_name="TimeAndExpenses", header=1)
te.columns = [c.strip() for c in te.columns]
te = te.dropna(subset=["PEP"])
te["nome_norm"] = te["PROFISSIONAL"].apply(norm_nome)
te["cpf"] = te["BRCPF"].astype(str).str.strip()

metas = pd.read_csv("metas_custo.csv", dtype={"numero_pessoal": str})
metas["nome_norm"] = metas["nome"].apply(norm_nome)
pj = metas[metas["tipo"] == "PJ"].copy()

# Os 13 CPFs que casaram via CPF mas não via nome
cpfs_13 = [
    "BRCPF11092032410", "BRCPF10211737623", "BRCPF33246754802",
    "BRCPF41344060803", "BRCPF36162658864", "BRCPF41397013826",
    "BRCPF02547194309", "BRCPF07845720461", "BRCPF06893995610",
    "BRCPF04037628635", "BRCPF05960318903", "BRCPF40254370829",
    "BRCPF30682776807",
]

rows = []
for cpf in cpfs_13:
    nome_rac = te[te["cpf"] == cpf]["PROFISSIONAL"].dropna().iloc[0] if len(te[te["cpf"] == cpf]) > 0 else "?"
    nome_pj  = pj[pj["numero_pessoal"] == cpf]["nome"].iloc[0] if len(pj[pj["numero_pessoal"] == cpf]) > 0 else "?"
    rows.append({"cpf": cpf, "nome_rac": nome_rac, "nome_pj": nome_pj})

df_out = pd.DataFrame(rows)
df_out.to_csv("cpf_nomes_comparacao.csv", index=False, encoding="utf-8-sig")
print("Salvo cpf_nomes_comparacao.csv")

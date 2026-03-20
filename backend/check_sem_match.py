import pathlib, pandas as pd, unicodedata, re
from rapidfuzz import process, fuzz

def norm_nome(s):
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s

def fmt_periodo(ts):
    if pd.isna(ts): return None
    try: return f"{pd.Timestamp(ts).year}-{pd.Timestamp(ts).month:02d}"
    except: return None

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

exact = set(metas["nome_norm"].unique())
all_metas = list(exact)

sem_match_nomes = [n for n in te["nome_norm"].unique() if n not in exact]

# identifica os que tiveram fuzzy match
fuzzy_matched = set()
for n in sem_match_nomes:
    res = process.extractOne(n, all_metas, scorer=fuzz.token_sort_ratio, score_cutoff=88)
    if res:
        fuzzy_matched.add(n)

# nomes sem match algum (nem exato nem fuzzy)
truly_sem = [n for n in sem_match_nomes if n not in fuzzy_matched]
# filtra não-pessoas óbvias
IGNORAR = {"MAQUINAS", "COBRANCA RETROATIVA", "NAN", ""}
truly_sem = [n for n in truly_sem if n not in IGNORAR]

pj_cpfs  = set(metas[metas["tipo"] == "PJ"]["numero_pessoal"].str.strip())
clt_nomes = set(metas[metas["tipo"] == "CLT"]["nome_norm"])

te_sem = te[te["nome_norm"].isin(truly_sem)][["nome_norm","cpf"]].drop_duplicates()

results = []
for _, row in te_sem.iterrows():
    cpf = row["cpf"]
    in_pj  = cpf in pj_cpfs
    results.append({
        "nome_rac":   row["nome_norm"],
        "cpf_rac":    cpf,
        "na_base_pj": in_pj,
        "sem_custo":  not in_pj,
    })

df = pd.DataFrame(results).sort_values("na_base_pj", ascending=False)
df.to_csv("sem_match_analise.csv", index=False, encoding="utf-8-sig")

with open("sem_match_analise.txt", "w", encoding="utf-8") as f:
    f.write(f"Total sem match (nome + fuzzy): {len(df)}\n")
    f.write(f"Com CPF na base PJ (custo via CPF): {df['na_base_pj'].sum()}\n")
    f.write(f"Sem custo em nenhuma base: {df['sem_custo'].sum()}\n\n")

    f.write("=== COM CUSTO VIA CPF (PJ) ===\n")
    for _, r in df[df["na_base_pj"]].iterrows():
        f.write(f"  {r['nome_rac']} | {r['cpf_rac']}\n")

    f.write("\n=== SEM CUSTO EM NENHUMA BASE ===\n")
    for _, r in df[df["sem_custo"]].iterrows():
        f.write(f"  {r['nome_rac']} | {r['cpf_rac']}\n")

print(open("sem_match_analise.txt", encoding="utf-8").read())

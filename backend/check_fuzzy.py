import pathlib, pandas as pd, unicodedata, re
from rapidfuzz import process, fuzz

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

metas = pd.read_csv("metas_custo.csv", dtype={"numero_pessoal": str})
metas["nome_norm"] = metas["nome"].apply(norm_nome)

exact = set(metas["nome_norm"].unique())
all_metas = list(exact)

sem_match = [n for n in te["nome_norm"].unique() if n not in exact]
rows = []
for n in sem_match:
    res = process.extractOne(n, all_metas, scorer=fuzz.token_sort_ratio, score_cutoff=88)
    if res:
        rows.append({"nome_rac": n, "nome_metas": res[0], "score": res[1]})
    else:
        rows.append({"nome_rac": n, "nome_metas": "", "score": 0})

df_log = pd.DataFrame(rows).sort_values("score", ascending=False)
df_log.to_csv("fuzzy_matches_log.csv", index=False, encoding="utf-8-sig")
print(f"Salvo fuzzy_matches_log.csv ({len(df_log)} nomes)")

# Salva também um txt legível
with open("fuzzy_matches_log.txt", "w", encoding="utf-8") as f:
    f.write("=== Com match (score >= 88) ===\n")
    for _, r in df_log[df_log["score"] > 0].iterrows():
        f.write(f"  [{r['score']:.0f}] '{r['nome_rac']}' -> '{r['nome_metas']}'\n")
    f.write("\n=== Sem match ===\n")
    for n in df_log[df_log["score"] == 0]["nome_rac"]:
        f.write(f"  {n}\n")

print("Salvo fuzzy_matches_log.txt")

import pandas as pd, unicodedata, re

def norm(s):
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s

metas = pd.read_csv("metas_custo.csv", dtype={"numero_pessoal": str})
rac = pd.read_csv("margem_pessoas.csv", dtype={"cpf": str})

print("=== metas_custo ===")
res = metas[metas["nome"].str.upper().str.contains("FABIO|FABIO", na=False)][["nome","numero_pessoal","tipo"]].drop_duplicates()
for _, r in res.iterrows():
    print(f"  [{r['tipo']}] {r['nome']} (id={r['numero_pessoal']}) -> norm: {norm(r['nome'])}")

print("\n=== margem_pessoas (RAC) ===")
res2 = rac[rac["nome"].str.contains("abio", na=False, case=False)][["nome","cpf"]].drop_duplicates()
for _, r in res2.iterrows():
    print(f"  {r['nome']} (cpf={r['cpf']}) -> norm: {norm(r['nome'])}")

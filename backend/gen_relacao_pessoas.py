import pandas as pd
import unicodedata, re, os

def norm_nome(s):
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s

out_dir = os.path.dirname(__file__)

# metas_custo: numero_pessoal + nome
metas = pd.read_csv(os.path.join(out_dir, "metas_custo.csv"), dtype={"numero_pessoal": str})
metas["nome_norm"] = metas["nome"].apply(norm_nome)
pessoas_metas = metas[["tipo","numero_pessoal","nome","empresa","nome_norm"]].drop_duplicates(subset=["numero_pessoal","nome_norm"])

# margem_pessoas: cpf (BRCPF) + nome
pess = pd.read_csv(os.path.join(out_dir, "margem_pessoas.csv"), dtype={"cpf": str})
pess["nome_norm"] = pess["nome"].apply(norm_nome)
pessoas_rac = pess[["cpf","nome","empresa","nome_norm"]].drop_duplicates(subset=["cpf","nome_norm"])

# PJ: numero_pessoal IS the cpf (BRCPF format)
# Deduplica pessoas_rac por CPF: mantém o nome mais longo (mais completo)
pj_metas = pessoas_metas[pessoas_metas["tipo"] == "PJ"].copy()
pj_metas = pj_metas.rename(columns={"numero_pessoal": "cpf", "nome": "nome_metas"})
pj_metas = pj_metas.sort_values("nome_metas", key=lambda s: s.str.len(), ascending=False).drop_duplicates(subset=["cpf"])

pj_rac = pessoas_rac.copy()
pj_rac = pj_rac.sort_values("nome", key=lambda s: s.str.len(), ascending=False).drop_duplicates(subset=["cpf"])

pj_joined = pj_metas.merge(
    pj_rac[["cpf","nome"]].rename(columns={"nome":"nome_rac"}),
    on="cpf", how="outer"
)
# Prefere nome do metas (mais completo/oficial), fallback para RAC
pj_joined["nome_final"] = pj_joined["nome_metas"].fillna(pj_joined["nome_rac"])
pj_joined["id_sap"] = ""
pj_joined["tipo"] = "PJ"
if "empresa" not in pj_joined.columns:
    pj_joined["empresa"] = ""

# CLT: numero_pessoal = SAP ID, join por nome_norm
clt_metas = pessoas_metas[pessoas_metas["tipo"] == "CLT"].copy()
clt_metas = clt_metas.rename(columns={"numero_pessoal": "id_sap", "nome": "nome_metas"})
clt_joined = clt_metas.merge(
    pessoas_rac[["nome_norm","cpf","nome"]].rename(columns={"nome":"nome_rac"}),
    on="nome_norm", how="outer"
)
clt_joined["nome_final"] = clt_joined["nome_metas"].fillna(clt_joined["nome_rac"])
if "cpf" not in clt_joined.columns:
    clt_joined["cpf"] = ""
clt_joined["cpf"] = clt_joined["cpf"].fillna("")
clt_joined["tipo"] = "CLT"

# Consolidar
pj_out  = pj_joined[["tipo","nome_final","id_sap","cpf","empresa"]].rename(columns={"nome_final":"nome"})
clt_out = clt_joined[["tipo","nome_final","id_sap","cpf","empresa"]].rename(columns={"nome_final":"nome"})

df_out = pd.concat([pj_out, clt_out], ignore_index=True)
df_out = df_out.sort_values(["tipo","nome"]).drop_duplicates(subset=["tipo","nome","cpf"])
df_out = df_out.rename(columns={
    "tipo":     "Tipo",
    "nome":     "Nome",
    "id_sap":   "ID SAP",
    "cpf":      "CPF / Worker ID",
    "empresa":  "Empresa",
})

output_path = os.path.join(out_dir, "relacao_pessoas.xlsx")
df_out.to_excel(output_path, index=False)
print(f"Salvo: {output_path}")
print(f"Total: {len(df_out)} pessoas")
print(df_out.groupby("Tipo").size().to_string())

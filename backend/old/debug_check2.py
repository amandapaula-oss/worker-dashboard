import pandas as pd

proj = pd.read_csv('margem_projetos.csv', dtype={'pep': str})
pess = pd.read_csv('margem_pessoas.csv', dtype={'cpf': str})
razao_raw = pd.read_csv('razao_agg.csv')
metas = pd.read_csv('metas_custo.csv', dtype={'numero_pessoal': str})

# Replicar lógica do endpoint
razao = razao_raw.copy()
razao["periodo"] = razao["FiscalYear"].astype(int).astype(str) + "-" + razao["FiscalPeriod"].astype(int).apply(lambda x: f"{x:02d}")

# Filtrar out-dez
periodos = ["2025-10","2025-11","2025-12"]
razao = razao[razao["periodo"].isin(periodos)]
proj  = proj[proj["periodo"].isin(periodos)]
pess  = pess[pess["periodo"].isin(periodos)]

razao_receita = (
    razao[razao["agrupador_fpa"] == "Net Revenue"]
    .groupby(["empresa","periodo"], as_index=False)["AmountInCompanyCodeCurrency"]
    .sum().rename(columns={"AmountInCompanyCodeCurrency": "receita_razao"})
)
receita_rac = proj.groupby(["empresa","periodo"], as_index=False)["receita"].sum()

print("razao_receita empresas:", razao_receita["empresa"].unique().tolist())
print("receita_rac empresas:", receita_rac["empresa"].unique().tolist())
print()

# Check if names match exactly
for e in razao_receita["empresa"].unique():
    match = e in receita_rac["empresa"].values
    print(f"  razao empresa '{e}' ({e.encode()}) -> match in proj: {match}")

print()
# Merge
pj_cpfs = set(metas[metas["tipo"] == "PJ"]["numero_pessoal"].dropna().unique())
pess["is_pj"] = pess["cpf"].isin(pj_cpfs)
custo_pj  = pess[pess["is_pj"]].groupby(["empresa","periodo"], as_index=False)["custo_rateado"].sum().rename(columns={"custo_rateado": "custo_pj"})
custo_clt = pess[~pess["is_pj"]].groupby(["empresa","periodo"], as_index=False)["custo_rateado"].sum().rename(columns={"custo_rateado": "custo_clt"})

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

df = razao_receita \
    .merge(razao_payroll, on=["empresa","periodo"], how="outer") \
    .merge(razao_3p, on=["empresa","periodo"], how="outer") \
    .merge(receita_rac, on=["empresa","periodo"], how="outer") \
    .merge(custo_clt, on=["empresa","periodo"], how="outer") \
    .merge(custo_pj, on=["empresa","periodo"], how="outer")

df = df.fillna(0)
df["receita_razao"] = df["receita_razao"] * -1
df["custo_clt"] = df["custo_clt"] * -1
df["custo_pj"]  = df["custo_pj"]  * -1

print(f"Rows no df final: {len(df)}")
print(f"Receita RAC total: R$ {df['receita'].sum():,.0f}")
print(f"Receita Razão total: R$ {df['receita_razao'].sum():,.0f}")
print()
print("Por empresa:")
print(df.groupby("empresa")[["receita","receita_razao"]].sum().apply(lambda c: c.map(lambda x: f"R$ {x:,.0f}")).to_string())

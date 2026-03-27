import pandas as pd

proj = pd.read_csv('margem_projetos.csv', dtype={'pep': str})
proj_oct_dec = proj[proj['periodo'] >= '2025-10']

print('=== margem_projetos (out-dez) ===')
print(f'Receita total: R$ {proj_oct_dec["receita"].sum():,.0f}')
print('Por empresa:')
print(proj_oct_dec.groupby('empresa')['receita'].sum().sort_values(ascending=False).apply(lambda x: f'R$ {x:,.0f}').to_string())

razao = pd.read_csv('razao_agg.csv')
razao_oct_dec = razao[razao['FiscalPeriod'] >= 10]
nr = razao_oct_dec[razao_oct_dec['agrupador_fpa'] == 'Net Revenue']
print('\n=== razao Net Revenue (out-dez) ===')
print(f'Total: R$ {nr["AmountInCompanyCodeCurrency"].sum() * -1:,.0f}')
print('Por empresa:')
print((nr.groupby('empresa')['AmountInCompanyCodeCurrency'].sum() * -1).sort_values(ascending=False).apply(lambda x: f'R$ {x:,.0f}').to_string())

print('\n=== Empresas em margem mas NAO em razao ===')
emp_margem = set(proj_oct_dec['empresa'].unique())
emp_razao = set(nr['empresa'].unique())
print('Só em margem:', emp_margem - emp_razao)
print('Só em razão:', emp_razao - emp_margem)

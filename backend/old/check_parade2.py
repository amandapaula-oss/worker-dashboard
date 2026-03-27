import pandas as pd, unicodedata, re, sys, openpyxl
from rapidfuzz import process, fuzz
sys.stdout.reconfigure(encoding='utf-8')

def norm(s):
    s = str(s).upper().strip()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\s+', ' ', s)
    return s

path = 'C:/Users/amanda.paula/Downloads/Racional Tentativa yuri.xlsx'

# CUTOS CLTs: nomes únicos coluna D + info
clt = pd.read_excel(path, sheet_name='CUTOS CLTs', header=0)
clt.columns = [str(c).strip() for c in clt.columns]
print('CUTOS CLTs colunas:', clt.columns.tolist()[:6])

# Pega nome (coluna D) e empresa
clt_pessoas = clt[['Nome','Empresa','N° ID SAP']].dropna(subset=['Nome']).copy()
clt_pessoas['nome_norm'] = clt_pessoas['Nome'].apply(norm)
clt_unicas = clt_pessoas.drop_duplicates(subset=['nome_norm'])
print(f'CLTs únicos: {len(clt_unicas)}')

# PARA DE PESSOAS coluna C (já com nomes ajustados)
pess = pd.read_excel(path, sheet_name='PARA DE PESSOAS', header=0)
pess.columns = [str(c).strip() for c in pess.columns]
nomes_pess_norm = set(pess['Nome'].dropna().apply(norm))
print(f'PARA DE PESSOAS únicos: {len(nomes_pess_norm)}')

# Nossa base relacao_pessoas
rel = pd.read_excel('relacao_pessoas.xlsx')
rel.columns = [str(c).strip() for c in rel.columns]
nomes_rel = set(rel['Nome'].dropna().apply(norm))
print(f'Nossa base: {len(nomes_rel)}')
print()

# CLTs que NÃO estão em PARA DE PESSOAS
nao_em_pess = clt_unicas[~clt_unicas['nome_norm'].isin(nomes_pess_norm)]
print(f'CLTs não encontrados em PARA DE PESSOAS: {len(nao_em_pess)}')
for _, r in nao_em_pess.iterrows():
    print(f'  {r["Nome"]} | {r["Empresa"]}')

print()

# CLTs que NÃO estão na nossa base (relacao_pessoas)
nao_em_base = clt_unicas[~clt_unicas['nome_norm'].isin(nomes_rel)]
print(f'CLTs não encontrados na nossa base: {len(nao_em_base)}')
for _, r in nao_em_base.iterrows():
    # Tenta fuzzy
    m = process.extractOne(r['nome_norm'], list(nomes_rel), scorer=fuzz.token_sort_ratio, score_cutoff=85)
    sugestao = m[0] if m else 'SEM SUGESTAO'
    print(f'  {r["Nome"]} | {r["Empresa"]} -> fuzzy: {sugestao}')

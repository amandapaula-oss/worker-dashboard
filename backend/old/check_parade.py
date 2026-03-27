import pandas as pd, unicodedata, re, sys
from rapidfuzz import process, fuzz
sys.stdout.reconfigure(encoding='utf-8')

def norm(s):
    s = str(s).upper().strip()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\s+', ' ', s)
    return s

path = 'C:/Users/amanda.paula/Downloads/Racional Tentativa yuri.xlsx'

# PARA DE PESSOAS - coluna Nome (original, não ajustada pelo script anterior)
pess = pd.read_excel(path, sheet_name='PARA DE PESSOAS', header=0)
pess.columns = [str(c).strip() for c in pess.columns]
nomes_pess = pess['Nome'].dropna().apply(lambda x: str(x).strip())
nomes_pess_norm = nomes_pess.apply(norm)

# Nossa base (relacao_pessoas.xlsx)
rel = pd.read_excel('relacao_pessoas.xlsx')
rel.columns = [str(c).strip() for c in rel.columns]
nomes_rel_norm = set(rel['Nome'].dropna().apply(norm))
print(f'PARA DE PESSOAS: {len(nomes_pess)} | Nossa base: {len(nomes_rel_norm)}')

# Não encontrados por match exato
nao_encontrados = [(nomes_pess.iloc[i], nomes_pess_norm.iloc[i])
                   for i in range(len(nomes_pess_norm))
                   if nomes_pess_norm.iloc[i] not in nomes_rel_norm]
print(f'Não encontrados (exato): {len(nao_encontrados)}')

# Tenta fuzzy nos não encontrados
nomes_rel_norm_list = list(nomes_rel_norm)
sem_fuzzy = []
com_fuzzy = []
for orig, n in nao_encontrados:
    match = process.extractOne(n, nomes_rel_norm_list, scorer=fuzz.token_sort_ratio, score_cutoff=88)
    if match:
        com_fuzzy.append((orig, match[0], match[1]))
    else:
        sem_fuzzy.append(orig)

print(f'Com fuzzy match (>=88): {len(com_fuzzy)}')
print(f'Sem match mesmo com fuzzy: {len(sem_fuzzy)}')
print()
print('=== Genuinamente ausentes da nossa base ===')
for n in sem_fuzzy:
    print(f'  {n}')

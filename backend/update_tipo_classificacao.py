import pandas as pd
import unicodedata
import os

BASE_DIR = os.path.dirname(__file__)

PESSOAS_PATH = os.path.join(BASE_DIR, "relacao_pessoas.xlsx")
SOURCE_PATH = (
    r"C:\Users\amanda.paula\FCamara Consultoria e Formação"
    r"\FCamara Files - CONTROLADORIA\30. FP&A NOVO"
    r"\06. Cockpit - Desenvolvimentos\NewDashboard"
    r"\Dados para apuração de metas\Base atualizada de pessoas.xlsx"
)


def norm(s):
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


# --- Ler classificações da fonte ---
raw = pd.read_excel(SOURCE_PATH, sheet_name="TimeAndExpenses", header=0)

# Coluna L = índice 11 (Profissional), Coluna T = índice 19 (Tipo)
raw = raw.iloc[:, [11, 19]]
raw.columns = ["nome", "tipo"]

# Remover linhas de cabeçalho interno e entradas sem nome/tipo real
raw = raw[~raw["nome"].isin(["PROFISSIONAL", "Profissional", None])]
raw = raw[raw["tipo"].isin(["CLT", "PJ"])]
raw = raw.dropna(subset=["nome", "tipo"])

# Normalizar nomes para cruzamento
raw["nome_norm"] = raw["nome"].apply(norm)

# Para cada nome normalizado, pegar o tipo mais frequente
tipo_map = (
    raw.groupby("nome_norm")["tipo"]
    .agg(lambda x: x.value_counts().idxmax())
    .to_dict()
)

print(f"Classificações carregadas da fonte: {len(tipo_map)} nomes únicos")

# --- Ler nossa base ---
df = pd.read_excel(PESSOAS_PATH)
df["nome_norm"] = df["Nome"].apply(norm)

# Contar antes
antes = df["Tipo"].value_counts().to_dict()

# Atualizar Tipo onde houver match
matched = 0
changed = 0
for idx, row in df.iterrows():
    novo_tipo = tipo_map.get(row["nome_norm"])
    if novo_tipo:
        matched += 1
        if df.at[idx, "Tipo"] != novo_tipo:
            changed += 1
            df.at[idx, "Tipo"] = novo_tipo

# Remover coluna auxiliar
df.drop(columns=["nome_norm"], inplace=True)

depois = df["Tipo"].value_counts().to_dict()

print(f"\nNomes com match encontrado: {matched} / {len(df)}")
print(f"Registros com tipo corrigido: {changed}")
print(f"\nDistribuição ANTES: {antes}")
print(f"Distribuição DEPOIS: {depois}")

# Salvar
df.to_excel(PESSOAS_PATH, index=False)
print(f"\nArquivo salvo: {PESSOAS_PATH}")

"""Adiciona TODOS os nomes da Mapa Pessoas (CLTs + PJs sheets) ao
pessoal_depara.csv como aliases, com os respectivos CPFs.

Isso resolve casos em que o nome no master (Cadastro Pessoa) eh
diferente do nome na CLT/PJ sheet pra mesma pessoa (CPF).
"""
import sys, io, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

MAPA = "2026 dados/Mapa Pessoas - Mar26.xlsx"
DEPARA = "pessoal_depara.csv"


def norm(s):
    if not s or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().upper()


def main():
    d = pd.read_csv(DEPARA, dtype=str)
    print(f"Depara antes: {len(d)} entries")
    existing_keys = set(zip(d["nome"].fillna("").apply(norm), d["cpf"].fillna("")))

    novos = []

    # CLTs sheet
    clt = pd.read_excel(MAPA, sheet_name="CLTs")
    clt.columns = [str(c).strip() for c in clt.columns]
    clt["cpf_d"] = clt["CPF"].astype(str).str.replace(r"\D", "", regex=True)
    clt = clt[clt["cpf_d"].str.len() >= 11]
    for _, r in clt.iterrows():
        nome = str(r["Nome"]).strip()
        cpf = f"BRCPF{r['cpf_d']}"
        key = (norm(nome), cpf)
        if key in existing_keys: continue
        existing_keys.add(key)
        novos.append({"id": "", "nome": nome, "cpf": cpf})
    print(f"Aliases CLT novos: {sum(1 for x in novos if 'BRCPF' in x['cpf'])}")

    # PJs sheet
    pj = pd.read_excel(MAPA, sheet_name="PJs")
    pj["cpf_d"] = pj["worker_id"].astype(str).str.replace(r"\D", "", regex=True)
    pj = pj[pj["cpf_d"].str.len() >= 11]
    n_clt = len(novos)
    for _, r in pj.iterrows():
        nome = str(r["worker_name"]).strip()
        cpf = f"BRCPF{r['cpf_d']}"
        key = (norm(nome), cpf)
        if key in existing_keys: continue
        existing_keys.add(key)
        novos.append({"id": "", "nome": nome, "cpf": cpf})
    print(f"Aliases PJ novos: {len(novos) - n_clt}")

    if not novos:
        print("Nada a adicionar")
        return

    result = pd.concat([d, pd.DataFrame(novos)], ignore_index=True)
    result.to_csv(DEPARA, index=False)
    print(f"Depara depois: {len(result)} entries (+{len(novos)})")


if __name__ == "__main__":
    main()

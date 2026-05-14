"""Sobe Custo Socios do Mapa Mar26 aba 'Custo Socios':
- Periodos: 2026-01 a 2026-09 (cols H..P, indexes 7..15)
- Cada Categoria (Salario Mensal / Carro / Plano de Saude) vira linha propria
- Coluna E (vertical) e F (em branco) ignoradas
- Apenas Rodrigo Fonseca Burgers: classificacao='custo' (billable)
  Demais: classificacao='despesa' (non-billable)
- DELETE existentes em fonte=Custo Socios + empresa=BR02 FCamara + 2026-01..09
"""
import os, uuid, math
from datetime import datetime, timezone
import pandas as pd, httpx
from _supabase_creds import load_creds

DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(DIR, "2026 dados", "Mapa Pessoas - Mar26.xlsx")
FD = "Mapa Pessoas - Mar26.xlsx"
FONTE = "Custo Socios"
EMPRESA = "BR02 FCamara"
PERIODOS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
            "2026-06", "2026-07", "2026-08", "2026-09"]
MES_COLS = list(range(7, 7 + len(PERIODOS)))  # indexes H..P

ROD = "RODRIGO FONSECA BURGERS"

url, key = load_creds()
H = {"apikey": key, "Authorization": f"Bearer {key}"}
H_DEL = {**H, "Prefer": "return=minimal"}
H_INS = {**H, "Content-Type": "application/json", "Prefer": "return=minimal"}

UPLOAD_ID = str(uuid.uuid4())
UPLOADED_AT = datetime.now(timezone.utc).isoformat()
UPLOADED_BY = "amanda.paula@fcamara.com"


def numv(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    if isinstance(v, str):
        s = v.strip()
        if not s: return None
        try: return float(s.replace(",", "."))
        except: return None
    try: return float(v)
    except: return None


# Le aba
aba_name = "Custo Sócios"
df = pd.read_excel(SRC, sheet_name=aba_name, header=None)
print(f"Aba: {aba_name!r} | Total rows: {len(df)}")

# Dados comecam linha 4 (idx 4). Colunas: B=empresa, C=categoria, D=nome, G=tipo
rows_out = []
for i in range(4, len(df)):
    empresa_raw = df.iat[i, 1]
    if not isinstance(empresa_raw, str) or not empresa_raw.strip():
        continue
    if "FCamara" not in empresa_raw and empresa_raw.strip() != "FCamara":
        # Outras empresas — ignora por ora (so BR02 FCamara)
        continue
    categoria = str(df.iat[i, 2] or "").strip()
    nome = str(df.iat[i, 3] or "").strip()
    tipo_col = str(df.iat[i, 6] or "").strip()  # Custo / Despesa do Excel
    if not categoria or not nome:
        continue

    nome_upper = nome.upper().strip()
    is_rodrigo = nome_upper == ROD
    classif = "custo" if is_rodrigo else "despesa"
    bill = "billable" if is_rodrigo else "non-billable"

    for k, periodo in enumerate(PERIODOS):
        v = numv(df.iat[i, MES_COLS[k]])
        if v is None or v == 0:
            continue
        rows_out.append({
            "upload_id": UPLOAD_ID, "uploaded_at": UPLOADED_AT, "uploaded_by": UPLOADED_BY,
            "fonte": FONTE, "fonte_dados": FD,
            "periodo": periodo,
            "empresa": EMPRESA,
            "nome_pessoa": nome.upper(),
            "agrupador": categoria,
            "tipos": categoria,
            "classificacao": classif,
            "billable_category": bill,
            "tipo_contrato": "Socio",
            "valor": v, "valor_liquido": v, "custo_rateado": v,
            "margem": v,
        })

print(f"Linhas preparadas: {len(rows_out)}")

# Normaliza schema
all_keys = set()
for r in rows_out: all_keys.update(r.keys())
for r in rows_out:
    for k in all_keys: r.setdefault(k, None)

# DELETE existentes
print()
print(f"DELETE existentes (fonte={FONTE} + empresa={EMPRESA} + periodos {PERIODOS[0]}..{PERIODOS[-1]})...")
del_url = (f"{url}/rest/v1/nova_base?fonte=eq.{FONTE}"
           f"&empresa=eq.{EMPRESA}"
           f"&periodo=in.({','.join(PERIODOS)})")
dr = httpx.delete(del_url, headers=H_DEL, timeout=60)
print(f"  status: {dr.status_code}")
if dr.status_code not in (200, 204):
    print(f"  ERRO: {dr.text[:300]}")
    raise SystemExit(1)

# INSERT
print()
print("INSERT em batches de 200...")
BATCH = 200
ins_url = f"{url}/rest/v1/nova_base"
inserted = 0
for i in range(0, len(rows_out), BATCH):
    batch = rows_out[i:i+BATCH]
    r = httpx.post(ins_url, headers=H_INS, json=batch, timeout=60)
    if r.status_code not in (200, 201, 204):
        print(f"  ERRO batch {i}: {r.status_code} | {r.text[:500]}")
        break
    inserted += len(batch)
    print(f"  {inserted}/{len(rows_out)}")

print()
print(f"OK: {inserted} linhas. upload_id={UPLOAD_ID}")
print()
# Resumo por categoria
from collections import Counter
cats = Counter((r["agrupador"], r["classificacao"]) for r in rows_out)
for (cat, cl), n in sorted(cats.items()):
    print(f"  {cat:20} | {cl:10}: {n} linhas")

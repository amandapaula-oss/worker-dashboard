import csv

# ── 1. Build vlookup from clientes.csv ──────────────────────────────────────
clientes_path  = r"C:\Users\amanda.paula\worker-dashboard\backend\clientes.csv"
pv_path        = r"C:\Users\amanda.paula\worker-dashboard\backend\pep_vertical.csv"
margem_path    = r"C:\Users\amanda.paula\worker-dashboard\backend\margem_projetos.csv"

# key: nome_base if present, else nome_cliente  -> vertical (bu field)
vlookup = {}
with open(clientes_path, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        key = (row.get("nome_base") or "").strip() or (row.get("nome_cliente") or "").strip()
        vertical = (row.get("bu") or "").strip()
        if key:
            vlookup[key] = vertical

# ── 2. Load pep_vertical overrides ──────────────────────────────────────────
pep_override = {}
with open(pv_path, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        pep_override[row["pep"].strip()] = row["vertical"].strip()

# ── 3. Load margem_projetos.csv ─────────────────────────────────────────────
Q4_PERIODS = {"2025-10", "2025-11", "2025-12"}

all_peps   = {}   # pep -> nome_cliente (any period)
q4_revenue = {}   # pep -> float sum

with open(margem_path, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        pep    = (row.get("pep") or "").strip()
        period = (row.get("periodo") or "").strip()
        nome   = (row.get("nome_cliente") or "").strip()
        rec    = row.get("receita") or "0"
        try:
            rec_f = float(rec)
        except ValueError:
            rec_f = 0.0

        if pep:
            if pep not in all_peps:
                all_peps[pep] = nome
            if period in Q4_PERIODS:
                q4_revenue[pep] = q4_revenue.get(pep, 0.0) + rec_f

# ── 4. Vertical normalisation map ───────────────────────────────────────────
NORM = {
    "Finance": "Finance & Insurance",
}

def normalise(v):
    return NORM.get(v, v)

def get_current_vertical(pep, nome_cliente):
    if pep in pep_override:
        return normalise(pep_override[pep]), "override"
    v = vlookup.get(nome_cliente, "")
    return normalise(v), "lookup"

# ── 5. Expected list ─────────────────────────────────────────────────────────
EXPECTED_RAW = [
    ("Finance & Insurance", "BR02CLP00004"),
    ("Retail", "BR02CLP00102"),
    ("Others", "BR02LIC0002"),
    ("Logistics", "BR02CLP00045"),
    ("Logistics", "BR02CLP00029"),
    ("Others", "BR02CLP00202"),
    ("Finance & Insurance", "BR02CLP00074"),
    ("Finance & Insurance", "BR02CLP00071"),
    ("Finance & Insurance", "BR02CLP00008"),
    ("Multisector", "BR02CLP00075"),
    ("Finance & Insurance", "BR02CLP00098"),
    ("Finance & Insurance", "BR02CLP00072"),
    ("Retail", "BR02CLP00076"),
    ("Finance & Insurance", "BR02CLP00097"),
    ("Health", "BR02CLP00083"),
    ("Others", "BR02CLP00085"),
    ("Finance & Insurance", "BR02CLP00007"),
    ("Multisector", "BR02CLP00068"),
    ("Multisector", "BR02CLP00061"),
    ("Others", "BR02LIC0003"),
    ("Others", "BR07CLP00058"),
    ("Others", "BR07CLP00119"),
    ("Others", "BR07CLP00069"),
    ("Others", "BR07CLP00068"),
    ("Others", "BR07CLP00070"),
    ("Others", "BR07CLP00123"),
    ("Others", "BR07CLP00106"),
    ("Others", "BR07CLP00035"),
    ("Others", "BR07CLP00033"),
    ("Others", "BR07CLP00043"),
    ("Others", "BR07CLP00047"),
    ("Others", "BR07CLP00049"),
    ("Others", "BR07CLP00018"),
    ("Others", "BR07CLP00050"),
    ("Others", "BR07CLP00009"),
    ("Others", "BR07CLP00048"),
    ("Others", "BR07CLP00011"),
    ("Others", "BR07CLP00020"),
    ("Others", "BR08CLP00003"),
    ("Logistics", "BR02CLP00112"),
    ("Others", "BR07CLP00012"),
    ("Others", "BR07CLP00003"),
    ("Multisector", "BR08CLP00017"),
    ("Finance & Insurance", "BR02CLP00005"),
    ("Others", "BR07CLP00061"),
    ("Others", "BR07CLP00062"),
    ("Others", "BR07CLP00063"),
    ("Retail", "BR02CLP00042"),
    ("Others", "BR08CLP00012"),
    ("Others", "BR08CLP00009"),
    ("Others", "BR07CLP00087"),
    ("Retail", "BR02CLP00084"),
    ("Retail", "BR02CLP000250"),
    ("Multisector", "BR02CLP00095"),
    ("Others", "BR07CLP00022"),
    ("Others", "BR08CLP00004"),
    ("Others", "BR02CLP00122"),
    ("Health", "BR02CLP00041"),
    ("Multisector", "BR02CLP000120"),
    ("Others", "BR07CLP00002"),
    ("Others", "BR07CLP00121"),
    ("Others", "BR08CLP00014"),
    ("Finance & Insurance", "BR02CLP00129"),
    ("Logistics", "BR02CLP00106"),
    ("Multisector", "BR02CLP00092"),
    ("Multisector", "BR02CLP000100"),
    ("Logistics", "BR02CLP00037"),
    ("Logistics", "BR02CLP00028"),
    ("Health", "BR02CLP00022"),
    ("Logistics", "BR02CLP00113"),
    ("Others", "BR07CLP00126"),
    ("Others", "BR07CLP00141"),
    ("Others", "BR07CLP00027"),
    ("Others", "BR07CLP00025"),
    ("Others", "BR07CLP00026"),
    ("Others", "BR07CLP00051"),
    ("Others", "BR07CLP00052"),
    ("Finance & Insurance", "BR02CLP00018"),
    ("Health", "BR07CLP00004"),
    ("Others", "BR07CLP00001"),
    ("Finance & Insurance", "BR09CLP00002"),
    ("Retail", "BR02CLP00003"),
    ("Health", "BR02CLP00123"),
    ("Others", "BR02CLP000303"),
    ("Others", "BR07CLP00130"),
    ("Retail", "BR02CLP00107"),
    ("Multisector", "BR09CLP00006"),
    ("Multisector", "BR09CLP00001"),
    ("Finance & Insurance", "BR09CLP00004"),
    ("Others", "BR07CLP00029"),
    ("Others", "BR07CLP00059"),
    ("Finance & Insurance", "BR09CLP00003"),
    ("Health", "BR02CLP00021"),
    ("Health", "BR08CLP000015"),
    ("Others", "BR07CLP00060"),
    ("Multisector", "BR02CLP00059"),
    ("Others", "BR07CLP00096"),
    ("Multisector", "BR02CLP00118"),
    ("Others", "BR08CLP00015"),
    ("Health", "BR02CLP00026"),
    ("Health", "BR02CLP000211"),
    ("Health", "BR02CLP000210"),
    ("Finance & Insurance", "BR02CLP000122"),
    ("Multisector", "BR02CLP00149"),
    ("Logistics", "BR02CLP00250"),
    ("Retail", "BR02CLP006849"),
    ("Others", "BR07CLP00135"),
    ("Finance & Insurance", "BR07CLP00024"),
    ("Others", "BR07CLP00046"),
    ("Retail", "BR02CLP00039"),
    ("Finance & Insurance", "BR02CLP00006"),
    ("Health", "BR02CLP00050"),
    ("Finance & Insurance", "BR02CLP00015"),
    ("Others", "BR07CLP00100"),
    ("Others", "BR07CLP00101"),
    ("Others", "BR07CLP00055"),
    ("Finance & Insurance", "BR09CLP00005"),
    ("Health", "BR02CLP00044"),
    ("Health", "BR02CLP000148"),
    ("Others", "BR07CLP001140"),
    ("Others", "BR07CLP00089"),
    ("Finance & Insurance", "BR02CLP00019"),
    ("Others", "BR07CLP00140"),
    ("Others", "BR08CLP00018"),
    ("Health", "BR02CLP000512"),
    ("Logistics", "BR02CLP00030"),
    ("Logistics", "BR02CLP00051"),
    ("Others", "BR07CLP00021"),
    ("Health", "BR02CLP000473"),
    ("Others", "BR02CLP00200"),
    ("Others", "BR02CLP00201"),
    ("Retail", "BR02CLP00052"),
    ("Others", "BR07CLP00054"),
    ("Multisector", "BR02CLP00055"),
    ("Multisector", "BR02CLP000545"),
    ("Others", "BR08CLP00019"),
    ("Health", "BR02CLP000234"),
    ("Health", "BR02CLP000312"),
    ("Others", "BR02CLP000567"),
    ("Others", "BR07CLP00134"),
    ("Others", "BR08CLP000405"),
    ("Others", "BR07CLP00019"),
    ("Retail", "BR02CLP00025"),
    ("Finance & Insurance", "BR02CLP000092"),
    ("Retail", "BR02CLP000125"),
    ("Finance & Insurance", "BR02CLP00073"),
    ("Finance & Insurance", "BR02CLP00115"),
    ("Retail", "BR02CLP00077"),
    ("Multisector", "BR02CLP001150"),
    ("Multisector", "BR02CLP00131"),
    ("Logistics", "BR02CLP00056"),
    ("Multisector", "BR02CLP00049"),
    ("Retail", "BR02CLP000130"),
    ("Others", "BR02CLP000310"),
    ("Logistics", "BR02CLP00032"),
    ("Logistics", "BR02CLP00033"),
    ("Logistics", "BR02CLP000110"),
    ("Health", "BR02CLP000141"),
    ("Multisector", "BR02CLP000301"),
    ("Multisector", "BR02CLP000311"),
    ("Multisector", "BR02CLP001120"),
    ("Others", "BR02CLP00040"),
    ("Finance & Insurance", "BR02CLP00100"),
    ("Logistics", "BR02CLP00036"),
    ("Health", "BR02CLP00086"),
    ("Retail", "BR02CLP000190"),
    ("Logistics", "BR02CLP00035"),
    ("Logistics", "BR02CLP00136"),
    ("Multisector", "BR02CLP00141"),
    ("Retail", "BR02CLP000600"),
    ("Health", "BR02CLP00549"),
    ("Multisector", "BR02CLP00120"),
    ("Multisector", "BR02CLP000117"),
    ("Others", "BR07CLP00057"),
    ("Multisector", "BR09CLP00013"),
    ("Others", "BR07CLP00132"),
    ("Multisector", "BR09CLP00008"),
    ("Logistics", "BR02CLP00046"),
    ("Others", "BR07CLP00013"),
    ("Retail", "BR07CLP00094"),
    ("Others", "BR07CLP00010"),
    ("Others", "BR07CLP00125"),
    ("Others", "BR07CLP00111"),
    ("Others", "BR07CLP00081"),
    ("Others", "BR07CLP133"),
    ("Others", "BR07CLP00127"),
    ("Others", "BR07CLP00075"),
    ("Others", "BR07CLP00142"),
    ("Others", "BR07CLP00139"),
    ("Others", "BR07CLP00137"),
    ("Others", "BR07CLP00124"),
    ("Others", "BR07CLP00077"),
    ("Others", "BR07CLP00006"),
    ("Others", "BR07CLP00084"),
    ("Others", "BR07CLP00200"),
    ("Others", "BR07CLP00007"),
    ("Others", "BR07CLP00032"),
    ("Others", "BR07CLP00034"),
    ("Others", "BR07CLP00071"),
    ("Others", "BR07CLP00074"),
    ("Others", "BR07CLP00080"),
    ("Others", "BR07CLP00082"),
    ("Others", "BR07CLP00083"),
    ("Logistics", "BR07CLP00092"),
    ("Others", "BR07CLP00097"),
    ("Others", "BR07CLP00099"),
    ("Others", "BR07CLP00104"),
    ("Others", "BR07CLP00108"),
    ("Others", "BR07CLP00128"),
    ("Others", "BR07CLP00133"),
    ("Others", "BR07CLP00136"),
    ("Others", "BR07CLP00138"),
    ("Health", "BR09CLP00010"),
    ("Health", "BR02CLP00089"),
    ("Retail", "BR02CLP00078"),
    ("Retail", "BR02CLP00099"),
    ("Health", "BR02CLP00081"),
    ("Retail", "BR02CLP00080"),
    ("Retail", "BR02CLP0000200"),
    ("Health", "BR09CLP00156"),
    ("Finance & Insurance", "BR02CLP000345"),
    ("Multisector", "BR02CLP00124"),
    ("Logistics", "BR02CLP00109"),
    ("Others", "BR02CLP00145"),
    ("Others", "BR07LIC0005"),
    ("Health", "BRO2CLP000715"),
    ("Health", "BR02CLP000432"),
    ("Health", "BR02CLP00126"),
    ("Retail", "BR02CLP00132"),
    ("Health", "BR02CLP00121"),
    ("Health", "BR02CLP000914"),
    ("Health", "BR02CLP000116"),
    ("Logistics", "BR02CLP000114"),
    ("Multisector", "BR02CLP000140"),
    ("Others", "BR02CLP00065"),
    ("Others", "BR07CLP00144"),
    ("Multisector", "BR02CLP00067"),
    ("Multisector", "BR02CLP00096"),
    ("Others", "BR02CLP00240"),
    ("Others", "BR07CLP00148"),
    ("Others", "BR08CLP00042"),
    ("Others", "BR08CLP000029"),
    ("Others", "BR09CLP00158"),
    ("Multisector", "BR02CLP000101"),
    ("Others", "BR07CLP00098"),
    ("Multisector", "BR08CLP00002"),
    ("Others", "BR07CLP00143"),
    ("Others", "BR07CLP00147"),
    ("Others", "BR0CLP00143"),
    ("Others", "BR07CLP00090"),
    ("Health", "BR02CLP000808"),
    ("Finance & Insurance", "BR02CLP00016"),
    ("Logistics", "BR02CLP00128"),
    ("Logistics", "BR02CLP00053"),
    ("Multisector", "BR02CLP000123"),
    ("Finance & Insurance", "BR02CLP00064"),
    ("Multisector", "BR02CLP00066"),
    ("Others", "BR02CLP00105"),
    ("Others", "BR02CLP00114"),
    ("Finance & Insurance", "BR02CLP00163"),
    ("Others", "BR02CLP00162"),
    ("Others", "BR02CLP00133"),
    ("Others", "CLP00"),
    ("Retail", "BR02CLP000816"),
    ("Multisector", "BR02CLP000149"),
    ("Finance & Insurance", "BR02CLP000150"),
    ("Finance & Insurance", "BR02CLP00174"),
    ("Multisector", "BR02CLP000183"),
    ("Finance & Insurance", "BR02CLP000151"),
    ("Multisector", "BR02CLP000144"),
    ("Others", "BR07CLP00152"),
    ("Others", "BR07CLP00153"),
    ("Others", "BR07CLP00154"),
    ("Others", "BR07CLP00157"),
    ("Others", "BR07CLP00150"),
    ("Others", "BR07CLP00155"),
    ("Others", "BR07CLP00156"),
    ("Others", "BR07CLP00159"),
    ("Others", "BR07CLP00149"),
    ("Others", "BR02LIC0004"),
    ("Others", "BR07CLP00086"),
    ("Others", "BR07CLP00085"),
    ("Others", "BR07CLP00105"),
    ("Others", "BR07CLP00076"),
    ("Others", "BR07CLP00151"),
    ("Others", "BR07CLP00045"),
    ("Others", "BR07CLP00095"),
]

expected_list = [(pep, exp_vert) for exp_vert, pep in EXPECTED_RAW]

# ── 6. Evaluate ──────────────────────────────────────────────────────────────
mismatches   = []
not_in_sap   = []
ok_count     = 0

for pep, exp_vert in expected_list:
    if pep not in all_peps:
        not_in_sap.append((pep, exp_vert))
        continue

    nome_cli = all_peps[pep]
    cur_vert, _ = get_current_vertical(pep, nome_cli)
    q4_rev = q4_revenue.get(pep, 0.0)

    if cur_vert == exp_vert:
        ok_count += 1
    else:
        mismatches.append({
            "pep":          pep,
            "expected":     exp_vert,
            "current":      cur_vert,
            "nome_cliente": nome_cli,
            "q4_revenue":   q4_rev,
        })

# ── 7. Print results ─────────────────────────────────────────────────────────
print("=" * 110)
print("SECTION 1 -- MISMATCHES")
print("=" * 110)
if mismatches:
    print(f"{'PEP':<22} {'EXPECTED':<22} {'CURRENT':<22} {'Q4 REC':>15}  NOME_CLIENTE")
    print("-" * 110)
    for m in mismatches:
        print(f"{m['pep']:<22} {m['expected']:<22} {m['current']:<22} {m['q4_revenue']:>15,.0f}  {m['nome_cliente']}")
else:
    print("(none)")

print()
print("=" * 110)
print("SECTION 2 -- NOT IN SAP")
print("=" * 110)
if not_in_sap:
    for pep, exp in not_in_sap:
        print(f"  {pep}  (expected: {exp})")
else:
    print("(none)")

print()
print("=" * 110)
print("SECTION 3 -- SUMMARY")
print("=" * 110)
total = len(expected_list)
print(f"  Total PEPs in expected list : {total}")
print(f"  OK (match)                  : {ok_count}")
print(f"  MISMATCH                    : {len(mismatches)}")
print(f"  NOT IN SAP                  : {len(not_in_sap)}")

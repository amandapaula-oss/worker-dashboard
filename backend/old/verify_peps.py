import csv, os

def norm_vert(v):
    v = v.strip()
    if v in ('Finance & Insurance', 'Finance & Insurance'): return 'Finance'
    if v == 'Logistics': return 'Grupo Mult'
    return v

# vlookup clientes.csv
vlookup = {}
with open('clientes.csv', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        bu = (row.get('bu') or '').strip()
        nb = (row.get('nome_base') or '').strip().upper()
        nc = (row.get('nome_cliente') or '').strip().upper()
        if nb: vlookup[nb] = bu
        if nc and nc not in vlookup: vlookup[nc] = bu

# pep_vertical override
pv_map = {}
with open('pep_vertical.csv', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        pv_map[row['pep'].strip()] = row['vertical'].strip()

# margem_projetos
Q4 = {'2025-10', '2025-11', '2025-12'}
all_peps = {}
q4_rec   = {}
with open('margem_projetos.csv', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        pep  = (row.get('pep') or '').strip()
        nome = (row.get('nome_cliente') or '').strip()
        per  = (row.get('periodo') or '').strip()
        try:    rec = float(row.get('receita') or 0)
        except: rec = 0.0
        if pep:
            all_peps.setdefault(pep, nome)
            if per in Q4:
                q4_rec[pep] = q4_rec.get(pep, 0.0) + rec

def current_vert(pep, nome):
    if pep in pv_map: return pv_map[pep]
    return vlookup.get(nome.upper(), '')

expected_raw = [
    ("Finance & Insurance", "BR02CLP00004"), ("Retail", "BR02CLP00102"), ("Others", "BR02LIC0002"),
    ("Logistics", "BR02CLP00045"), ("Logistics", "BR02CLP00029"), ("Others", "BR02CLP00202"),
    ("Finance & Insurance", "BR02CLP00074"), ("Finance & Insurance", "BR02CLP00071"),
    ("Finance & Insurance", "BR02CLP00008"), ("Multisector", "BR02CLP00075"),
    ("Finance & Insurance", "BR02CLP00098"), ("Finance & Insurance", "BR02CLP00072"),
    ("Retail", "BR02CLP00076"), ("Finance & Insurance", "BR02CLP00097"),
    ("Health", "BR02CLP00083"), ("Others", "BR02CLP00085"),
    ("Finance & Insurance", "BR02CLP00007"), ("Multisector", "BR02CLP00068"),
    ("Multisector", "BR02CLP00061"), ("Others", "BR02LIC0003"),
    ("Others", "BR07CLP00058"), ("Others", "BR07CLP00119"), ("Others", "BR07CLP00069"),
    ("Others", "BR07CLP00068"), ("Others", "BR07CLP00070"), ("Others", "BR07CLP00123"),
    ("Others", "BR07CLP00106"), ("Others", "BR07CLP00035"), ("Others", "BR07CLP00033"),
    ("Others", "BR07CLP00043"), ("Others", "BR07CLP00047"), ("Others", "BR07CLP00049"),
    ("Others", "BR07CLP00018"), ("Others", "BR07CLP00050"), ("Others", "BR07CLP00009"),
    ("Others", "BR07CLP00048"), ("Others", "BR07CLP00011"), ("Others", "BR07CLP00020"),
    ("Others", "BR08CLP00003"), ("Logistics", "BR02CLP00112"), ("Others", "BR07CLP00012"),
    ("Others", "BR07CLP00003"), ("Multisector", "BR08CLP00017"),
    ("Finance & Insurance", "BR02CLP00005"), ("Others", "BR07CLP00061"),
    ("Others", "BR07CLP00062"), ("Others", "BR07CLP00063"), ("Retail", "BR02CLP00042"),
    ("Others", "BR08CLP00012"), ("Others", "BR08CLP00009"), ("Others", "BR07CLP00087"),
    ("Retail", "BR02CLP00084"), ("Retail", "BR02CLP000250"), ("Multisector", "BR02CLP00095"),
    ("Others", "BR07CLP00022"), ("Others", "BR08CLP00004"), ("Others", "BR02CLP00122"),
    ("Health", "BR02CLP00041"), ("Multisector", "BR02CLP000120"), ("Others", "BR07CLP00002"),
    ("Others", "BR07CLP00121"), ("Others", "BR08CLP00014"),
    ("Finance & Insurance", "BR02CLP00129"), ("Logistics", "BR02CLP00106"),
    ("Multisector", "BR02CLP00092"), ("Multisector", "BR02CLP000100"),
    ("Logistics", "BR02CLP00037"), ("Logistics", "BR02CLP00028"),
    ("Health", "BR02CLP00022"), ("Logistics", "BR02CLP00113"),
    ("Others", "BR07CLP00126"), ("Others", "BR07CLP00141"), ("Others", "BR07CLP00027"),
    ("Others", "BR07CLP00025"), ("Others", "BR07CLP00026"), ("Others", "BR07CLP00051"),
    ("Others", "BR07CLP00052"), ("Finance & Insurance", "BR02CLP00018"),
    ("Health", "BR07CLP00004"), ("Others", "BR07CLP00001"),
    ("Finance & Insurance", "BR09CLP00002"), ("Retail", "BR02CLP00003"),
    ("Health", "BR02CLP00123"), ("Others", "BR02CLP000303"), ("Others", "BR07CLP00130"),
    ("Retail", "BR02CLP00107"), ("Multisector", "BR09CLP00006"), ("Multisector", "BR09CLP00001"),
    ("Finance & Insurance", "BR09CLP00004"), ("Others", "BR07CLP00029"),
    ("Others", "BR07CLP00059"), ("Finance & Insurance", "BR09CLP00003"),
    ("Health", "BR02CLP00021"), ("Health", "BR08CLP000015"), ("Others", "BR07CLP00060"),
    ("Multisector", "BR02CLP00059"), ("Others", "BR07CLP00096"),
    ("Multisector", "BR02CLP00118"), ("Others", "BR08CLP00015"),
    ("Health", "BR02CLP00026"), ("Health", "BR02CLP000211"), ("Health", "BR02CLP000210"),
    ("Finance & Insurance", "BR02CLP000122"), ("Multisector", "BR02CLP00149"),
    ("Logistics", "BR02CLP00250"), ("Retail", "BR02CLP006849"),
    ("Others", "BR07CLP00135"), ("Finance & Insurance", "BR07CLP00024"),
    ("Others", "BR07CLP00046"), ("Retail", "BR02CLP00039"),
    ("Finance & Insurance", "BR02CLP00006"), ("Health", "BR02CLP00050"),
    ("Finance & Insurance", "BR02CLP00015"), ("Others", "BR07CLP00100"),
    ("Others", "BR07CLP00101"), ("Others", "BR07CLP00055"),
    ("Finance & Insurance", "BR09CLP00005"), ("Health", "BR02CLP00044"),
    ("Health", "BR02CLP000148"), ("Others", "BR07CLP001140"), ("Others", "BR07CLP00089"),
    ("Finance & Insurance", "BR02CLP00019"), ("Others", "BR07CLP00140"),
    ("Others", "BR08CLP00018"), ("Health", "BR02CLP000512"),
    ("Logistics", "BR02CLP00030"), ("Logistics", "BR02CLP00051"),
    ("Others", "BR07CLP00021"), ("Health", "BR02CLP000473"),
    ("Others", "BR02CLP00200"), ("Others", "BR02CLP00201"),
    ("Retail", "BR02CLP00052"), ("Others", "BR07CLP00054"),
    ("Multisector", "BR02CLP00055"), ("Multisector", "BR02CLP000545"),
    ("Others", "BR08CLP00019"), ("Health", "BR02CLP000234"), ("Health", "BR02CLP000312"),
    ("Others", "BR02CLP000567"), ("Others", "BR07CLP00134"), ("Others", "BR08CLP000405"),
    ("Others", "BR07CLP00019"), ("Retail", "BR02CLP00025"),
    ("Finance & Insurance", "BR02CLP000092"), ("Retail", "BR02CLP000125"),
    ("Finance & Insurance", "BR02CLP00073"), ("Finance & Insurance", "BR02CLP00115"),
    ("Retail", "BR02CLP00077"), ("Multisector", "BR02CLP001150"),
    ("Multisector", "BR02CLP00131"), ("Logistics", "BR02CLP00056"),
    ("Multisector", "BR02CLP00049"), ("Retail", "BR02CLP000130"),
    ("Others", "BR02CLP000310"), ("Logistics", "BR02CLP00032"),
    ("Logistics", "BR02CLP00033"), ("Logistics", "BR02CLP000110"),
    ("Health", "BR02CLP000141"), ("Multisector", "BR02CLP000301"),
    ("Multisector", "BR02CLP000311"), ("Multisector", "BR02CLP001120"),
    ("Others", "BR02CLP00040"), ("Finance & Insurance", "BR02CLP00100"),
    ("Logistics", "BR02CLP00036"), ("Health", "BR02CLP00086"),
    ("Retail", "BR02CLP000190"), ("Logistics", "BR02CLP00035"),
    ("Logistics", "BR02CLP00136"), ("Multisector", "BR02CLP00141"),
    ("Retail", "BR02CLP000600"), ("Health", "BR02CLP00549"),
    ("Multisector", "BR02CLP00120"), ("Multisector", "BR02CLP000117"),
    ("Others", "BR07CLP00057"), ("Multisector", "BR09CLP00013"),
    ("Others", "BR07CLP00132"), ("Multisector", "BR09CLP00008"),
    ("Logistics", "BR02CLP00046"), ("Others", "BR07CLP00013"),
    ("Retail", "BR07CLP00094"), ("Others", "BR07CLP00010"), ("Others", "BR07CLP00125"),
    ("Others", "BR07CLP00111"), ("Others", "BR07CLP00081"), ("Others", "BR07CLP133"),
    ("Others", "BR07CLP00127"), ("Others", "BR07CLP00075"), ("Others", "BR07CLP00142"),
    ("Others", "BR07CLP00139"), ("Others", "BR07CLP00137"), ("Others", "BR07CLP00124"),
    ("Others", "BR07CLP00077"), ("Others", "BR07CLP00006"), ("Others", "BR07CLP00084"),
    ("Others", "BR07CLP00200"), ("Others", "BR07CLP00007"), ("Others", "BR07CLP00032"),
    ("Others", "BR07CLP00034"), ("Others", "BR07CLP00071"), ("Others", "BR07CLP00074"),
    ("Others", "BR07CLP00080"), ("Others", "BR07CLP00082"), ("Others", "BR07CLP00083"),
    ("Logistics", "BR07CLP00092"), ("Others", "BR07CLP00097"), ("Others", "BR07CLP00099"),
    ("Others", "BR07CLP00104"), ("Others", "BR07CLP00108"), ("Others", "BR07CLP00128"),
    ("Others", "BR07CLP00133"), ("Others", "BR07CLP00136"), ("Others", "BR07CLP00138"),
    ("Health", "BR09CLP00010"), ("Health", "BR02CLP00089"), ("Retail", "BR02CLP00078"),
    ("Retail", "BR02CLP00099"), ("Health", "BR02CLP00081"), ("Retail", "BR02CLP00080"),
    ("Retail", "BR02CLP0000200"), ("Health", "BR09CLP00156"),
    ("Finance & Insurance", "BR02CLP000345"), ("Multisector", "BR02CLP00124"),
    ("Logistics", "BR02CLP00109"), ("Others", "BR02CLP00145"), ("Others", "BR07LIC0005"),
    ("Health", "BRO2CLP000715"), ("Health", "BR02CLP000432"), ("Health", "BR02CLP00126"),
    ("Retail", "BR02CLP00132"), ("Health", "BR02CLP00121"), ("Health", "BR02CLP000914"),
    ("Health", "BR02CLP000116"), ("Logistics", "BR02CLP000114"),
    ("Multisector", "BR02CLP000140"), ("Others", "BR02CLP00065"),
    ("Others", "BR07CLP00144"), ("Multisector", "BR02CLP00067"),
    ("Multisector", "BR02CLP00096"), ("Others", "BR02CLP00240"),
    ("Others", "BR07CLP00148"), ("Others", "BR08CLP00042"), ("Others", "BR08CLP000029"),
    ("Others", "BR09CLP00158"), ("Multisector", "BR02CLP000101"),
    ("Others", "BR07CLP00098"), ("Multisector", "BR08CLP00002"),
    ("Others", "BR07CLP00143"), ("Others", "BR07CLP00147"), ("Others", "BR0CLP00143"),
    ("Others", "BR07CLP00090"), ("Health", "BR02CLP000808"),
    ("Finance & Insurance", "BR02CLP00016"), ("Logistics", "BR02CLP00128"),
    ("Logistics", "BR02CLP00053"), ("Multisector", "BR02CLP000123"),
    ("Finance & Insurance", "BR02CLP00064"), ("Multisector", "BR02CLP00066"),
    ("Others", "BR02CLP00105"), ("Others", "BR02CLP00114"),
    ("Finance & Insurance", "BR02CLP00163"), ("Others", "BR02CLP00162"),
    ("Others", "BR02CLP00133"), ("Others", "CLP00"), ("Retail", "BR02CLP000816"),
    ("Multisector", "BR02CLP000149"), ("Finance & Insurance", "BR02CLP000150"),
    ("Finance & Insurance", "BR02CLP00174"), ("Multisector", "BR02CLP000183"),
    ("Finance & Insurance", "BR02CLP000151"), ("Multisector", "BR02CLP000144"),
    ("Others", "BR07CLP00152"), ("Others", "BR07CLP00153"), ("Others", "BR07CLP00154"),
    ("Others", "BR07CLP00157"), ("Others", "BR07CLP00150"), ("Others", "BR07CLP00155"),
    ("Others", "BR07CLP00156"), ("Others", "BR07CLP00159"), ("Others", "BR07CLP00149"),
    ("Others", "BR02LIC0004"), ("Others", "BR07CLP00086"), ("Others", "BR07CLP00085"),
    ("Others", "BR07CLP00105"), ("Others", "BR07CLP00076"), ("Others", "BR07CLP00151"),
    ("Others", "BR07CLP00045"), ("Others", "BR07CLP00095"),
]

expected = {pep: norm_vert(v) for v, pep in expected_raw}

ok, mismatches, not_in_sap = [], [], []
for pep, exp in sorted(expected.items()):
    nome = all_peps.get(pep, '')
    if not nome:
        not_in_sap.append(pep)
        continue
    cur = current_vert(pep, nome)
    rec = q4_rec.get(pep, 0.0)
    if cur == exp:
        ok.append(pep)
    else:
        mismatches.append((pep, exp, cur if cur else '(vazio)', nome, rec))

real_conflicts = [(p,e,c,n,r) for p,e,c,n,r in mismatches if c != '(vazio)']
empty_vert     = [(p,e,c,n,r) for p,e,c,n,r in mismatches if c == '(vazio)']

print(f"OK: {len(ok)}  |  DIVERGENCIAS: {len(mismatches)}  |  NAO NO SAP: {len(not_in_sap)}")
print()
print(f"=== CONFLITOS REAIS (vertical preenchida mas errada): {len(real_conflicts)} ===")
print(f"{'PEP':<20} {'ESPERADO':<14} {'ATUAL':<16} {'CLIENTE':<38} {'REC Q4':>12}")
print('-'*106)
for p,e,c,n,r in sorted(real_conflicts, key=lambda x: -x[4]):
    print(f"{p:<20} {e:<14} {c:<16} {n[:38]:<38} {r:>12,.0f}")

print()
print(f"=== SEM VERTICAL (precisam entrar no pep_vertical.csv): {len(empty_vert)} PEPs com receita Q4 > 0 ===")
print(f"{'PEP':<20} {'ESPERADO':<14} {'CLIENTE':<45} {'REC Q4':>12}")
print('-'*96)
for p,e,c,n,r in sorted(empty_vert, key=lambda x: -x[4]):
    if r > 0:
        print(f"{p:<20} {e:<14} {n[:45]:<45} {r:>12,.0f}")

print()
print(f"=== NAO NO SAP: {len(not_in_sap)} ===")
for p in sorted(not_in_sap): print(f"  {p}")

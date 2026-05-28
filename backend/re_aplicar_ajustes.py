"""Re-aplica TODOS os ajustes manuais documentados em AJUSTES_MANUAIS.txt.

Idempotente: pode rodar varias vezes sem efeito colateral.

USO:
    Rode este script DEPOIS de cada upload novo de PJs/CLTs/etc.
    Ele detecta o estado atual e aplica os ajustes que estiverem faltando.

    python re_aplicar_ajustes.py            # dry-run (so reporta)
    python re_aplicar_ajustes.py --apply    # aplica de fato
"""
import sys, io, urllib.parse, unicodedata, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx
import pandas as pd
from _supabase_creds import load_creds

URL, KEY = load_creds()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
HP = {**H, "Content-Type": "application/json", "Prefer": "return=representation"}
APPLY = "--apply" in sys.argv


def patch(filter_q, body, descricao):
    """PATCH com filtro PostgREST. Retorna numero de linhas atualizadas."""
    method = httpx.patch if APPLY else httpx.get
    if APPLY:
        r = httpx.patch(f"{URL}/rest/v1/nova_base?{filter_q}", headers=HP, json=body, timeout=60)
        n = len(r.json()) if r.status_code < 300 else 0
        if r.status_code >= 300:
            print(f"  ERRO: {r.status_code} {r.text[:200]}")
    else:
        # Conta linhas que precisariam mudar (estado atual != alvo).
        # Constroi filtro inverso pra saber qual NAO esta no alvo ainda.
        r = httpx.get(f"{URL}/rest/v1/nova_base?{filter_q}&select=id", headers={**H, "Prefer": "count=exact"}, timeout=60)
        n = len(r.json()) if r.status_code < 300 else 0
    print(f"  {descricao}: {n} linhas{' atualizadas' if APPLY else ' candidatas'}")
    return n


def regra_pep_almap():
    """1.1 - PEP BR02CLP000310 -> cliente ALMAP"""
    print("\n[1.1] PEP BR02CLP000310 -> ALMAP")
    patch("pep_base=eq.BR02CLP000310&nome_cliente=neq.ALMAP",
          {"nome_cliente": "ALMAP"},
          "PEP BR02CLP000310")


def regra_leonardo_almap():
    """1.2 - Leonardo Souza de Freitas (CLTs) -> ALMAP"""
    print("\n[1.2] LEONARDO SOUZA DE FREITAS (CLTs) -> ALMAP")
    patch("fonte=eq.CLTs&nome_pessoa=ilike.*LEONARDO*SOUZA*DE*FREITAS*&nome_cliente=neq.ALMAP",
          {"nome_cliente": "ALMAP"},
          "Leonardo CLTs")


def regra_tatiane_transunion():
    """1.3 - TATIANE CORREA CAMILO -> TransUnion / BU Finance (todas as linhas)"""
    print("\n[1.3] TATIANE CORREA CAMILO -> TransUnion + BU Finance")
    patch("nome_pessoa=ilike.*atiane*camilo*&nome_cliente=neq.TransUnion",
          {"nome_cliente": "TransUnion", "vertical": "BU Finance"},
          "Tatiane Camilo")


def regra_transunion_bu_finance():
    """1.3b - Qualquer cliente TransUnion (qualquer grafia) -> BU Finance"""
    print("\n[1.3b] TransUnion (todas grafias) -> BU Finance")
    patch("nome_cliente=ilike.*TRANSUNION*&or=(vertical.is.null,vertical.neq.BU Finance)",
          {"vertical": "BU Finance"},
          "TransUnion BU Finance")


def regra_fernando_boldrin_klabin():
    """1.4 - Fernando Henrique Dourado Boldrin (PJ): CBMM -> KLABIN S.A."""
    print("\n[1.4] Fernando Boldrin (PJ CBMM) -> Klabin")
    patch("fonte=eq.PJs&nome_pessoa=ilike.*FERNANDO*HENRIQUE*DOURADO*BOLDRIN*&nome_cliente=ilike.*METALURGIA*",
          {"nome_cliente": "KLABIN S.A.", "vertical": "BU Logistics"},
          "Fernando Boldrin")


def regra_it_solution_poliedro():
    """1.5 - IT SOLUTION SOLUCOES TECNOLOGICAS (PJ): CBMM -> POLIEDRO SISTEMA DE ENSINO LTDA"""
    print("\n[1.5] IT Solution (PJ CBMM) -> Poliedro")
    patch("fonte=eq.PJs&nome_pessoa=ilike.*IT*SOLUTION*SOLUCOES*&nome_cliente=ilike.*METALURGIA*",
          {"nome_cliente": "POLIEDRO SISTEMA DE ENSINO LTDA", "vertical": "BU Logistics"},
          "IT Solution")


def regra_no_hierarquia_codes():
    """2.2 - Adiciona codigo DC nas categorias com so rotulo"""
    print("\n[2.2] no_hierarquia: rotulo -> codigo DC")
    MAP = {
        "E-commerce": "DC004 E-commerce",
        "FC Consult. B. Sales": "DC040 FC Consult. B. Sales",
        "FC Consult. New Rev": "DC029 FC Consult. New Rev",
        "FC Consult. New Ver": "DC029 FC Consult. New Rev",
        "Imagine": "DC007 Imagine",
        "Open-X": "DC005 Open-X",
        "Consulting (Play)": "DC029 FC Consult. New Rev",
        "Vertical": "DC002 Dedicated Teams",
        "Squads": "DC001 Squads",
        "Dedicated Teams": "DC002 Dedicated Teams",
        "Business Unit": "DC037 Business Unit",
        "Hyperautomation": "DC008 Hyperautomation",
        "Licensing Hyper": "DC009 Licensing Hyper",
    }
    for old, new in MAP.items():
        q = urllib.parse.quote(old, safe="")
        patch(f"no_hierarquia=eq.{q}", {"no_hierarquia": new}, f"{old} -> {new}")


def regra_orange_no_hierarquia():
    """2.3 - Linhas Base Orange sem no_hierarquia: deriva via PEP lookup
    (no_hierarquia dominante do mesmo PEP em outras fontes); default DC002."""
    print("\n[2.3] Orange sem no_hierarquia (via PEP lookup + default DC002)")
    if not APPLY:
        # Conta candidatas
        r = httpx.get(f"{URL}/rest/v1/nova_base?select=id&fonte=eq.base Orange&or=(no_hierarquia.is.null,no_hierarquia.eq.)&limit=1", headers={**H, "Prefer": "count=exact"})
        cr = r.headers.get('content-range', '0/0')
        print(f"  Orange sem no_hierarquia: {cr}")
        return
    import collections as _co
    # Mapa PEP -> DC dominante (nao-Orange)
    allr = []; off = 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/nova_base?select=pep_base,no_hierarquia&fonte=neq.base Orange&offset={off}&limit=1000", headers=H, timeout=60)
        d = r.json()
        if not isinstance(d, list): break
        allr += d
        if len(d) < 1000: break
        off += 1000
    pep_map = _co.defaultdict(_co.Counter)
    for x in allr:
        p = str(x.get("pep_base") or "").strip()
        n = str(x.get("no_hierarquia") or "").strip()
        if p and n and not n.lower().startswith("vertical"):
            pep_map[p][n] += 1
    pep_dc = {p: c.most_common(1)[0][0] for p, c in pep_map.items()}

    # Orange sem no_hierarquia
    oranges = []; off = 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/nova_base?select=id,pep_base,no_hierarquia&fonte=eq.base Orange&offset={off}&limit=1000", headers=H, timeout=60)
        d = r.json()
        if not isinstance(d, list): break
        oranges += d
        if len(d) < 1000: break
        off += 1000
    sem = [x for x in oranges if not (x.get("no_hierarquia") or "").strip()]
    if not sem:
        print("  nada a atualizar")
        return
    upd = _co.defaultdict(list)
    for x in sem:
        p = str(x.get("pep_base") or "").strip()
        dc = pep_dc.get(p) or "DC002 Dedicated Teams"
        upd[dc].append(x["id"])
    done = 0
    for dc, ids in upd.items():
        for i in range(0, len(ids), 200):
            chunk = ids[i:i+200]
            idlist = ",".join(str(x) for x in chunk)
            r = httpx.patch(f"{URL}/rest/v1/nova_base?id=in.({idlist})", headers=HP, json={"no_hierarquia": dc}, timeout=60)
            if r.status_code >= 300:
                print(f"  ERRO: {r.status_code} {r.text[:150]}"); return
            done += len(chunk)
    print(f"  Orange: {done} linhas atualizadas")


def regra_peps_validados_receita():
    """1.7-1.14 - PEPs corrigidos via Receita 26.05.xlsx (referencia SAP)"""
    print("\n[1.7] PEPs validados via Receita 26.05.xlsx")
    FIXES = [
        ("BR07CLP00015", "RED HAT BRASIL LTDA", None, None),
        ("BR02CLP00021", None, "DC037 Business Unit", None),
        ("BR07CLP00019", "FIDELITY NATIONAL SERVICOS E CONTAC", None, None),
        ("BR07CLP00020", "FIDELITY NATIONAL SERVICOS E CONTAC", None, None),
        ("BR02CLP00020", "JULIUS BAER BRASIL GESTAO DE PATRIMONIO", None, None),
        ("BR07CLP00123", "UNIMED NACIONAL - COOPERATIVA CENTRAL", None, None),
        ("BR02CLP000186", "ELFA MEDICAMENTOS S.A", None, None),
        ("BR02CLP000116", "Adcos", None, None),
        ("BR07CLP00147", "BANCO OURINVEST S/A", None, "BU Finance"),  # 3044 Squad Gerenciada
        ("BR07CLP00203", "BANCO MUFG BRASIL S.A.", None, "BU Hyper"),  # 215135
        ("BR07CLP00099", "BANCO MUFG BRASIL S.A.", None, "BU Hyper"),  # 212190
        ("BR07CLP00100", "BANCO MUFG BRASIL S.A.", None, "BU Hyper"),  # 11283
        ("BR07CLP00204", "BANCO MUFG BRASIL S.A.", None, "BU Hyper"),  # 214919
        ("BR07CLP00151", "ODONTOPREV S.A.", None, "BU Health"),  # 213785
        ("BR07CLP00136", "BANCO OURINVEST S/A", None, "BU Finance"),  # 212772
        ("BR07CLP00081", "ULTRAPAR PARTICIPACOES S/A", None, "BU Hyper"),  # 211312_HORAS DESENVOL_SNOW
        ("BR07CLP00054", "EMPREENDIMENTOS IMOBILIARIOS PARAISO GOLD LTDA", None, "BU Hyper"),  # 10725 PARAISO GOLD RPA WATSON
    ]
    for pep, cli, dc, vert in FIXES:
        body = {}
        if cli: body["nome_cliente"] = cli
        if dc: body["no_hierarquia"] = dc
        if vert: body["vertical"] = vert
        if APPLY:
            r = httpx.patch(f"{URL}/rest/v1/nova_base?pep_base=eq.{pep}", headers=HP, json=body, timeout=60)
            n = len(r.json()) if r.status_code < 300 else 0
            print(f"  {pep} -> {body}: {n}")
        else:
            print(f"  {pep} -> {body}")


def regra_cliente_zero_null():
    """2.5 - nome_cliente='0' (string literal) -> NULL"""
    print("\n[2.5] nome_cliente='0' -> NULL")
    patch("nome_cliente=eq.0", {"nome_cliente": None}, "cliente='0'")


def regra_rodrigo_burgers():
    """2.4 - RODRIGO FONSECA BURGERS -> DC029 FC Consult. New Rev"""
    print("\n[2.4] RODRIGO FONSECA BURGERS -> DC029")
    patch("nome_pessoa=ilike.*RODRIGO*FONSECA*BURGE*&no_hierarquia=neq.DC029 FC Consult. New Rev",
          {"no_hierarquia": "DC029 FC Consult. New Rev"},
          "Rodrigo Burgers")


def regra_tdm():
    """3.1 - 11 pessoas TDM -> macro_area=TDM, classificacao=custo (so PJs+TDMs)"""
    print("\n[3.1] TDM macro_area + classificacao=custo")
    NOMES = [
        "Guilherme Amaral Bonilha",
        "Rafael Macedo Rozalino", "56.934.070 RAFAEL MACEDO ROZALINO", "Rafael Macedo",
        "Marcelo Pereira Lima",
        "FERNANDO PEREIRA LISBOA TECNOLOGIA", "Fernando Pereira Lisboa",
        "Roberto Antonio Ribeiro Caracciolo Junior",
        "LEONARDO BARBETTA DE OLIVEIRA TECNO", "Leonardo  Barbetta de Oliveira", "Leonardo Barbetta de Oliveira",
        "JAMIL DIAS COSTA - ME", "Jamil Dias Costa",
        "LEANDRO DE BRITO SISTEMAS", "Leandro de Brito",
        "Thiago Vieira Tersariol",
        "Fabiano da Silva Remião Monteiro", "Fabiano da Silva RemiÃ£o Monteiro",
        "Jefferson  da Silva Leal", "Jefferson da Silva Leal",
    ]
    if not APPLY:
        print(f"  TDM: {len(NOMES)} nomes alvo (PJs+TDMs)")
        return
    ids = []
    for n in NOMES:
        q = urllib.parse.quote(n, safe="")
        r = httpx.get(f"{URL}/rest/v1/nova_base?select=id,fonte&nome_pessoa=eq.{q}", headers=H)
        for x in r.json():
            if x["fonte"] in ("PJs", "TDMs"):
                ids.append(x["id"])
    if ids:
        for i in range(0, len(ids), 200):
            chunk = ids[i:i+200]
            idlist = ",".join(str(x) for x in chunk)
            r = httpx.patch(f"{URL}/rest/v1/nova_base?id=in.({idlist})", headers=HP,
                            json={"macro_area": "TDM", "classificacao": "custo"}, timeout=60)
        print(f"  TDM: {len(ids)} linhas atualizadas")
    else:
        print("  TDM: nada a atualizar")


def regra_pj_w_vertical_dc002():
    """2.1 - PJs com coluna W='Vertical' -> no_hierarquia=DC002 Dedicated Teams.

    Re-roda fix_pj_no_hierarquia_vertical.py contra a PJs.xlsx atual.
    """
    print("\n[2.1] PJs W='Vertical' -> DC002 Dedicated Teams (via PJs.xlsx)")
    XLSX = "2026 dados/custo gerencial/PJs.xlsx"
    import os
    if not os.path.exists(XLSX):
        # fallback Mapa Pessoas
        XLSX = "2026 dados/Mapa Pessoas - Mar26.xlsx"
        if not os.path.exists(XLSX):
            print(f"  AVISO: PJs.xlsx nao encontrado")
            return
    df = pd.read_excel(XLSX, sheet_name="PJs")
    df.columns = [str(c).strip() for c in df.columns]
    comp = "Compet" + chr(0xEA) + "ncia"
    df["_per"] = df[comp].astype(str).str[:7]
    df = df[df["worker_name"].notna()]
    pc_w = "Profit Center.1"

    def _norm(s):
        if not s or (isinstance(s, float) and pd.isna(s)): return ""
        s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"\s+", " ", s).strip().upper()

    is_vertical_keys = {}
    for _, r in df.iterrows():
        k = (_norm(r["worker_name"]), r["_per"], round(float(r.get("valor_a_pagar") or 0), 2))
        is_vertical_keys[k] = _norm(r.get(pc_w)) == "VERTICAL"

    # nova_base PJ
    allr = []
    off = 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/nova_base?select=id,nome_pessoa,periodo,valor_liquido,no_hierarquia&fonte=eq.PJs&offset={off}&limit=1000", headers=H, timeout=60)
        d = r.json()
        if not isinstance(d, list): break
        allr += d
        if len(d) < 1000: break
        off += 1000

    to_upd = []
    for x in allr:
        k = (_norm(x["nome_pessoa"]), x["periodo"], round(float(x["valor_liquido"] or 0), 2))
        if is_vertical_keys.get(k) and (x.get("no_hierarquia") or "") != "DC002 Dedicated Teams":
            to_upd.append(x["id"])

    if not APPLY:
        print(f"  PJ W='Vertical': {len(to_upd)} linhas candidatas (de {len(allr)} PJs)")
        return
    if to_upd:
        for i in range(0, len(to_upd), 200):
            chunk = to_upd[i:i+200]
            idlist = ",".join(str(x) for x in chunk)
            r = httpx.patch(f"{URL}/rest/v1/nova_base?id=in.({idlist})", headers=HP,
                            json={"no_hierarquia": "DC002 Dedicated Teams"}, timeout=60)
    print(f"  PJ W='Vertical': {len(to_upd)} linhas atualizadas")


def main():
    print(f"=" * 70)
    print(f"RE-APLICAR AJUSTES MANUAIS  {'[APLICANDO]' if APPLY else '[DRY-RUN]'}")
    print(f"=" * 70)

    regra_pep_almap()
    regra_leonardo_almap()
    regra_tatiane_transunion()
    regra_transunion_bu_finance()
    regra_fernando_boldrin_klabin()
    regra_it_solution_poliedro()
    regra_no_hierarquia_codes()
    regra_orange_no_hierarquia()
    regra_cliente_zero_null()
    regra_rodrigo_burgers()
    regra_tdm()
    regra_pj_w_vertical_dc002()

    print()
    print(f"=" * 70)
    if not APPLY:
        print("DRY-RUN concluido. Use --apply pra efetivar.")
    else:
        print("OK. Rode tambem o clear-cache no site pra recarregar.")
    print(f"=" * 70)


if __name__ == "__main__":
    main()

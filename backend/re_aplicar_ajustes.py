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


def regra_odontoprev_centros():
    """1.3e - Odontoprev: centro de lucro por empresa
       BR07 Hyper -> DC008 Hyperautomation
       BR08 Dojo  -> DC012
       BR05 SGA   -> DC032
       BR04 Nacao Digital -> DC030
    """
    print("\n[1.3e] Odontoprev: centro de lucro por empresa")
    MAP = [
        ("empresa=ilike.*Hyper*",   "DC008 Hyperautomation", "Hyper -> DC008"),
        ("empresa=ilike.*Dojo*",    "DC012",                 "Dojo -> DC012"),
        ("empresa=ilike.*SGA*",     "DC032",                 "SGA -> DC032"),
        ("empresa=ilike.*Digital*", "DC030",                 "Nacao Digital -> DC030"),
    ]
    for emp_filt, dc, desc in MAP:
        patch(f"nome_cliente=ilike.*ODONTOPREV*&{emp_filt}&or=(no_hierarquia.is.null,no_hierarquia.neq.{urllib.parse.quote(dc, safe='')})",
              {"no_hierarquia": dc},
              f"Odontoprev {desc}")


def regra_riachuelo_dc008():
    """1.3d - Riachuelo (todas grafias) -> DC008 Hyperautomation"""
    print("\n[1.3d] Riachuelo -> DC008 Hyperautomation")
    # Cobre variantes "Riachuelo", "RIACHUELO", "LOJAS RIACHUELO SA", "11406-RIACHUELO"
    patch("nome_cliente=ilike.*RIACHUELO*&or=(no_hierarquia.is.null,no_hierarquia.neq.DC008 Hyperautomation)",
          {"no_hierarquia": "DC008 Hyperautomation"},
          "Riachuelo DC008")


def regra_spad_adcos():
    """1.3c - SPAD COMERCIO DE COSMETICOS LTDA -> Adcos / BU Health"""
    print("\n[1.3c] SPAD Cosmeticos -> Adcos + BU Health")
    patch("nome_cliente=ilike.*SPAD*COSMETIC*&nome_cliente=neq.Adcos",
          {"nome_cliente": "Adcos", "vertical": "BU Health"},
          "SPAD -> Adcos")
    # Garante que TODAS as linhas Adcos fiquem em BU Health
    patch("nome_cliente=ilike.Adcos&or=(vertical.is.null,vertical.neq.BU Health)",
          {"vertical": "BU Health"},
          "Adcos BU Health")


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
        # Codigos sem nome -> nome completo
        "DC001": "DC001 Squads",
        "DC002": "DC002 Dedicated Teams",
        "DC004": "DC004 E-commerce",
        "DC005": "DC005 Open-X",
        "DC007": "DC007 Imagine",
        "DC008": "DC008 Hyperautomation",
        "DC009": "DC009 Licensing Hyper",
        "DC029": "DC029 FC Consult. New Rev",
        "DC037": "DC037 Business Unit",
        "DC040": "DC040 FC Consult. B. Sales",
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
        ("BR07CLP00015", "BANCO OURINVEST S/A", None, "BU Finance"),
        ("BR02CLP00021", None, "DC002 Dedicated Teams", None),  # Unimed SP, NG
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
        ("BR07CLP00089", "Riachuelo", None, "BU Retail"),  # 11406-Riachuelo
        ("BR02CLP00134", "BIRMINGHAM BANK", None, None),  # Squad BIRMINGHAM BANK
        ("BR04CLP00044", "Grupo Dorben", None, None),  # CG - Grupo Dorben
        ("BR04CLP00047", "Feira Nova", None, None),  # CG - Feira Nova
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
        "Roberto Antonio Ribeiro Caracciolo Junior", "CARACCIOLO E NUNEZ LTDA",
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


def _realocfin_aplicar(integrais, splits):
    """Motor comum das regras REALOCFIN (4.x): custos CLT indevidos saem do
    cliente pro "projeto" REALOCFIN, mantendo BU/empresa/mes.

    integrais: [(periodo, nome_pessoa, nome_cliente)] - move a linha inteira
    splits:    [(periodo, nome, cliente, full_vl, keep_vl, keep_sap, keep_h,
                 move_vl, move_sap, move_h, motivo)] - reduz a original pro
                proporcional e insere linha nova REALOCFIN com o excedente.
    Idempotente; valores dos splits sao fixos (se o valor cheio mudar num
    re-upload, pula com AVISO pra recalibrar).
    """
    ALVO = {"nome_cliente": "REALOCFIN", "tipos": "REALOCFIN"}
    FD_AJUSTE = "Ajuste REALOCFIN (apuracao metas comerciais)"
    COPY_EXCLUDE = {"id", "upload_id", "uploaded_at", "uploaded_by",
                    "apuracao"}  # apuracao e generated column (nao aceita INSERT)

    for per, nome, cli in integrais:
        patch(f"fonte=eq.CLTs&periodo=eq.{per}&nome_pessoa=eq.{urllib.parse.quote(nome, safe='')}"
              f"&nome_cliente=eq.{urllib.parse.quote(cli, safe='')}",
              ALVO, f"{nome} {per} ({cli}) -> REALOCFIN")

    for (per, nome, cli, full_vl, keep_vl, keep_sap, keep_h,
         move_vl, move_sap, move_h, motivo) in splits:
        q = urllib.parse.quote(nome, safe="")
        base_f = f"fonte=eq.CLTs&periodo=eq.{per}&nome_pessoa=eq.{q}"
        r = httpx.get(f"{URL}/rest/v1/nova_base?{base_f}&nome_cliente=eq.{urllib.parse.quote(cli, safe='')}&select=*",
                      headers=H, timeout=60)
        rows = r.json() if r.status_code < 300 else []
        r2 = httpx.get(f"{URL}/rest/v1/nova_base?{base_f}&nome_cliente=eq.REALOCFIN&select=id", headers=H, timeout=60)
        ja_inserida = bool(r2.json()) if r2.status_code < 300 else False

        if len(rows) != 1:
            print(f"  AVISO {nome} {per}: esperava 1 linha {cli}, achei {len(rows)}"
                  f"{' (split ja aplicado)' if ja_inserida else ''} - pulando")
            continue
        row = rows[0]
        cur_vl = round(float(row.get("valor_liquido") or 0), 2)
        precisa_patch = abs(cur_vl - keep_vl) > 0.02
        if precisa_patch and abs(cur_vl - full_vl) > 0.02:
            print(f"  AVISO {nome} {per}: valor atual {cur_vl:,.2f} != esperado {full_vl:,.2f} - pulando")
            continue

        if not APPLY:
            print(f"  {nome} {per} ({motivo}): "
                  f"{f'{cli} ja proporcional' if not precisa_patch else f'{cli} {cur_vl:,.2f} -> {keep_vl:,.2f}'}"
                  f"{'; linha REALOCFIN ja existe' if ja_inserida else f'; + INSERT REALOCFIN {move_vl:,.2f}'}")
            continue

        if precisa_patch:
            body = {"valor_liquido": keep_vl, "custo_rateado": -keep_vl, "margem": -keep_vl,
                    "custo_gerencial_sap": keep_sap, "horas": keep_h}
            rp = httpx.patch(f"{URL}/rest/v1/nova_base?id=eq.{row['id']}", headers=HP, json=body, timeout=60)
            if rp.status_code >= 300:
                print(f"  ERRO patch {nome} {per}: {rp.status_code} {rp.text[:150]}")
                continue
        if not ja_inserida:
            nova = {k: v for k, v in row.items() if k not in COPY_EXCLUDE}
            nova.update({"nome_cliente": "REALOCFIN", "tipos": "REALOCFIN", "fonte_dados": FD_AJUSTE,
                         "valor_liquido": move_vl, "custo_rateado": -move_vl, "margem": -move_vl,
                         "custo_gerencial_sap": move_sap, "horas": move_h})
            ri = httpx.post(f"{URL}/rest/v1/nova_base", headers=HP, json=nova, timeout=60)
            if ri.status_code >= 300:
                print(f"  ERRO insert {nome} {per}: {ri.status_code} {ri.text[:150]}")
                continue
        print(f"  {nome} {per}: split ok ({motivo}) - {cli} fica {keep_vl:,.2f}, REALOCFIN {move_vl:,.2f}")


def _migrar_excedente_orange(per, nome, dest_cli, pep_b, pep, tipos, vert, label):
    """Move horas Orange do excedente (REALOCFIN) pro cliente de origem real."""
    patch(f"fonte=eq.base Orange&periodo=eq.{per}&nome_pessoa=eq.{urllib.parse.quote(nome, safe='')}"
          f"&nome_cliente=eq.REALOCFIN&fonte_dados=eq.{urllib.parse.quote(label, safe='')}",
          {"nome_cliente": dest_cli, "pep_base": pep_b, "pep": pep, "tipos": tipos, "vertical": vert},
          f"{nome} {per}: horas excedente REALOCFIN -> {dest_cli}")


def regra_realocfin_btg():
    """4.1 - Apuracao metas comerciais (jul/26): custos CLT indevidos no BANCO BTG
    -> projeto REALOCFIN (sai do cliente, mantem BU/empresa/mes).

    Pessoas desligadas/transferidas cujo custo continuou caindo no BTG, e
    entradas/saidas no meio do mes com custo cheio (regra: dias uteis x 8h).
    Robson dos Santos (BR07 Hyper) nunca atuou no BTG (Orange: Callink/Energisa);
    o BTG legitimo e ROBSON DOS SANTOS ROSA - eq. exato nao pega ele.
    Gustavo (entrou 21/02): Amanda decidiu 2026-07-02 aplicar a regua padrao
    (jan inteiro fora + fev proporcional), apesar do conflito com racionais.
    Backups pre-ajuste: _backup_realocfin_btg_jan_abr26.json + _backup_realocfin_gustavo_btg.json
    """
    print("\n[4.1] BTG: custos CLT indevidos -> REALOCFIN (apuracao metas comerciais)")

    # (a) meses inteiros indevidos: pessoa nao estava mais/ainda no BTG
    INTEGRAIS = [
        ("2026-01", "ELLEN DALECIO MATOS"),               # saiu 18/12/25
        ("2026-02", "ELLEN DALECIO MATOS"),
        ("2026-01", "ERIK LOPES VITELLI"),                # saiu 05/12/25
        ("2026-01", "LEONARDO FERREIRA SILVA"),           # saiu 27/10/25
        ("2026-02", "LEONARDO FERREIRA SILVA"),
        ("2026-03", "LEONARDO FERREIRA SILVA"),
        ("2026-01", "PABLO MADEIRA FREIRE"),              # saiu em 2025
        ("2026-02", "MARCELO SANTOS DA COSTA"),           # saiu 31/01/26
        ("2026-03", "MARCELO SANTOS DA COSTA"),
        ("2026-03", "ANA CAROLINA RODRIGUES LEITE"),      # saiu 27/02/26
        ("2026-03", "GABRIEL DAMASCENO DANTAS ESTEFANO"), # saiu 27/02/26
        ("2026-02", "EVANDRO ARAUJO DE ABREU"),           # saiu 09/01/26
        ("2026-04", "WILHAMS MEIRA JUNIOR"),              # saiu 13/03/26
        ("2026-01", "ROBSON DOS SANTOS"),                 # Hyper, nunca foi BTG
        ("2026-02", "ROBSON DOS SANTOS"),
        ("2026-03", "ROBSON DOS SANTOS"),
        ("2026-04", "ROBSON DOS SANTOS"),
        ("2026-01", "GUSTAVO FELIPE HAUS GONCALVES"),     # entrou 21/02/26
    ]
    # (b) meses parciais: mantem no BTG so o proporcional (dias uteis x 8h).
    #     Valores fixados a partir do estado de 2026-07-02 (ver backup).
    SPLITS = [
        # (periodo, nome, full_vl, keep: vl/sap/h, move: vl/sap/h, motivo)
        ("2026-01", "EVANDRO ARAUJO DE ABREU", 20377.70,
         5822.20, 5781.77, 48.0, 14555.50, 14454.42, 118.8, "saiu 09/01: 48h de 168h"),
        ("2026-03", "DANIELLE SOUSA DA SILVA", 14734.32,
         4018.45, 2224.61, 48.0, 10715.87, 5932.29, 49.4, "entrou 24/03: 48h de 176h"),
        ("2026-03", "DIEGO DO CARMO SILVEIRA", 23248.71,
         12681.11, 6932.58, 96.2, 10567.60, 5777.15, 0.0, "entrou 16/03: 96h de 176h (horas ja corretas)"),
        ("2026-03", "WILHAMS MEIRA JUNIOR", 15081.76,
         6855.35, 5920.53, 80.0, 8226.41, 7104.63, 72.0, "saiu 13/03: 80h de 176h"),
        ("2026-02", "GUSTAVO FELIPE HAUS GONCALVES", 22471.39,
         5617.85, 5309.45, 40.0, 16853.54, 15928.36, 111.22, "entrou 21/02: 40h de 160h"),
    ]
    _realocfin_aplicar(
        integrais=[(per, nome, "BANCO BTG") for per, nome in INTEGRAIS],
        splits=[(per, nome, "BANCO BTG", *resto) for per, nome, *resto in SPLITS])


def regra_realocfin_abc_tu_bullla():
    """4.2 - Apuracao metas comerciais (jul/26), lote 2: BANCO ABC, Transunion
    e Bullla -> REALOCFIN. Mesma metodologia da 4.1.

    PENDENTES (fora do lote): Vinicius Farias Rocha jan/26 no BANCO MUFG
    (19.216,65 - Amanda vai verificar onde ele estava em jan); custos abr/26
    com cliente 'nan' (Rosangela 27.217,39 / Joao Brito 21.009,68).
    Obs: Orange de mar/26 mostra 152h na TU pra Alex e Joao (contradiz saida
    27/02) - Amanda confirmou mover mesmo assim.
    Backup pre-ajuste: _backup_realocfin_abc_tu_bullla_lote2.json
    """
    print("\n[4.2] ABC/TransUnion/Bullla: custos CLT indevidos -> REALOCFIN (lote 2)")
    INTEGRAIS = [
        ("2026-01", "MARIO CESAR MIRANDA JUNIOR", "BANCO ABC"),        # saiu 16/12/25
        ("2026-03", "ALEX DOS SANTOS NALIM", "Transunion"),            # saiu 27/02/26
        ("2026-03", "JOAO LUIS MENDES DA SILVA BRITO", "Transunion"),  # saiu 27/02/26
    ]
    # Valores fixados a partir do estado de 2026-07-02 (ver backup do lote 2).
    SPLITS = [
        # (periodo, nome, cliente, full_vl, keep: vl/sap/h, move: vl/sap/h, motivo)
        ("2026-02", "ROSANGELA DANTAS LIMA", "BANCO ABC", 27216.93,
         6804.23, 6804.23, 40.0, 20412.70, 20412.70, 120.0, "entrou 23/02: 40h de 160h"),
        ("2026-02", "VINICIUS FARIAS ROCHA", "Transunion", 20087.44,
         15065.58, 13559.02, 120.0, 5021.86, 4519.68, 24.0, "entrou 09/02: 120h de 160h"),
        ("2026-02", "JOSE ELIOMAR INACIO DE OLIVEIRA", "Bullla", 14411.45,
         10808.59, 10307.56, 120.0, 3602.86, 3435.86, 32.58, "entrou 09/02: 120h de 160h"),
    ]
    _realocfin_aplicar(integrais=INTEGRAIS, splits=SPLITS)


def regra_rateio_open_accelerator_h1():
    """4.3 - Time Open Finance/Insurance Accelerator (H1/26, jan-mar).

    O time lancava custo sem criterio (concentrado em HDI / linhas sem cliente).
    Percentual correto H1 (definicao do gestor, jul/26):
      BANCO PAN 50% | HDI 20% | GRUPO BANQI 14% | CARTOS 8% | Justos Seguros 8%
    O valor correto por pessoa/mes vem da planilha do time (print da Amanda);
    o excedente do custo real vai pro REALOCFIN. Lucas jan/26 = 100% REALOCFIN
    (print marca 'x' - nao era do time em jan). Faltantes (sem linha PJ na base:
    Felipe/Kleber/Lucas/Ney/Yagan fev-mar e Leonardo Benevenuto jan-mar) sao
    INSERIDOS com o valor da planilha, ja rateados. ABRIL FORA (sem print).
    Linhas novas/alteradas: fonte_dados = LABEL (ilha no rateio do site).
    Backup pre-ajuste: _backup_rateio_open_h1.json
    """
    print("\n[4.3] Open Accelerator H1: rateio 50/20/14/8/8 + excedente -> REALOCFIN")
    LABEL = "Ajuste rateio Open Accelerator H1"
    PCTS = [("BANCO PAN", 0.50), ("HDI", 0.20), ("GRUPO BANQI", 0.14),
            ("CARTOS", 0.08), ("Justos Seguros", 0.08)]
    COPY_EXCLUDE = {"id", "upload_id", "uploaded_at", "uploaded_by", "apuracao"}

    def shares(p):
        """[(cliente, valor)] - 4 primeiros arredondados, ultimo fecha a soma."""
        vals = [round(p * pct, 2) for _, pct in PCTS[:-1]]
        vals.append(round(p - sum(vals), 2))
        return list(zip([c for c, _ in PCTS], vals))

    def _get_pj(per, nome, cli=None):
        q = f"fonte=eq.PJs&periodo=eq.{per}&nome_pessoa=eq.{urllib.parse.quote(nome, safe='')}"
        if cli is not None:
            q += f"&nome_cliente=eq.{urllib.parse.quote(cli, safe='')}"
        r = httpx.get(f"{URL}/rest/v1/nova_base?{q}&select=*", headers=H, timeout=60)
        return r.json() if r.status_code < 300 else []

    def _ja_aplicado(per, nome):
        q = (f"fonte=eq.PJs&periodo=eq.{per}&nome_pessoa=eq.{urllib.parse.quote(nome, safe='')}"
             f"&fonte_dados=eq.{urllib.parse.quote(LABEL, safe='')}")
        r = httpx.get(f"{URL}/rest/v1/nova_base?{q}&select=id&limit=1", headers=H, timeout=60)
        return bool(r.json()) if r.status_code < 300 else False

    def _post(row):
        r = httpx.post(f"{URL}/rest/v1/nova_base", headers=HP, json=row, timeout=60)
        if r.status_code >= 300:
            print(f"  ERRO insert: {r.status_code} {r.text[:150]}")
            return False
        return True

    def _nova(base_row, cliente, valor, tipos=None, vertical=None):
        nova = {k: v for k, v in base_row.items() if k not in COPY_EXCLUDE}
        nova.update({"nome_cliente": cliente, "fonte_dados": LABEL,
                     "valor_liquido": valor, "custo_rateado": -valor, "margem": -valor})
        if tipos is not None: nova["tipos"] = tipos
        if vertical is not None: nova["vertical"] = vertical
        return nova

    # (a) Lucas jan: 100% REALOCFIN (nao era do time; nao pertence a HDI)
    patch("fonte=eq.PJs&periodo=eq.2026-01&nome_pessoa=eq.Lucas Alves Barbosa Monteiro&nome_cliente=eq.HDI",
          {"nome_cliente": "REALOCFIN", "tipos": "REALOCFIN"},
          "Lucas Alves Barbosa Monteiro 2026-01 (HDI) -> REALOCFIN integral")

    # (b) linhas PJ existentes: viram 5 fatias + excedente REALOCFIN
    #     (periodo, nome_pessoa exato, cliente atual, valor na base B, valor planilha P)
    RESHAPE = [
        ("2026-01", "Felipe Mateus Marcolla", "BANCO PAN", 12000.00, 12000.00),
        ("2026-01", "Gleisy Caroline Marc Fracasso", "HDI", 11000.00, 11000.00),
        ("2026-01", "Kleber Aquino dos Santos Junior", "STRADA", 23000.00, 11000.00),
        ("2026-01", "Luiz Otavio Lima Pinheiro", "HDI", 12571.68, 12000.00),
        ("2026-01", "Ana Caroline Brandão Costa", "GRUPO BANQI", 8500.00, 8500.00),
        ("2026-01", "Ney Candido Fonseca", "BANCO PAN", 30000.00, 30000.00),
        ("2026-01", "Vanderson Teodoro Camatini", "HDI", 15715.04, 15000.00),
        ("2026-01", "Yagan James Cadorin", "GRUPO CASAS BAHIA", 18819.84, 3619.00),
        ("2026-02", "GLEISY CONSULTORIA DE TI LTDA", "nan", 11000.00, 11000.00),
        ("2026-02", "LUIZ OTAVIO LIMA PINHEIRO CONSULTOR", "HDI", 12000.00, 12000.00),
        ("2026-02", "54.609.378 ANA CAROLINE BRANDAO COS", "nan", 8500.00, 8500.00),
        ("2026-02", "CAMATINI DESENVOLVIMENTO DE SOFTWAR", "nan", 15000.00, 15000.00),
        ("2026-03", "GLEISY CONSULTORIA DE TI LTDA", "nan", 11000.00, 11000.00),
        ("2026-03", "LUIZ OTAVIO LIMA PINHEIRO CONSULTOR", "HDI", 12000.00, 12000.00),
        ("2026-03", "54.609.378 ANA CAROLINE BRANDAO COS", "nan", 8500.00, 8500.00),
        ("2026-03", "CAMATINI DESENVOLVIMENTO DE SOFTWAR", "nan", 15000.00, 15000.00),
    ]
    # Excedentes com trabalho real no cliente de origem NAO vao pro REALOCFIN:
    # voltam pro proprio cliente (decisao Amanda 2026-07-07 - Yagan tem receita
    # racional no GCB o trimestre todo; Kleber tem horas Orange na STRADA).
    EXCEDENTE_DESTINO = {
        ("2026-01", "Kleber Aquino dos Santos Junior"): ("STRADA", "Assessment Modernização", "BU Retail"),
        ("2026-01", "Yagan James Cadorin"): ("GRUPO CASAS BAHIA", "Open Insurance Accelerator Lib", "BU Retail"),
    }

    for per, nome, cli_atual, b_esp, p in RESHAPE:
        dest_cli, dest_tipos, dest_vert = EXCEDENTE_DESTINO.get((per, nome), ("REALOCFIN", "REALOCFIN", None))
        if dest_cli != "REALOCFIN":
            # migra excedente que tenha ido pro REALOCFIN em versao anterior da regra
            patch(f"fonte=eq.PJs&periodo=eq.{per}&nome_pessoa=eq.{urllib.parse.quote(nome, safe='')}"
                  f"&nome_cliente=eq.REALOCFIN&fonte_dados=eq.{urllib.parse.quote(LABEL, safe='')}",
                  {"nome_cliente": dest_cli, "tipos": dest_tipos, "vertical": dest_vert},
                  f"{nome} {per}: excedente REALOCFIN -> {dest_cli}")
        if _ja_aplicado(per, nome):
            print(f"  {nome} {per}: ja aplicado")
            continue
        rows = _get_pj(per, nome, cli_atual)
        if len(rows) != 1:
            ok_msg = " (ja aplicado)" if _ja_aplicado(per, nome) else " - AVISO: verificar!"
            print(f"  {nome} {per}: linha em {cli_atual} nao encontrada{ok_msg}")
            continue
        row = rows[0]
        b = round(float(row.get("valor_liquido") or 0), 2)
        if abs(b - b_esp) > 0.02:
            print(f"  AVISO {nome} {per}: valor {b:,.2f} != esperado {b_esp:,.2f} - pulando")
            continue
        fatias = shares(p)
        sobra = round(b - p, 2)
        if not APPLY:
            print(f"  {nome} {per}: {cli_atual} {b:,.2f} -> "
                  + ", ".join(f"{c} {v:,.2f}" for c, v in fatias)
                  + (f", REALOCFIN {sobra:,.2f}" if sobra > 0.005 else ""))
            continue
        # PATCH original -> 1a fatia (BANCO PAN); INSERT demais + excedente
        c0, v0 = fatias[0]
        rp = httpx.patch(f"{URL}/rest/v1/nova_base?id=eq.{row['id']}", headers=HP,
                         json={"nome_cliente": c0, "valor_liquido": v0, "custo_rateado": -v0,
                               "margem": -v0, "fonte_dados": LABEL, "vertical": "BU Finance"},
                         timeout=60)
        if rp.status_code >= 300:
            print(f"  ERRO patch {nome} {per}: {rp.status_code} {rp.text[:150]}")
            continue
        ok = all(_post(_nova(row, c, v, vertical="BU Finance")) for c, v in fatias[1:])
        if ok and sobra > 0.005:
            vert_orig = row.get("vertical") if str(row.get("vertical")) not in ("nan", "None", "") else "BU Finance"
            ok = _post(_nova(row, "REALOCFIN", sobra, tipos="REALOCFIN", vertical=vert_orig))
        print(f"  {nome} {per}: rateado ({b:,.2f} = {p:,.2f} nos 5 clientes"
              + (f" + {sobra:,.2f} REALOCFIN)" if sobra > 0.005 else ")"))

    # (c) faltantes: sem linha PJ na base -> INSERE valor da planilha ja rateado.
    #     (periodo, nome da nova linha, P, pessoa-template, periodo-template)
    INSERTS = [
        ("2026-01", "LEONARDO JUNIO BENEVENUTO", 500.00, "Felipe Mateus Marcolla", "2026-01"),
        ("2026-02", "Felipe Mateus Marcolla", 12000.00, "Felipe Mateus Marcolla", "2026-01"),
        ("2026-02", "Kleber Aquino dos Santos Junior", 11000.00, "Kleber Aquino dos Santos Junior", "2026-01"),
        ("2026-02", "Lucas Alves Barbosa Monteiro", 17500.00, "Lucas Alves Barbosa Monteiro", "2026-01"),
        ("2026-02", "Ney Candido Fonseca", 30000.00, "Ney Candido Fonseca", "2026-01"),
        ("2026-02", "Yagan James Cadorin", 3619.00, "Yagan James Cadorin", "2026-01"),
        ("2026-02", "LEONARDO JUNIO BENEVENUTO", 500.00, "Felipe Mateus Marcolla", "2026-01"),
        ("2026-03", "Felipe Mateus Marcolla", 12000.00, "Felipe Mateus Marcolla", "2026-01"),
        ("2026-03", "Kleber Aquino dos Santos Junior", 11000.00, "Kleber Aquino dos Santos Junior", "2026-01"),
        ("2026-03", "Lucas Alves Barbosa Monteiro", 17500.00, "Lucas Alves Barbosa Monteiro", "2026-01"),
        ("2026-03", "Ney Candido Fonseca", 30000.00, "Ney Candido Fonseca", "2026-01"),
        ("2026-03", "Yagan James Cadorin", 3619.00, "Yagan James Cadorin", "2026-01"),
        ("2026-03", "LEONARDO JUNIO BENEVENUTO", 500.00, "Felipe Mateus Marcolla", "2026-01"),
    ]
    for per, nome, p, tpl_nome, tpl_per in INSERTS:
        if _ja_aplicado(per, nome):
            print(f"  {nome} {per}: inserts ja existem")
            continue
        # se a pessoa ja tem linha PJ nesse mes fora do LABEL, nao insere (evita duplicar custo)
        if _get_pj(per, nome):
            print(f"  AVISO {nome} {per}: ja existe linha PJ nesse mes - NAO inserindo (verificar)")
            continue
        fatias = shares(p)
        if not APPLY:
            print(f"  {nome} {per}: INSERIR {p:,.2f} -> " + ", ".join(f"{c} {v:,.2f}" for c, v in fatias))
            continue
        tpl_rows = _get_pj(tpl_per, tpl_nome)
        tpl = None
        for t in tpl_rows:  # template ja pode ter sido re-rateado; qualquer linha serve de molde
            tpl = t; break
        if tpl is None:
            print(f"  ERRO {nome} {per}: template {tpl_nome} {tpl_per} nao encontrado")
            continue
        base_row = dict(tpl)
        base_row.update({"periodo": per, "nome_pessoa": nome, "horas": None,
                         "tipos": "Open Finance Accelerator", "pep": None, "pep_base": None,
                         "custo_gerencial_sap": 0, "receita": 0})
        ok = all(_post(_nova(base_row, c, v, vertical="BU Finance")) for c, v in fatias)
        print(f"  {nome} {per}: inseridos {p:,.2f} nos 5 clientes {'ok' if ok else 'COM ERRO'}")


def regra_horas_open_accelerator_h1():
    """4.4 - Horas Orange do time Open Accelerator compativeis com o custo (4.3).

    Redistribui as horas 'base Orange' de cada pessoa/mes na MESMA proporcao
    do custo alocado: fatias 50/20/14/8/8 sobre o valor da planilha (P) e o
    excedente (B-P) em horas no REALOCFIN. Total de horas da pessoa preservado.
    Re-aplicavel: upload novo da Base Orange restaura as horas originais e
    este script re-redistribui (rodar apos cada upload, como sempre).
    Backup pre-ajuste: _backup_orange_open_h1.json
    """
    print("\n[4.4] Open Accelerator H1: horas Orange na proporcao do custo")
    LABEL = "Ajuste rateio Open Accelerator H1"
    COPY_EXCLUDE = {"id", "upload_id", "uploaded_at", "uploaded_by", "apuracao"}
    PEP_MAP = {
        "BANCO PAN":      ("BR02CLP00071", "BR02CLP00071.1.2"),
        "HDI":            ("BR02CLP00008", "BR02CLP00008.1.1"),
        "GRUPO BANQI":    ("BR02CLP00097", "BR02CLP00097.1.1"),
        "CARTOS":         ("BR02CLP00072", "BR02CLP00072.1.1"),
        "Justos Seguros": ("BR02CLP00074", "BR02CLP00074.1.1"),
        "REALOCFIN":      (None, None),
        "STRADA":            ("BR02CLP000250", "BR02CLP000250.1.1"),
        "GRUPO CASAS BAHIA": ("BR02CLP00042", "BR02CLP00042.1.3"),
    }
    # Excedente em horas segue o mesmo destino do custo (Yagan->GCB, Kleber->STRADA)
    EXCEDENTE_DESTINO_H = {
        ("2026-01", "Kleber Aquino dos Santos Junior"): ("STRADA", "Assessment Modernização", "BU Retail"),
        ("2026-01", "Yagan James Cadorin"): ("GRUPO CASAS BAHIA", "Open Insurance Accelerator Lib", "BU Retail"),
    }
    PCTS = [("BANCO PAN", 0.50), ("HDI", 0.20), ("GRUPO BANQI", 0.14),
            ("CARTOS", 0.08), ("Justos Seguros", 0.08)]

    # (periodo, nome exato nas linhas Orange, custo na base B, valor planilha P)
    TIME = []
    PESSOAS = [  # (nome, {periodo: (B, P)})
        ("Felipe Mateus Marcolla", {"2026-01": (12000.00, 12000.00), "2026-02": (12000.00, 12000.00), "2026-03": (12000.00, 12000.00)}),
        ("Gleisy Caroline Marc Fracasso", {"2026-01": (11000.00, 11000.00), "2026-02": (11000.00, 11000.00), "2026-03": (11000.00, 11000.00)}),
        ("Kleber Aquino dos Santos Junior", {"2026-01": (23000.00, 11000.00), "2026-02": (11000.00, 11000.00), "2026-03": (11000.00, 11000.00)}),
        ("Lucas Alves Barbosa Monteiro", {"2026-01": (17498.88, 0.00), "2026-02": (17500.00, 17500.00), "2026-03": (17500.00, 17500.00)}),
        ("Luiz Otavio Lima Pinheiro", {"2026-01": (12571.68, 12000.00), "2026-02": (12000.00, 12000.00), "2026-03": (12000.00, 12000.00)}),
        ("Ana Caroline Brandão Costa", {"2026-01": (8500.00, 8500.00), "2026-02": (8500.00, 8500.00), "2026-03": (8500.00, 8500.00)}),
        ("Ney Candido Fonseca", {"2026-01": (30000.00, 30000.00), "2026-02": (30000.00, 30000.00), "2026-03": (30000.00, 30000.00)}),
        ("Vanderson Teodoro Camatini", {"2026-01": (15715.04, 15000.00), "2026-02": (15000.00, 15000.00), "2026-03": (15000.00, 15000.00)}),
        ("Yagan James Cadorin", {"2026-01": (18819.84, 3619.00), "2026-02": (3619.00, 3619.00), "2026-03": (3619.00, 3619.00)}),
    ]
    for nome, meses in PESSOAS:
        for per, (b, p) in meses.items():
            TIME.append((per, nome, b, p))

    for per, nome, b, p in TIME:
        dest_h = EXCEDENTE_DESTINO_H.get((per, nome))
        if dest_h:
            _migrar_excedente_orange(per, nome, dest_h[0], PEP_MAP[dest_h[0]][0],
                                     PEP_MAP[dest_h[0]][1], dest_h[1], dest_h[2], LABEL)
        q = urllib.parse.quote(nome, safe="")
        r = httpx.get(f"{URL}/rest/v1/nova_base?fonte=eq.base Orange&periodo=eq.{per}"
                      f"&nome_pessoa=eq.{q}&select=*", headers=H, timeout=60)
        rows = r.json() if r.status_code < 300 else []
        labeled = [x for x in rows if x.get("fonte_dados") == LABEL]
        if labeled and len(labeled) == len(rows):
            print(f"  {nome} {per}: horas ja redistribuidas")
            continue
        if labeled:
            print(f"  AVISO {nome} {per}: estado misto ({len(labeled)}/{len(rows)} com label) - pulando")
            continue
        if not rows:
            print(f"  {nome} {per}: sem linhas Orange - nada a fazer")
            continue
        htot = round(sum(float(x.get("horas") or 0) for x in rows), 2)
        if htot <= 0:
            print(f"  {nome} {per}: horas totais 0 - nada a fazer")
            continue

        # fatias de valor (mesmas da 4.3) -> fracoes de hora
        vals = [round(p * pct, 2) for _, pct in PCTS[:-1]]
        vals.append(round(p - sum(vals), 2))
        fatias = [(c, v) for (c, _), v in zip(PCTS, vals) if p > 0.005]
        sobra = round(b - p, 2)
        if sobra > 0.005:
            fatias.append(((dest_h[0] if dest_h else "REALOCFIN"), sobra))
        buckets = []
        for c, v in fatias[:-1]:
            buckets.append((c, round(htot * v / b, 2)))
        buckets.append((fatias[-1][0], round(htot - sum(h for _, h in buckets), 2)))

        if not APPLY:
            print(f"  {nome} {per}: {htot}h -> " + ", ".join(f"{c} {h}h" for c, h in buckets))
            continue

        erro = False
        for i, (c, h) in enumerate(buckets):
            pep_b, pep = PEP_MAP[c]
            body = {"nome_cliente": c, "horas": h, "fonte_dados": LABEL,
                    "vertical": "BU Finance", "pep": pep, "pep_base": pep_b,
                    "tipos": "REALOCFIN" if c == "REALOCFIN" else "Open Finance Accelerator"}
            if dest_h and c == dest_h[0]:
                body["tipos"], body["vertical"] = dest_h[1], dest_h[2]
            if i < len(rows):
                rr = httpx.patch(f"{URL}/rest/v1/nova_base?id=eq.{rows[i]['id']}", headers=HP, json=body, timeout=60)
            else:
                nova = {k: v for k, v in rows[0].items() if k not in COPY_EXCLUDE}
                nova.update(body)
                rr = httpx.post(f"{URL}/rest/v1/nova_base", headers=HP, json=nova, timeout=60)
            if rr.status_code >= 300:
                print(f"  ERRO {nome} {per} bucket {c}: {rr.status_code} {rr.text[:120]}")
                erro = True
        # linhas originais sobrando alem dos buckets: zera no REALOCFIN
        for x in rows[len(buckets):]:
            rr = httpx.patch(f"{URL}/rest/v1/nova_base?id=eq.{x['id']}", headers=HP,
                             json={"nome_cliente": "REALOCFIN", "horas": 0, "fonte_dados": LABEL,
                                   "tipos": "REALOCFIN", "pep": None, "pep_base": None}, timeout=60)
            if rr.status_code >= 300:
                print(f"  ERRO {nome} {per} zerando linha extra: {rr.status_code}")
                erro = True
        if not erro:
            print(f"  {nome} {per}: {htot}h redistribuidas em {len(buckets)} linhas")


def main():
    print(f"=" * 70)
    print(f"RE-APLICAR AJUSTES MANUAIS  {'[APLICANDO]' if APPLY else '[DRY-RUN]'}")
    print(f"=" * 70)

    regra_pep_almap()
    regra_leonardo_almap()
    regra_tatiane_transunion()
    regra_transunion_bu_finance()
    regra_spad_adcos()
    regra_odontoprev_centros()
    regra_riachuelo_dc008()
    regra_fernando_boldrin_klabin()
    regra_it_solution_poliedro()
    regra_no_hierarquia_codes()
    regra_peps_validados_receita()
    regra_orange_no_hierarquia()
    regra_cliente_zero_null()
    regra_rodrigo_burgers()
    regra_tdm()
    regra_pj_w_vertical_dc002()
    regra_realocfin_btg()
    regra_realocfin_abc_tu_bullla()
    regra_rateio_open_accelerator_h1()
    regra_horas_open_accelerator_h1()

    print()
    print(f"=" * 70)
    if not APPLY:
        print("DRY-RUN concluido. Use --apply pra efetivar.")
    else:
        print("OK. Rode tambem o clear-cache no site pra recarregar.")
    print(f"=" * 70)


if __name__ == "__main__":
    main()

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

    print()
    print(f"=" * 70)
    if not APPLY:
        print("DRY-RUN concluido. Use --apply pra efetivar.")
    else:
        print("OK. Rode tambem o clear-cache no site pra recarregar.")
    print(f"=" * 70)


if __name__ == "__main__":
    main()

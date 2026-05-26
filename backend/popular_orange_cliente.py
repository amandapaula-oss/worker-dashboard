"""Popula nome_cliente e vertical nas linhas Base Orange via PEP_base lookup.
Para cada Orange row, busca o cliente/vertical dominante em outras fontes pelo
mesmo pep_base. Sem match -> deixa None.
"""
import sys, io, collections, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx
from _supabase_creds import load_creds

URL, KEY = load_creds()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
HP = {**H, "Content-Type": "application/json", "Prefer": "return=minimal"}


def fetch_all(filter_q):
    out = []
    off = 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/nova_base?{filter_q}&offset={off}&limit=1000",
                      headers=H, timeout=60)
        d = r.json()
        if not isinstance(d, list):
            print("ERR", d); return out
        out += d
        if len(d) < 1000: break
        off += 1000
    return out


def main():
    apply = "--apply" in sys.argv
    # 1. Mapa PEP_base -> (cliente, vertical) dominantes em fontes que NAO sao Orange
    nonorange = fetch_all("select=pep_base,nome_cliente,vertical&fonte=neq.base Orange")
    print(f"Non-orange rows: {len(nonorange)}")
    pep_cli = collections.defaultdict(collections.Counter)
    pep_vert = collections.defaultdict(collections.Counter)
    for x in nonorange:
        p = str(x.get("pep_base") or "").strip()
        c = str(x.get("nome_cliente") or "").strip()
        v = str(x.get("vertical") or "").strip()
        if p and c: pep_cli[p][c] += 1
        if p and v: pep_vert[p][v] += 1
    print(f"PEPs com cliente: {len(pep_cli)}")
    print(f"PEPs com vertical: {len(pep_vert)}")

    # 2. Orange
    oranges = fetch_all("select=id,pep_base,nome_cliente,vertical&fonte=eq.base Orange")
    print(f"Orange rows: {len(oranges)}")

    # 3. Construir updates por (cliente_canonico, vertical_canonico)
    # Agrupa ids que recebem o mesmo cliente/vertical pra reduzir PATCHes
    upd = collections.defaultdict(list)  # (cliente, vertical) -> [ids]
    matched = 0
    for x in oranges:
        if x.get("nome_cliente"):  # ja tem
            continue
        p = str(x.get("pep_base") or "").strip()
        if not p: continue
        c = pep_cli.get(p)
        v = pep_vert.get(p)
        if not c and not v: continue
        cli = c.most_common(1)[0][0] if c else None
        ver = v.most_common(1)[0][0] if v else None
        upd[(cli, ver)].append(x["id"])
        matched += 1
    print(f"Orange a receber cliente via PEP: {matched}")
    print(f"Grupos (cliente, vertical) distintos: {len(upd)}")

    if not apply:
        print("\n[DRY-RUN] use --apply pra efetivar")
        # mostra top
        tops = sorted(upd.items(), key=lambda kv:-len(kv[1]))[:10]
        for (c,v), ids in tops:
            print(f"  {len(ids):4d}  cliente={c!r:40s} vert={v!r}")
        return

    done = 0
    for (cli, ver), ids in upd.items():
        body = {}
        if cli: body["nome_cliente"] = cli
        if ver: body["vertical"] = ver
        if not body: continue
        for i in range(0, len(ids), 200):
            chunk = ids[i:i+200]
            idlist = ",".join(str(x) for x in chunk)
            r = httpx.patch(f"{URL}/rest/v1/nova_base?id=in.({idlist})",
                            headers=HP, json=body, timeout=60)
            if r.status_code >= 300:
                print(f"ERRO: {r.status_code} {r.text[:300]}"); return
            done += len(chunk)
    print(f"OK: {done} linhas Orange populadas com cliente/vertical")


if __name__ == "__main__":
    main()

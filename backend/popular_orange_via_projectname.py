"""Popula nome_cliente nas linhas Base Orange SEM cliente extraindo do
project_name (coluna `tipos`). Formato: <PEP> - <CLIENTE/CONTEXTO> - <sub>.

Casos internos (Hyper, ND, SGA, etc — overhead nao-cliente) sao mantidos None.
"""
import sys, io, collections, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx
from _supabase_creds import load_creds

URL, KEY = load_creds()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
HP = {**H, "Content-Type": "application/json", "Prefer": "return=minimal"}

# Internos (nao-cliente). Esses ficam sem nome_cliente.
INTERNOS = {
    "Hyper", "ND", "SGA", "CG", "DOJO", "Symphony", "Play Studio",
    "Dojo Labs", "Sistemas Internos FC", "Managed Services",
    "INATIVO_Alocação", "ND  Férias Feriado Ausencia Licença C",
    "Demanda judicial _caneta emagrecedora",
}

# Mapeamento extraido -> canonico (usa nomes que ja existem na base ou casam
# com NOME_CLIENTE_ALIAS).
CANON = {
    "BTG": "BANCO BTG",
    "Alocação BV": "BANCO VOTORANTIM S.A.",
    "GCB": "GRUPO CASAS BAHIA S.A.",
    "Odontoprev": "ODONTOPREV S.A.",
    "ESTAPAR": "ESTAPAR",
    "AMBIPAR": "AMBIPAR",
    "MULTIPLAN": "MULTIPLAN",
    "EUROFARMA": "EUROFARMA",
    "BUNZL": "BUNZL",
    "Eurofarma": "EUROFARMA",
    "Bunzl": "BUNZL",
}


def parse_cli(tipos: str) -> str | None:
    if not tipos:
        return None
    t = re.sub(r"^[A-Z0-9]+\.\d+\.\d+\s*-\s*", "", tipos)
    parts = [p.strip() for p in t.split(" - ")]
    if not parts:
        return None
    cli = parts[0]
    # Codigo "numero_CLIENTE_descricao"
    m = re.match(r"^\d+_([A-Z][A-Z0-9]+)(?:_|$)", cli)
    if m:
        return m.group(1)
    return cli


def fetch_orange():
    out = []
    off = 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/nova_base?select=id,tipos,nome_cliente&fonte=eq.base Orange&offset={off}&limit=1000",
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
    rows = fetch_orange()
    print(f"Orange total: {len(rows)}")
    sem_cli = [x for x in rows if not (x.get("nome_cliente") or "").strip()]
    print(f"Orange SEM cliente: {len(sem_cli)}")

    # agrupa ids por (cliente_destino) — preserva o nome cru extraido se nao
    # tiver mapeamento canonico
    upd = collections.defaultdict(list)
    stats = collections.Counter()
    for x in sem_cli:
        raw = parse_cli(str(x.get("tipos") or ""))
        if not raw:
            stats["sem_parse"] += 1
            continue
        if raw in INTERNOS:
            stats["interno"] += 1
            continue
        canon = CANON.get(raw, raw)
        upd[canon].append(x["id"])
        stats["a_atualizar"] += 1

    print(f"\nDistribuicao:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\nClientes a aplicar ({len(upd)}):")
    for c, ids in sorted(upd.items(), key=lambda kv: -len(kv[1]))[:30]:
        print(f"  {len(ids):4d}  {c!r}")

    if not apply:
        print("\n[DRY-RUN] use --apply pra efetivar")
        return

    done = 0
    for c, ids in upd.items():
        for i in range(0, len(ids), 200):
            chunk = ids[i:i+200]
            idlist = ",".join(str(x) for x in chunk)
            r = httpx.patch(f"{URL}/rest/v1/nova_base?id=in.({idlist})",
                            headers=HP, json={"nome_cliente": c}, timeout=60)
            if r.status_code >= 300:
                print(f"ERRO: {r.status_code} {r.text[:300]}"); return
            done += len(chunk)
    print(f"\nOK: {done} linhas atualizadas")


if __name__ == "__main__":
    main()

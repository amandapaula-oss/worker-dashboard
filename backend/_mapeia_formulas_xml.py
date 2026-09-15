# -*- coding: utf-8 -*-
"""Le as abas P&L FCamara's e (2) direto do XML do xlsx (o arquivo tem 9 MB e 60 abas;
abrir pelo openpyxl duas vezes demora minutos). Mostra formula E ultimo valor calculado
de cada celula, destacando erros, plugs e somas que batem em celula vazia.
"""
import os, re, sys, zipfile
import xml.etree.ElementTree as ET

SCR = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
       r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b\scratchpad')
ARQ = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCR, 'pl_jun26_1456.xlsx')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NSR = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
ALVO = ["P&L FCamara's", "P&L FCamara's (2)"]

z = zipfile.ZipFile(ARQ)
wb = ET.fromstring(z.read('xl/workbook.xml'))
rels = {r.get('Id'): r.get('Target') for r in
        ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
abas = {}
for sh in wb.find(f'{NS}sheets'):
    alvo = rels.get(sh.get(f'{NSR}id'), '')
    abas[sh.get('name')] = 'xl/' + alvo.lstrip('/').replace('xl/', '', 1) if not alvo.startswith('xl/') else alvo

# strings compartilhadas (para ler rotulos)
shared = []
if 'xl/sharedStrings.xml' in z.namelist():
    for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
        shared.append(''.join(t.text or '' for t in si.iter(f'{NS}t')))


def celulas(path):
    """coordenada -> (formula, valor, tipo)"""
    out = {}
    for c in ET.fromstring(z.read(path)).iter(f'{NS}c'):
        ref, t = c.get('r'), c.get('t')
        f = c.find(f'{NS}f')
        vv = c.find(f'{NS}v')
        val = vv.text if vv is not None else None
        if t == 's' and val is not None:
            try:
                val = shared[int(val)]
            except (ValueError, IndexError):
                pass
        out[ref] = ('=' + (f.text or '') if f is not None and f.text else None, val, t)
    return out


def col(ref):
    return re.match(r'([A-Z]+)', ref).group(1)


def lin(ref):
    return int(re.search(r'(\d+)', ref).group(1))


for aba in ALVO:
    if aba not in abas:
        print(f'!! aba nao encontrada: {aba}')
        continue
    cel = celulas(abas[aba])
    rot = {}
    for ref, (f, v, t) in cel.items():
        if col(ref) in ('A', 'B') and t == 's' and v:
            rot.setdefault(lin(ref), v)
    print(f'\n{"=" * 76}\n{aba}   ({len(cel)} celulas)\n{"=" * 76}')

    print('--- ERROS (#REF!, #VALUE!, #DIV/0!) ---')
    n = 0
    for ref, (f, v, t) in sorted(cel.items(), key=lambda x: (lin(x[0]), col(x[0]))):
        if t == 'e' or (isinstance(v, str) and v.startswith('#')):
            print(f'   {ref:>7} {str(v):>9}  = {str(f)[:56]:56} [{str(rot.get(lin(ref), ""))[:22]}]')
            n += 1
            if n >= 25:
                print('   ...'); break
    if not n:
        print('   (nenhum)')

    print('--- SOMA que inclui celula VAZIA (o total sai errado) ---')
    achou = 0
    for ref, (f, v, t) in sorted(cel.items(), key=lambda x: (lin(x[0]), col(x[0]))):
        if not f or not re.fullmatch(r'=[A-Z]+\d+([+\-][A-Z]+\d+)+', f.replace(' ', '')):
            continue
        refs = re.findall(r'[A-Z]+\d+', f)
        vazias = [x for x in refs if x not in cel or cel[x][1] in (None, '')]
        if vazias and len(vazias) < len(refs):
            print(f'   {ref:>7} = {f[:40]:40} -> {str(v)[:14]:14} vazias: {", ".join(vazias[:4])}  [{str(rot.get(lin(ref), ""))[:20]}]')
            achou += 1
    if not achou:
        print('   (nenhuma)')

    print('--- PLUG: numero cravado dentro da formula ---')
    achou = 0
    for ref, (f, v, t) in sorted(cel.items(), key=lambda x: (lin(x[0]), col(x[0]))):
        if f and re.search(r'=\s*\d{4,}[\d.,]*\s*[*+\-/]', f):
            print(f'   {ref:>7} = {f[:50]:50} -> {str(v)[:14]}  [{str(rot.get(lin(ref), ""))[:20]}]')
            achou += 1
    if not achou:
        print('   (nenhum)')

    print('--- NUMERO CRAVADO onde a linha tem formulas ---')
    porlinha = {}
    for ref, (f, v, t) in cel.items():
        if col(ref) in ('A', 'B'):
            continue
        porlinha.setdefault(lin(ref), []).append((ref, f, v, t))
    for L in sorted(porlinha):
        itens = porlinha[L]
        comf = [x for x in itens if x[1]]
        crav = [x for x in itens if not x[1] and x[3] != 's' and x[2] not in (None, '', '0')]
        if len(comf) >= 3 and crav:
            for ref, f, v, t in sorted(crav, key=lambda x: col(x[0]))[:4]:
                try:
                    fv = f'{float(v):,.2f}'
                except (TypeError, ValueError):
                    fv = str(v)[:16]
                print(f'   {ref:>7} = {fv:>18}  (a linha tem {len(comf)} formulas)  [{str(rot.get(L, ""))[:26]}]')
z.close()

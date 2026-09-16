# -*- coding: utf-8 -*-
"""Dump rapido (via XML) das abas de receita, marcando quais celulas sao formula —
para separar linha de TOTAL de linha de DETALHE antes de extrair."""
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

DIR = os.path.dirname(os.path.abspath(__file__))
PL = os.path.join(DIR, '2026 dados', 'FCamara - P&L Gerencial - jun26 v2.xlsx')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NSR = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

z = zipfile.ZipFile(PL)
wbx = ET.fromstring(z.read('xl/workbook.xml'))
rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
paths = {}
for sh in wbx.find(f'{NS}sheets'):
    t = rels.get(sh.get(f'{NSR}id'), '')
    paths[sh.get('name')] = t if t.startswith('xl/') else 'xl/' + t.lstrip('/')
shared = []
if 'xl/sharedStrings.xml' in z.namelist():
    for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
        shared.append(''.join(t.text or '' for t in si.iter(f'{NS}t')))


def colnum(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


def dump(aba, nlin, ncol):
    print(f'\n{"=" * 74}\n{aba}\n{"=" * 74}')
    grade = {}
    for c in ET.fromstring(z.read(paths[aba])).iter(f'{NS}c'):
        ref = c.get('r')
        m = re.match(r'([A-Z]+)(\d+)', ref)
        col, lin = colnum(m.group(1)), int(m.group(2))
        if lin > nlin or col > ncol:
            continue
        t = c.get('t')
        f = c.find(f'{NS}f')
        vv = c.find(f'{NS}v')
        val = vv.text if vv is not None else None
        if t == 's' and val is not None:
            try:
                val = shared[int(val)]
            except (ValueError, IndexError):
                pass
        if val is None and f is None:
            continue
        if t not in ('s', 'str', 'e') and val is not None:
            try:
                x = float(val)
                val = f'{x:,.0f}' if abs(x) > 1000 else f'{x:,.2f}'
                if 40000 < x < 60000:            # provavel data serial
                    import datetime
                    val += '=' + (datetime.date(1899, 12, 30) +
                                  datetime.timedelta(days=int(x))).strftime('%b/%y')
            except ValueError:
                pass
        s = str(val)[:17]
        if f is not None:
            s += '~'
        grade[(lin, col)] = s
    for lin in range(1, nlin + 1):
        linha = [grade.get((lin, c), '') for c in range(1, ncol + 1)]
        if any(x.strip() for x in linha):
            print(f'  r{lin:>2}|' + '|'.join(f'{x:>18}' for x in linha))


if __name__ == '__main__':
    alvo = sys.argv[1] if len(sys.argv) > 1 else 'todas'
    tudo = [('Licensing Hyper', 22, 11), ('Play', 28, 17),
            ('Sales Boost', 20, 13), ('Licensing Msf', 38, 9)]
    for aba, nl, nc in tudo:
        if alvo in ('todas', aba):
            dump(aba, nl, nc)
z.close()

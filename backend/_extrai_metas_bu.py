# -*- coding: utf-8 -*-
"""Extrai os CSVs de backend/_metas_bu/ a partir das planilhas de Apuracao por BU.

Esse extrator nao existia no repositorio: os CSVs de 14/09 vieram de um script perdido.
Ele le o mesmo layout que as planilhas ja' tinham: na linha 3 de cada aba ha' um bloco
por trimestre (Q1Y26, Q2Y26, Q3Y26, Q4Y26 e ANUAL), cada um comecando numa coluna
rotulada "Periodo" e com 13 colunas:

  Periodo | BU | Avaliado | Posicao | Meta(nome da metrica) | Peso Meta | Realizado |
  Meta(valor) | Trigger Min | Atingimento | Salario | Quantidade | Apuracao

Uso:  python _extrai_metas_bu.py            (usa os arquivos - 18.09)
      python _extrai_metas_bu.py --originais (usa os originais do Yuri)
Depois rode _gera_metas_detalhe_json.py.
"""
import csv
import os
import shutil
import sys
import tempfile

import openpyxl

P = (r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA'
     r'\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais')
DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DIR, '_metas_bu')
ORIG = '--originais' in sys.argv

# (bu, arquivo novo, arquivo original, nome do csv)
ARQUIVOS = [
    ('Finance', r'Finance\Apuração Meta Finance (AE) - 18.09.xlsx',
     r'Finance\Apuração Meta Finance (AE) OFICIAL.xlsx', 'finance_ae'),
    ('Finance', r'Finance\Apuração Meta Finance (DIRETOR) - 18.09.xlsx',
     r'Finance\Apuração Meta Finance (DIRETOR).xlsx', 'finance_diretor'),
    ('Health', r'Health\Apuração Meta 2026 Health - 18.09.xlsx',
     r'Health\Apuração Meta 2026 Health OFICIAL.xlsx', 'health'),
    ('Grupo Mult', r'Grupo Mult\Apuração Meta Grupo Mult - 18.09.xlsx',
     r'Grupo Mult\Apuração Meta Grupo Mult Oficial.xlsx', 'grupomult'),
    ('Multisector', r'Multisector\Apuração Meta Multisector - 18.09.xlsx',
     r'Multisector\Apuração Meta Multisector OFICIAL V3.xlsx', 'multisector'),
    ('Retail', r'Retail\Apuração Meta Retail (AE) - 18.09.xlsx',
     r'Retail\Apuração Meta Retail  (AE) OFICIAL.xlsx', 'retail_ae'),
    ('Retail', r'Retail\Apuração Meta Retail (diretor) - 18.09.xlsx',
     r'Retail\Apuração Meta Retail  (diretor) Oficial2.xlsx', 'retail_diretor'),
]
ABAS = {'AE', 'DIRETOR', 'AE G MULT', 'DIRETOR (oculta)', 'Comparativo QoQ'}
# nome da metrica na planilha -> chave usada no JSON
METRICA = {
    'receita total': 'receita',
    'mb%': 'mb',
    'lb': 'lb',
    'mc%': 'mc',
    'receita next gen': 'outra:receita_next_gen',
    'receita nextgen': 'outra:receita_next_gen',
    'receita ecossistema': 'outra:receita_ecossistema',
    'total': 'outra:total',
    'trigger lb': 'outra:trigger_lb',
    'trigger mc': 'outra:trigger_mc',
}
NOTA_TRIGGER = 'linha de gatilho: LB minimo p/ pagar bonus (sem peso)'


def num(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return ''
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        return ''


def periodo_rotulo(v):
    s = str(v).strip()
    return 'ANUAL' if s in ('2026', '2026.0', 'ANUAL') else s


def blocos(ws):
    """Cabecalhos de bloco: (linha, coluna) de cada celula 'Periodo'. As abas empilham
    VARIOS grupos verticalmente (ex: Multisector tem um grupo na linha 3 e outro na 33),
    entao nao da' pra procurar so' na linha 3."""
    out = []
    for rn in range(1, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            if str(ws.cell(rn, c).value or '').strip().lower() == 'periodo':
                out.append((rn, c))
    return out


def cols_bloco(ws):
    """so' as colunas, para quem precisa medir proximidade"""
    return sorted({c for _, c in blocos(ws)})


def extrai(ws, bu, arquivo):
    linhas, clientes = [], []
    for r0, c0 in blocos(ws):
        for rn in range(r0 + 1, ws.max_row + 1):
            if str(ws.cell(rn, c0).value or '').strip().lower() == 'periodo':
                break                      # comecou o proximo grupo
            per = ws.cell(rn, c0).value
            aval = ws.cell(rn, c0 + 2).value
            met = ws.cell(rn, c0 + 4).value
            if not aval or not met:
                continue
            chave = METRICA.get(str(met).strip().lower())
            if not chave:
                continue
            ap = num(ws.cell(rn, c0 + 12).value)
            obs = ''
            if chave == 'outra:total' and ap != '':
                obs = f'apuracao={ap}'
            elif chave.startswith('outra:trigger'):
                obs = NOTA_TRIGGER
            linhas.append({
                'bu': bu, 'arquivo': arquivo, 'aba': ws.title,
                'avaliado': str(aval).strip(),
                'posicao': str(ws.cell(rn, c0 + 3).value or '').strip(),
                'trimestre': periodo_rotulo(per), 'metrica': chave,
                'meta': num(ws.cell(rn, c0 + 7).value),
                'realizado': num(ws.cell(rn, c0 + 6).value),
                'atingimento': num(ws.cell(rn, c0 + 9).value),
                'peso': num(ws.cell(rn, c0 + 5).value),
                'trigger': num(ws.cell(rn, c0 + 8).value),
                'obs': obs,
            })
    return linhas, clientes



def extrai_clientes(ws, bu):
    """O rotulo "Clientes Considerados" aparece numa coluna proxima do bloco; os nomes
    vem logo abaixo. Liga ao bloco cuja coluna inicial estiver mais perto, e ao avaliado
    daquele bloco."""
    cols = cols_bloco(ws)
    if not cols:
        return []
    out = []
    for rn in range(1, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(rn, c).value
            if not (isinstance(v, str) and 'clientes considerad' in v.lower()):
                continue
            c0 = min(cols, key=lambda x: abs(x - c))
            per = aval = None
            for k in range(rn - 1, 0, -1):
                if ws.cell(k, c0).value and ws.cell(k, c0 + 2).value:
                    per = periodo_rotulo(ws.cell(k, c0).value)
                    aval = str(ws.cell(k, c0 + 2).value).strip()
                    break
            if not per or not aval:
                continue
            for k in range(rn + 1, ws.max_row + 1):
                nome = ws.cell(k, c).value
                if not nome or not str(nome).strip():
                    break
                out.append({'bu': bu, 'avaliado': aval, 'trimestre': per,
                            'cliente': str(nome).strip()})
    return out


KPI = {'receita': 'receita', 'mb%': 'mb', 'lb': 'lb', 'mc%': 'mc'}


def extrai_qoq(ws, bu, arquivo):
    """Aba "Comparativo QoQ": uma linha por avaliado x KPI, colunas por trimestre.
    Sao METAS por trimestre (visao de referencia), nao realizados."""
    cab = None
    for rn in range(1, min(ws.max_row, 8) + 1):
        if any(str(ws.cell(rn, c).value or '').strip().upper().startswith('Q')
               and len(str(ws.cell(rn, c).value or '').strip()) == 5
               for c in range(1, ws.max_column + 1)):
            cab = rn
            break
    if cab is None:
        return []
    per_col = {}
    for c in range(1, ws.max_column + 1):
        t = str(ws.cell(cab, c).value or '').strip()
        if len(t) == 5 and t.upper().startswith('Q') and t.upper().endswith('Y26'):
            per_col.setdefault(t.upper(), c)
    out = []
    for rn in range(cab + 1, ws.max_row + 1):
        aval = ws.cell(rn, 3).value
        kpi = KPI.get(str(ws.cell(rn, 5).value or '').strip().lower())
        if not aval or not kpi:
            continue
        for per, c in per_col.items():
            v = num(ws.cell(rn, c).value)
            if v == '':
                continue
            out.append({'bu': bu, 'arquivo': arquivo, 'aba': ws.title,
                        'avaliado': str(aval).strip(),
                        'posicao': str(ws.cell(rn, 4).value or '').strip(),
                        'trimestre': per, 'metrica': kpi, 'meta': v, 'realizado': '',
                        'atingimento': '', 'peso': '', 'trigger': '',
                        'obs': 'meta do trimestre (Comparativo QoQ)'})
    return out

COLS = ['bu', 'arquivo', 'aba', 'avaliado', 'posicao', 'trimestre', 'metrica',
        'meta', 'realizado', 'atingimento', 'peso', 'trigger', 'obs']
print(f'extraindo dos arquivos {"ORIGINAIS do Yuri" if ORIG else "- 18.09"}\n')
tot_l = tot_c = 0
for bu, novo, velho, nome in ARQUIVOS:
    rel = velho if ORIG else novo
    src = os.path.join(P, rel)
    if not os.path.exists(src):
        print(f'!! nao achei: {rel}')
        continue
    tmp = os.path.join(tempfile.gettempdir(), '_ex_' + os.path.basename(rel))
    shutil.copy2(src, tmp)                 # o arquivo pode estar aberto no Excel
    wb = openpyxl.load_workbook(tmp, data_only=True)
    L, C = [], []
    for aba in wb.sheetnames:
        nome_aba = aba.strip()
        if nome_aba == 'Comparativo QoQ':
            L += extrai_qoq(wb[aba], bu, os.path.basename(rel))
        elif nome_aba in ABAS:
            a, _ = extrai(wb[aba], bu, os.path.basename(rel))
            L += a
            C += extrai_clientes(wb[aba], bu)
    wb.close()
    with open(os.path.join(OUT, nome + '.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter=';')
        w.writeheader()
        w.writerows(L)
    with open(os.path.join(OUT, nome + '_clientes.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['bu', 'avaliado', 'trimestre', 'cliente'], delimiter=';')
        w.writeheader()
        w.writerows(C)
    abas = sorted({x['aba'] for x in L})
    print(f'{nome:16} {len(L):>4} metricas | {len(C):>4} clientes | abas: {abas}')
    tot_l += len(L)
    tot_c += len(C)
print(f'\nTOTAL: {tot_l} linhas de metrica, {tot_c} de cliente')

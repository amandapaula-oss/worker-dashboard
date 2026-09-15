# -*- coding: utf-8 -*-
"""Reparo do P&L — versao final. A diferenca das anteriores esta na GRAVACAO:
escreve uma coluna por vez, em blocos de 500 linhas, como matriz N x 1. Escrever
a matriz 2838 x 4 de uma vez desalinhava os valores (cliente caia na coluna da BU).
Ao final reabre o arquivo salvo e confere de verdade.
"""
import csv
import os
import re
import unicodedata
from collections import Counter

import win32com.client as win32

DIR = os.path.dirname(os.path.abspath(__file__))
SCR = (r'C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude'
       r'\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b\scratchpad')
BASE = os.path.join(SCR, 'pl_jun26_1456.xlsx')      # parte sempre do arquivo limpo
SAIDA = os.path.join(SCR, 'pnl_corrigido.xlsx')
CSV = os.path.join(DIR, '_depara_pj.csv')
COLS = ['E', 'F', 'G']
LINHAS_BU = [37, 52, 67, 82, 98]


def npn(v):
    v = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().upper()
    return ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', v).split())


def cpfd(v):
    d = re.sub(r'\D', '', str(v or ''))
    return d[-11:].zfill(11) if len(d) >= 9 else ''


por_cpf, por_nome = {}, {}
with open(CSV, encoding='utf-8-sig') as f:
    for r in csv.DictReader(f, delimiter=';'):
        v = (r['cliente'], r['bu'], r['projeto'], r['profit_center'])
        if r['cpf']:
            por_cpf[(r['cpf'], r['competencia'])] = v
        if r['nome']:
            por_nome[(r['nome'], r['competencia'])] = v

excel = win32.DispatchEx('Excel.Application')
excel.Visible = False
excel.DisplayAlerts = False
excel.AskToUpdateLinks = False
excel.EnableEvents = False
try:
    if os.path.exists(SAIDA):
        os.remove(SAIDA)
    wb = excel.Workbooks.Open(BASE, 0, False)
    excel.Calculation = -4135
    pj = wb.Worksheets('PJs')
    # a aba tem AutoFilter com linhas OCULTAS: escrever num range filtrado so
    # preenche as visiveis (foi o que fez a gravacao anterior sair com 18 de 2838)
    if pj.AutoFilterMode:
        try:
            pj.ShowAllData()
            print('filtro da aba PJs: mostrei todas as linhas antes de gravar')
        except Exception as e:
            print('nao consegui limpar o filtro:', e)
    pj.Rows('1:3000').Hidden = False
    ult = pj.Cells(pj.Rows.Count, 1).End(-4162).Row
    for j, t in enumerate(['Cliente (dash)', 'BU (dash)', 'Projeto (dash)', 'Profit Center (dash)']):
        pj.Cells(1, 13 + j).Value = t

    dados = pj.Range(pj.Cells(2, 1), pj.Cells(ult, 8)).Value
    achados, ok = [], 0
    for row in dados:
        comp = row[7]
        per = comp.strftime('%Y-%m') if hasattr(comp, 'strftime') else ''
        hit = por_cpf.get((cpfd(row[0]), per)) or por_nome.get((npn(row[1]), per))
        achados.append(hit if hit else ('', '', '', ''))
        if hit:
            ok += 1
    print(f'aba PJs: {ult} linhas | casou {ok} | sem match {len(achados) - ok}')

    # uma coluna por vez, em blocos — matriz N x 1
    for j in range(4):
        colxl = 13 + j
        for ini in range(0, len(achados), 500):
            bloco = achados[ini:ini + 500]
            matriz = tuple((x[j],) for x in bloco)
            pj.Range(pj.Cells(2 + ini, colxl), pj.Cells(1 + ini + len(bloco), colxl)).Value = matriz
    print('colunas M:P gravadas (uma por vez, blocos de 500)')

    mc = wb.Worksheets('MC por BU')
    molde_bu = ('=-SUMIFS(PJs!$E:$E,PJs!$H:$H,{c}$3,PJs!$N:$N,$B{L},'
                'PJs!$I:$I,"billable",PJs!$G:$G,"<>BR07")')
    molde_pc = ('=-SUMIFS(PJs!$E:$E,PJs!$H:$H,{c}$3,PJs!$I:$I,"billable",'
                'PJs!$G:$G,"<>BR07",PJs!$P:$P,{crit})')
    molde_out = ('=-SUMIFS(PJs!$E:$E,PJs!$H:$H,{c}$3,PJs!$I:$I,"<>billable",'
                 'PJs!$G:$G,"<>BR07")')
    n = 0
    for L in LINHAS_BU:
        for c in COLS:
            mc.Range(f'{c}{L}').Formula = molde_bu.format(c=c, L=L)
            n += 1
    for L, crit in ((141, '$C$137'), (149, '$B$145'), (157, '$C$153')):
        for c in COLS:
            mc.Range(f'{c}{L}').Formula = molde_pc.format(c=c, crit=crit)
            n += 1
    for c in COLS:
        mc.Range(f'{c}171').Formula = molde_out.format(c=c)
        n += 1
    p2 = wb.Worksheets("P&L FCamara's (2)")
    m = 0
    for L in (64, 65, 66, 67, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81):
        cel = p2.Range(f'BK{L}')
        if str(cel.Text).strip() == '#DIV/0!':
            cel.Formula = f'=IFERROR(BD{L}/P{L}-1,"")'
            m += 1
    print(f'formulas: {n} de Custos PJ + {m} variacoes % protegidas')

    excel.Calculation = -4105
    wb.Application.CalculateFullRebuild()
    wb.SaveAs(SAIDA, 51)
    wb.Close(True)

    # ---------- conferencia em abertura limpa ----------
    wb = excel.Workbooks.Open(SAIDA, 0, True)
    pj, mc = wb.Worksheets('PJs'), wb.Worksheets('MC por BU')
    vals = pj.Range(pj.Cells(2, 14), pj.Cells(ult, 14)).Value
    c = Counter(str(v[0] or '(vazio)') for v in vals)
    print('\ncoluna N (BU) na aba PJs:', dict(c.most_common(8)))
    erros = 0
    try:
        erros = mc.UsedRange.SpecialCells(-4123, 16).Count
    except Exception:
        pass
    print(f'celulas com erro na MC por BU: {erros}')
    print("\n=== MC por BU — FCamara's (jan/fev/mar) ===")
    for L in (6, 7, 8, 9):
        print(f'   {mc.Cells(L, 3).Text[:14]:14}' +
              ''.join(f'{mc.Range(f"{cc}{L}").Text[:16]:>18}' for cc in COLS))
    print('\n=== Custos PJ por BU ===')
    for L, nome in ((37, 'Retail'), (52, 'Health'), (67, 'Finance'), (82, 'Multisector'), (98, 'Logistics')):
        print(f'   {nome:12}' + ''.join(f'{mc.Range(f"{cc}{L}").Text[:15]:>17}' for cc in COLS))
    wb.Close(False)
    print('\nOK:', SAIDA)
finally:
    excel.Quit()

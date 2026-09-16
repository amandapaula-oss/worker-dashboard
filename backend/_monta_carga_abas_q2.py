# -*- coding: utf-8 -*-
"""Monta a carga final das abas que faltavam no Q2, a partir do que ja foi extraido
(_abas_faltantes_q2.json), resolvendo duas armadilhas da aba Play:
  - as linhas de TOTAL ("Receita Bruta"/"Receita Líquida") estavam junto do detalhe;
  - cada projeto aparece DUAS vezes, bruto e liquido (razao ~0,9345). Ficamos com o
    LIQUIDO, que e a base do dashboard.
Cada aba e conferida contra o total do proprio P&L antes de virar carga.
Uso: python _monta_carga_abas_q2.py [--apply]
"""
import json
import os
import sys
from collections import defaultdict

DIR = os.path.dirname(os.path.abspath(__file__))
APPLY = '--apply' in sys.argv
Q2 = ['2026-04', '2026-05', '2026-06']
# totais oficiais de cada aba (conferidos no P&L)
OFICIAL = {
    'Licensing Hyper Q2': {'2026-04': 1939374.81, '2026-05': 1036385.58, '2026-06': 640362.16},
    'Play Q2': {'2026-04': 255774.68, '2026-05': 348418.48, '2026-06': 442507.35},
    'Sales Boost Q2': {'2026-04': 144708.28, '2026-05': 79708.28, '2026-06': 79708.28},
    'Licensing Msf Q2': {'2026-04': 310833.94, '2026-05': 371208.95, '2026-06': 292428.18},
}
TOTAIS = ('RECEITA BRUTA', 'RECEITA LIQUIDA', 'RECEITA LÍQUIDA', 'TOTAL', 'TOTAIS', 'MARGEM')

bruto = json.load(open(os.path.join(DIR, '_abas_faltantes_q2.json'), encoding='utf-8'))
linhas = []

for fonte in OFICIAL:
    itens = [x for x in bruto if x['fonte'] == fonte]
    if fonte == 'Play Q2':
        # fator liquido/bruto do proprio mes, tirado das linhas de total da aba
        fator = {}
        for per in Q2:
            b = next((x['valor'] for x in itens if x['periodo'] == per
                      and x['projeto'].strip().upper() == 'RECEITA BRUTA'), 0)
            l = next((x['valor'] for x in itens if x['periodo'] == per
                      and x['projeto'].strip().upper() in ('RECEITA LIQUIDA', 'RECEITA LÍQUIDA')), 0)
            fator[per] = (l / b) if b else 1.0
        # tira os totais; de cada par (projeto, mes) fica o menor (= liquido);
        # projeto que aparece so uma vez esta BRUTO e leva o fator do mes
        itens = [x for x in itens if x['projeto'].strip().upper() not in TOTAIS]
        por_chave = defaultdict(list)
        for x in itens:
            por_chave[(x['projeto'], x['periodo'])].append(x)
        itens = []
        for (proj, per), grupo in por_chave.items():
            if len(grupo) > 1:
                itens.append(min(grupo, key=lambda y: y['valor']))
            else:
                x = dict(grupo[0])
                x['valor'] = round(x['valor'] * fator[per], 2)
                x['obs'] = f'liquido = bruto x {fator[per]:.6f}'
                itens.append(x)
    linhas.extend(itens)

print(f'{"aba":24}{"mes":9}{"extraido":>14}{"oficial P&L":>14}{"dif":>12}')
print('-' * 74)
ok = True
for fonte in OFICIAL:
    for per in Q2:
        s = sum(x['valor'] for x in linhas if x['fonte'] == fonte and x['periodo'] == per)
        of = OFICIAL[fonte][per]
        dif = s - of
        if abs(dif) > 1:
            ok = False
        print(f'{fonte[:24]:24}{per[-2:]:9}{s:>14,.0f}{of:>14,.0f}{dif:>12,.0f}')
print('-' * 74)
tot = sum(x['valor'] for x in linhas)
print(f'{"TOTAL a subir":33}{tot:>14,.0f}   ({len(linhas)} linhas)')
print(f'\nconfere com o P&L: {"SIM" if ok else "NAO — ajustar antes de subir"}')

if not ok:
    print('\n--- nao gravo enquanto nao bater ---')
    # mostra o que esta sobrando/faltando
    for fonte in OFICIAL:
        for per in Q2:
            s = sum(x['valor'] for x in linhas if x['fonte'] == fonte and x['periodo'] == per)
            if abs(s - OFICIAL[fonte][per]) > 1:
                print(f'\n{fonte} {per}: extraido {s:,.2f} x oficial {OFICIAL[fonte][per]:,.2f}')
                for x in sorted([y for y in linhas if y['fonte'] == fonte and y['periodo'] == per],
                                key=lambda y: -y['valor']):
                    print(f'    {x["projeto"][:44] or x["cliente"][:44]:44} {x["valor"]:>12,.2f}')
    raise SystemExit(1)

json.dump(linhas, open(os.path.join(DIR, '_carga_abas_q2.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('salvo _carga_abas_q2.json')

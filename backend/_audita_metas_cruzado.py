# -*- coding: utf-8 -*-
"""Auditoria cruzada: RESUMO (metas_q2.json, visao geral do dash) x blocos das planilhas
por BU (metas_detalhe.json, secao detalhe do dash). Divergencia aqui = o diretor veria
numeros diferentes na mesma pagina."""
import json

q = json.load(open('metas_q2.json', encoding='utf-8'))
d = json.load(open('metas_detalhe.json', encoding='utf-8'))
print('clientes considerados no detalhe:', len(d.get('clientes', [])), 'linhas')

BU_MAP = {'Finance & Insurance': 'Finance', 'Grupo Mult': 'Grupo Mult', 'Multisector': 'Multisector',
          'Health': 'Health', 'Retail': 'Retail'}
ABA_PRIO = {'AE': 0, 'AE G MULT': 1, 'DIRETOR': 2}

def blocos(bu, avaliado, tri):
    cand = [r for r in d['rows'] if r['origem'] == 'bloco' and r['bu'] == bu
            and r['trimestre'] == tri and r['avaliado'].upper() == avaliado.upper()]
    if not cand:
        return {}
    aba = min({r['aba'] for r in cand}, key=lambda a: ABA_PRIO.get(a, 9))
    return {r['metrica']: r for r in cand if r['aba'] == aba}

def cmpv(a, b, tol=0.01):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= max(tol, abs(b) * 1e-6)

divs = []
sem_bloco = []
for tri_key, tri in (('q2', 'Q2Y26'), ('q1', 'Q1Y26')):
    for av in q[tri_key]:
        bu = BU_MAP.get(av['bu'], av['bu'])
        m = blocos(bu, av['avaliado'], tri)
        if not m:
            sem_bloco.append((tri, bu, av['avaliado']))
            continue
        is_dir = (av['posicao'] or '').lower() == 'diretor'
        pares = [
            ('receita realizado', av['receita']['realizado'], m.get('receita', {}).get('realizado')),
            ('receita meta', av['receita']['meta'], m.get('receita', {}).get('meta')),
            ('mb/mc realizado', av['mb']['realizado'], m.get('mc' if is_dir else 'mb', {}).get('realizado')),
            ('mb/mc meta', av['mb']['meta'], m.get('mc' if is_dir else 'mb', {}).get('meta')),
            ('lb/mc realizado', av['lb']['realizado'], m.get('outra:trigger_mc' if is_dir else 'outra:trigger_lb', {}).get('realizado')),
            ('lb/mc meta', av['lb']['meta'], m.get('outra:trigger_mc' if is_dir else 'outra:trigger_lb', {}).get('meta')),
            ('atingimento final', av['atingimento_final'], m.get('outra:total', {}).get('atingimento')),
            ('salario', av['salario'], m.get('outra:total', {}).get('salario')),
            ('bonus', av['apuracao_rs'], m.get('outra:total', {}).get('bonus')),
        ]
        for campo, vr, vb in pares:
            if not cmpv(vr, vb):
                divs.append((tri, bu, av['avaliado'], campo, vr, vb))

print(f'\n=== DIVERGENCIAS RESUMO x PLANILHA-BU: {len(divs)} ===')
for t, bu, nome, campo, vr, vb in divs:
    fr = f'{vr:,.2f}' if isinstance(vr, (int, float)) else str(vr)
    fb = f'{vb:,.2f}' if isinstance(vb, (int, float)) else str(vb)
    print(f'  {t} {bu:12} {nome[:28]:28} {campo:20} RESUMO={fr:>15} BU={fb:>15}')
print(f'\nno RESUMO sem bloco na planilha-BU: {sem_bloco if sem_bloco else "nenhum"}')

# cobertura inversa: quem tem bloco Q2 e nao esta no RESUMO
res_nomes = {(BU_MAP.get(a['bu'], a['bu']), a['avaliado'].upper()) for a in q['q2']}
blk = {(r['bu'], r['avaliado'].upper()) for r in d['rows'] if r['origem'] == 'bloco' and r['trimestre'] == 'Q2Y26'}
extra = blk - res_nomes
print('com bloco Q2 mas FORA do RESUMO:', sorted(extra) if extra else 'nenhum')

import sys
sys.path.append('backend')
from apuracao_engine import calc_bonus_ae
res = calc_bonus_ae('Nicolly Brasil')
print('real_lb_total (from response):', res.get('real_lb_total'))
print('Sum of real_lb in clientes_detalhe:', sum(c['real_lb'] for c in res.get('clientes_detalhe', [])))
for c in res.get('clientes_detalhe', []):
    if c['real_lb'] != round(c['real_rec'] - abs(c['real_custo']), 2):
        print(f"Mismatch in {c['cliente']}: {c['real_lb']} vs {c['real_rec'] - abs(c['real_custo'])}")

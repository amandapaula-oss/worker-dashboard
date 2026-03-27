import sys
sys.path.append('backend')
from apuracao_engine import calc_bonus_ae
res = calc_bonus_ae('Nicolly Brasil')
print("--- Clientes de Nicolly ---")
total_lb = 0
for c in res.get('clientes_detalhe', []):
    print(f"{c['cliente']}: {c['real_lb']}")
    total_lb += c['real_lb']
print(f"Total LB: {total_lb}")

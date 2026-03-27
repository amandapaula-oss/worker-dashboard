import sys
sys.path.append('backend')
from apuracao_engine import calc_bonus_ae
res = calc_bonus_ae('Nicolly Brasil')
detalhe_ws = res.get('detalhe_ws', [])
total_lb_benchmark = 0
for w in detalhe_ws:
    lb_ws = w['real_rec'] * (w['real_mb_pct'] / 100)
    print(f"WS {w['ws']}: LB={lb_ws}")
    total_lb_benchmark += lb_ws
print(f"Total Benchmark LB: {total_lb_benchmark}")

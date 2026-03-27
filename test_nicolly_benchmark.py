import sys
sys.path.append('backend')
from apuracao_engine import calc_bonus_ae
res = calc_bonus_ae('Nicolly Brasil')
print('real_lb_total (financial):', res.get('real_lb_total'))
# Since the backend code has realized_lb_ws but doesn't return it in full except as 'detalhe_ws'
detalhe_ws = res.get('detalhe_ws', [])
bench_lb = sum(w.get('real_rec', 0) * (w.get('real_mb_pct', 0)/100) for w in detalhe_ws)
print('Sum of benchmark-based LB in detalhe_ws:', bench_lb)

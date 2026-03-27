import sys
sys.path.append('backend')
from apuracao_engine import calc_bonus_ae
try:
    res = calc_bonus_ae('Nicolly Brasil')
    print('Gatilho total LB:', res.get('real_lb_total'))
except Exception as e:
    print('Erro:', e)

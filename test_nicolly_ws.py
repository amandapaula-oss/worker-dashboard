import sys, json
sys.path.append('backend')
from apuracao_engine import calc_bonus_ae
res = calc_bonus_ae('Nicolly Brasil')
print(json.dumps(res.get('detalhe_ws', []), indent=2))

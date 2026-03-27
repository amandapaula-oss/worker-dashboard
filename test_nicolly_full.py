import sys, json
sys.path.append('backend')
from apuracao_engine import calc_bonus_ae
res = calc_bonus_ae('Nicolly Brasil')
# remove large detalhe lists for clarity
slim = {k: v for k, v in res.items() if k not in ('detalhe_ws', 'clientes_detalhe')}
print(json.dumps(slim, indent=2))

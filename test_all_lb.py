import sys
sys.path.append('backend')
import pandas as pd
from apuracao_engine import calc_bonus_ae, calc_bonus_diretor, _load_all, norm

d = _load_all()
pessoas = d['pessoas']
for _, row in pessoas.iterrows():
    nome = row['Nome']
    pos = str(row['Posicao']).upper().strip()
    try:
        if pos == 'DIRETOR':
            res = calc_bonus_diretor(nome)
            lb = res.get('real_lb_q4', 0)
        else:
            res = calc_bonus_ae(nome)
            lb = res.get('real_lb_total', 0)
        
        if 1500000 < lb < 1600000:
             print(f"{nome} ({pos}): {lb}")
    except:
        pass
    
print("Check done.")

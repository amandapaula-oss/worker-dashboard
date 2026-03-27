import sys
sys.path.append('backend')
import pandas as pd
from apuracao_engine import _load_all, norm
d = _load_all()
bgt_rec = d['bgt_rec']
pessoa_nome_n = norm('Nicolly Brasil')
rec_ae  = bgt_rec[bgt_rec["ae_q4"].apply(norm) == pessoa_nome_n].copy()
clientes_ae = rec_ae["cliente_norm"].dropna().unique()
print('Clientes AE:', list(clientes_ae))

import sys
sys.path.append('backend')
import pandas as pd
from apuracao_engine import _load_all, norm, _match_cliente
d = _load_all()
pessoa_nome_n = norm('Nicolly Brasil')
bgt_rec = d['bgt_rec']
rec_ae  = bgt_rec[bgt_rec["ae_q4"].apply(norm) == pessoa_nome_n].copy()
clientes_ae = rec_ae["cliente_norm"].dropna().unique()

total_original_lb = 0
for cli_n in clientes_ae:
    orig_lb = _match_cliente(cli_n, d['marg_by_client'])
    total_original_lb += orig_lb
print(f"Total Original LB (from file): {total_original_lb}")

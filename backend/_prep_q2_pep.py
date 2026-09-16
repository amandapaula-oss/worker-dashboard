# -*- coding: utf-8 -*-
"""Carga Q2 no NOSSO formato a partir da 1a aba da Base Unificada v3,
com o PEP preenchido pelas outras abas (Racional Receita / Apontamentos Custo / Formato Metas).
Gera backend/_payload_q2_pep.json (pronto para subir) + relatorio de cobertura.
NAO acessa o banco — roda offline."""
import json, os, re, unicodedata
import pandas as pd

P = r'C:\Users\amanda.paula\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\06. Cockpit - Desenvolvimentos\NewDashboard\Apuração de metas 2 Q\Base Unificada v3.xlsx'
EMP = {'BR02': 'BR02 FCamara', 'BR09': 'BR09 NextGen', 'BR07': 'BR07 Hyper'}
FD = 'Base Unificada v3.xlsx | Racional MB% Q2'
PERS = ('2026-04', '2026-05', '2026-06')

def s(v):
    v = '' if v is None else str(v).strip()
    return None if v in ('', 'nan', 'NaN', 'None', '0') else v

def cpfd(v):
    d = re.sub(r'\D', '', str(v))
    return d[-11:].zfill(11) if len(d) >= 9 else None

def npn(v):
    v = unicodedata.normalize('NFKD', str(v)).encode('ascii', 'ignore').decode().upper().strip()
    return ' '.join(v.split())

def per_of(v):
    d = pd.to_datetime(v, errors='coerce')
    if pd.isna(d):
        n = pd.to_numeric(v, errors='coerce')
        if pd.notna(n):
            d = pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(n))
    return None if pd.isna(d) else d.strftime('%Y-%m')

def pep_ok(v):
    """PEP valido: comeca com BR + digitos (ex.: BR02CLP00086)."""
    v = s(v)
    if not v:
        return None
    v = re.split(r'[;,]| e ', v)[0].strip().upper()
    return v if re.match(r'^BR\d{2}[A-Z]{2,4}\d+', v) else None

# ---------- fontes de PEP ----------
mapa_cpf, mapa_nome, mapa_cli = {}, {}, {}   # (chave, periodo) -> pep

def add(d, k, per, pep):
    if k and per and pep:
        d.setdefault((k, per), {}).setdefault(pep, 0)
        d[(k, per)][pep] += 1

rec = pd.read_excel(P, sheet_name='Racional (Receita)')
rec.columns = [str(c).strip() for c in rec.columns]
for _, r in rec.iterrows():
    per = per_of(r.get('Competência'))
    pep = pep_ok(r.get('PEP')) or pep_ok(r.get('ID PROJETO'))
    add(mapa_cpf, cpfd(r.get('BRCPF')), per, pep)
    add(mapa_nome, npn(r.get('PROFISSIONAL')), per, pep)
    add(mapa_cli, npn(r.get('NOME CLIENTE')), per, pep)
print(f'aba Racional (Receita): {len(rec)} linhas -> {len(mapa_cpf)} chaves CPF-mes')

cus = pd.read_excel(P, sheet_name='Apontamentos de Horas (Custo)')
cus.columns = [str(c).strip() for c in cus.columns]
for _, r in cus.iterrows():
    per = per_of(r.get('Competência'))
    pep = pep_ok(r.get('ID Projeto'))
    add(mapa_cpf, cpfd(r.get('WorkerID')), per, pep)
    add(mapa_nome, npn(r.get('Nome')), per, pep)
    add(mapa_cli, npn(r.get('Cliente Unificado') or r.get('Cliente')), per, pep)
print(f'aba Apontamentos (Custo): {len(cus)} linhas -> {len(mapa_cpf)} chaves CPF-mes (acum.)')

try:
    fm = pd.read_excel(P, sheet_name='Formato Metas')
    fm.columns = [str(c).strip() for c in fm.columns]
    for _, r in fm.iterrows():
        per = s(r.get('periodo'))
        pep = pep_ok(r.get('pep')) or pep_ok(r.get('pep_base'))
        add(mapa_nome, npn(r.get('nome_pessoa')), per, pep)
        add(mapa_cli, npn(r.get('nome_cliente')), per, pep)
        add(mapa_cpf, cpfd(r.get('cpf')), per, pep)
    print(f'aba Formato Metas: {len(fm)} linhas (usada como reforco de PEP)')
except Exception as e:
    print('Formato Metas nao lida:', e)

def melhor(d, k, per):
    v = d.get((k, per))
    return max(v, key=v.get) if v else None

# ---------- aba 1: a base da carga ----------
df = pd.read_excel(P, sheet_name=0)
df.columns = [str(c).strip() for c in df.columns]
df['per'] = df['Competencia'].map(per_of)
fora = df[~df['per'].isin(PERS)]
df = df[df['per'].isin(PERS)].copy()
print(f'\naba 1 (Racional MB% Q2): {len(df)} linhas no Q2 ({len(fora)} fora do Q2, ignoradas)')

# TRAVA DE DEDUPE (16/09/26, revista): a fonte repete linhas INTEIRAS - em abril/26 eram
# 31 grupos, um bloco copiado em ordem espelhada, que entrou dobrado na base (R$ 413.339,28
# a mais). Mas linha identica repetida NEM SEMPRE e' erro: a Transunion tem duas linhas
# iguais de R$ 58.146,46 em maio que, somadas, dao o mesmo Fee mensal de abril e junho -
# e' um Fee partido em duas parcelas, nao uma duplicidade.
# Criterio: so derruba a repeticao quando o total do mes daquele cliente x projeto fica
# FORA da linha dos meses vizinhos, e derrubar aproxima o total da mediana dos vizinhos.
# Sem vizinho para comparar, mantem (e avisa) - errar pra menos apaga receita de verdade.
_antes = len(df)
_dupk = [c for c in df.columns if c != 'per']
_rec = pd.to_numeric(df.get('Receita (Valor Liquido)'), errors='coerce').fillna(0)
_cus = pd.to_numeric(df.get('Custo Alocado'), errors='coerce').fillna(0)
_cli = df['Cliente Unificado'].astype(str).str.strip().str.upper()
_prj = df.get('ID Projeto(s)', pd.Series('', index=df.index)).astype(str).str.strip().str.upper()
_tot_r = _rec.groupby([_cli, _prj, df['per']]).sum()
_tot_c = _cus.groupby([_cli, _prj, df['per']]).sum()
_marca = df.duplicated(subset=_dupk, keep=False)
_tira = []
for _ch, _g in (df[_marca].groupby(_dupk, dropna=False) if _marca.any() else []):
    if len(_g) < 2:
        continue
    _i = list(_g.index)
    _k = (_cli.loc[_i[0]], _prj.loc[_i[0]], df['per'].loc[_i[0]])
    # a linha repetida pode ser de receita ou so de custo; compara na grandeza que ela move
    _rot, _val, _tot = (('receita', _rec, _tot_r) if abs(float(_rec.loc[_i[0]])) > 0.005
                        else ('custo', _cus, _tot_c))
    _uni = float(_val.loc[_i[0]])
    _viz = [v for (c, pj, m), v in _tot.items()
            if c == _k[0] and pj == _k[1] and m != _k[2] and abs(v) > 0.005]
    _com = float(_tot.get(_k, 0))
    _sem = _com - float(_val.loc[_i[1:]].sum())
    if abs(_uni) <= 0.005 or not _viz:
        print(f'   ?? repeticao sem base de comparacao, MANTIDA: {_k[0][:26]} {_k[2]} '
              f'{len(_g)}x {_rot} {_uni:,.2f}')
        continue
    _med = sorted(_viz)[len(_viz) // 2]
    if abs(_sem - _med) < abs(_com - _med):
        _tira += _i[1:]
        print(f'   -- repeticao DERRUBADA: {_k[0][:26]} {_k[2]} {len(_g)}x {_rot} {_uni:,.2f} '
              f'(mes {_com:,.2f} -> {_sem:,.2f}, vizinhos {_med:,.2f})')
    else:
        print(f'   ok repeticao legitima, MANTIDA: {_k[0][:26]} {_k[2]} {len(_g)}x {_rot} '
              f'{_uni:,.2f} (mes {_com:,.2f} x vizinhos {_med:,.2f})')
if _tira:
    df = df.drop(index=_tira)
    print(f'   !! DEDUPE: {_antes - len(df)} linha(s) repetida(s) na fonte foram ignoradas '
          f'(o total do mes so fecha com os vizinhos sem elas)')

# AVISO (nao mexe em nada): a duplicidade de abril/26 NAO era linha repetida - era o valor
# ja dobrado DENTRO de uma unica linha, o que nenhum drop_duplicates pega. O que da' pra
# fazer aqui e' apontar: cliente x projeto cujo mes fica perto do DOBRO dos vizinhos.
for (_c, _pj, _m), _v in _tot_r.items():
    if abs(_v) < 20000:
        continue
    _viz = [x for (c2, p2, m2), x in _tot_r.items()
            if c2 == _c and p2 == _pj and m2 != _m and abs(x) > 0.005]
    if len(_viz) < 2:
        continue
    _med = sorted(_viz)[len(_viz) // 2]
    if _med and 1.8 <= _v / _med <= 2.2:
        print(f'   !! SUSPEITA DE VALOR DOBRADO: {str(_c)[:26]} {_pj[:16]} {_m} '
              f'R$ {_v:,.2f} = {_v/_med:.2f}x a mediana dos outros meses ({_med:,.2f}) '
              f'- conferir na fonte antes de subir')

# ATENCAO: a tabela nova_base NAO tem coluna 'cpf' (o main.py cria essa coluna em memoria,
# no processamento). Mandar 'cpf' no insert quebra com PGRST204.
KEYS = ['fonte', 'fonte_dados', 'periodo', 'empresa', 'pep', 'pep_base', 'nome_pessoa', 'nome_cliente',
        'vertical', 'apuracao_manual', 'tipos', 'receita', 'custo_rateado', 'classificacao']
ap_cli = pd.Series(df[df['apuracao'].notna()].groupby(df['Cliente Unificado'].astype(str))['apuracao']
                   .agg(lambda x: x.mode().iat[0] if len(x.mode()) else None)).to_dict()

rows, orig = [], {'proprio': 0, 'cpf': 0, 'nome': 0, 'cliente': 0, 'sem': 0}
sem_pep_valor = 0.0
for _, r in df.iterrows():
    per = r['per']
    cpf = cpfd(r.get('WorkerID'))
    nome = s(r.get('Nome Unificado')) or s(r.get('Nome (Receita)')) or s(r.get('Nome (Custo x Projeto)'))
    cli = s(r.get('Cliente Unificado'))
    pep = pep_ok(r.get('ID Projeto(s)'))
    if pep:
        orig['proprio'] += 1
    else:
        pep = melhor(mapa_cpf, cpf, per)
        if pep:
            orig['cpf'] += 1
        else:
            pep = melhor(mapa_nome, npn(nome), per)
            if pep:
                orig['nome'] += 1
            else:
                pep = melhor(mapa_cli, npn(cli), per)
                orig['cliente' if pep else 'sem'] += 1
    v_rec = float(pd.to_numeric(r.get('Receita (Valor Liquido)'), errors='coerce') or 0)
    v_cus = float(pd.to_numeric(r.get('Custo Alocado'), errors='coerce') or 0)
    if not pep:
        sem_pep_valor += abs(v_rec) + abs(v_cus)
    ap = s(r.get('apuracao'))
    if ap not in ('NG', 'Ecossistema'):
        ap = ap_cli.get(str(r.get('Cliente Unificado')))
        ap = ap if ap in ('NG', 'Ecossistema') else None
    sm = s(r.get('Status Match')) or ''
    base = {'fonte_dados': FD, 'periodo': per,
            'empresa': EMP.get(str(r.get('Empresa')).strip(), s(r.get('Empresa'))),
            'pep': pep, 'pep_base': pep,
            'nome_pessoa': nome, 'nome_cliente': cli,
            'vertical': ('BU ' + str(r.get('BU')).strip()) if s(r.get('BU')) else None,
            'apuracao_manual': ap, 'tipos': s(r.get('Tipo'))}
    if v_rec != 0:
        x = {k: None for k in KEYS}; x.update(base)
        x['fonte'] = 'racionais'; x['receita'] = round(v_rec, 2)
        rows.append(x)
    if v_cus != 0:
        x = {k: None for k in KEYS}; x.update(base)
        x['fonte'] = 'Base Unificada Q2'; x['custo_rateado'] = round(-abs(v_cus), 2)
        x['classificacao'] = 'despesa' if sm == 'Despesa' else 'custo'
        rows.append(x)

tot = sum(orig.values())
com = tot - orig['sem']
print(f"\n=== COBERTURA DE PEP ({tot} linhas da aba 1) ===")
print(f"  ja tinha na aba 1 : {orig['proprio']:>5}")
print(f"  +CPF x mes        : {orig['cpf']:>5}  (abas Receita/Custo)")
print(f"  +nome x mes       : {orig['nome']:>5}")
print(f"  +cliente x mes    : {orig['cliente']:>5}")
print(f"  ainda SEM pep     : {orig['sem']:>5}  (R$ {sem_pep_valor:,.0f} em receita+custo)")
print(f"  -> cobertura: {com/tot*100:.1f}% (antes: {orig['proprio']/tot*100:.1f}%)")

rr = sum(x['receita'] or 0 for x in rows)
cc = sum(x['custo_rateado'] or 0 for x in rows)
print(f"\npayload: {len(rows)} linhas | receita {rr:,.0f} | custo {cc:,.0f}")
for p in PERS:
    r_ = sum(x['receita'] or 0 for x in rows if x['periodo'] == p)
    c_ = sum(x['custo_rateado'] or 0 for x in rows if x['periodo'] == p)
    print(f"   {p}: receita {r_:>13,.0f} | custo {c_:>13,.0f}")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_payload_q2_pep.json')
json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
print('\nsalvo', out)

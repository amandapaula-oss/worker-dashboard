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

KEYS = ['fonte', 'fonte_dados', 'periodo', 'empresa', 'pep', 'pep_base', 'nome_pessoa', 'nome_cliente',
        'vertical', 'apuracao_manual', 'tipos', 'cpf', 'receita', 'custo_rateado', 'classificacao']
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
            'apuracao_manual': ap, 'tipos': s(r.get('Tipo')),
            'cpf': ('BRCPF' + cpf) if cpf else None}
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

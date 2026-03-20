import pandas as pd, openpyxl, sys
sys.stdout.reconfigure(encoding='utf-8')

path = 'C:/Users/amanda.paula/Downloads/Racional Tentativa yuri.xlsx'

# ── 1. Adiciona em PARA DE PESSOAS ──────────────────────────────────────────
wb = openpyxl.load_workbook(path)
ws = wb['PARA DE PESSOAS']

# Encontra próxima linha vazia na coluna B (Tipo)
next_row = ws.max_row + 1

ws.cell(next_row, 2).value = 'CLT'
ws.cell(next_row, 3).value = 'André Levi Neri Longo'
ws.cell(next_row, 4).value = '50000469'   # ID SAP
ws.cell(next_row, 5).value = None          # CPF desconhecido
ws.cell(next_row, 6).value = 'NextGen'
ws.cell(next_row, 7).value = 50000469      # ID SAP num

# Copia fórmulas das colunas H e I da linha anterior
prev = next_row - 1
for col in [8, 9]:  # H e I
    prev_cell = ws.cell(prev, col)
    if prev_cell.value and str(prev_cell.value).startswith('='):
        # Ajusta referência de linha
        import re
        new_formula = re.sub(
            r'([A-Z]+)' + str(prev),
            lambda m: m.group(1) + str(next_row),
            str(prev_cell.value)
        )
        ws.cell(next_row, col).value = new_formula

wb.save(path)
print(f'Adicionado em PARA DE PESSOAS linha {next_row}')

# ── 2. Adiciona em relacao_pessoas.xlsx ─────────────────────────────────────
rel = pd.read_excel('relacao_pessoas.xlsx')
nova_linha = pd.DataFrame([{
    'Tipo': 'CLT',
    'Nome': 'André Levi Neri Longo',
    'ID SAP': '50000469',
    'CPF / Worker ID': None,
    'Empresa': 'NextGen',
}])
rel = pd.concat([rel, nova_linha], ignore_index=True)
rel.to_excel('relacao_pessoas.xlsx', index=False)
print(f'Adicionado em relacao_pessoas.xlsx (total: {len(rel)} pessoas)')

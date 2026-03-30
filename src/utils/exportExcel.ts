import * as XLSX from "xlsx";

type ColDef = { title?: any; dataIndex?: string; key?: any; children?: ColDef[] };

/** Recursivamente achata colunas agrupadas (com children) em colunas folha. */
function flattenColumns(cols: ColDef[]): { label: string; key: string }[] {
  const result: { label: string; key: string }[] = [];
  for (const col of cols) {
    if (col.children?.length) {
      result.push(...flattenColumns(col.children));
    } else if (col.dataIndex) {
      const label = typeof col.title === "string" ? col.title : String(col.dataIndex);
      result.push({ label, key: String(col.dataIndex) });
    }
  }
  return result;
}

/**
 * Exporta os dados visíveis de uma tabela para xlsx.
 * @param columns  colunas retornadas pelo hook (já filtradas por visibilidade/ordem)
 * @param data     linhas da tabela (sem a linha __total__ se não quiser)
 * @param filename nome do arquivo sem extensão
 */
export function exportTableToExcel(
  columns: ColDef[],
  data: Record<string, any>[],
  filename: string
) {
  if (!data.length) return;
  const headers = flattenColumns(columns);
  if (!headers.length) return;

  const rows = data.map(row => {
    const obj: Record<string, any> = {};
    headers.forEach(h => {
      const v = row[h.key];
      obj[h.label] = v == null ? "" : v;
    });
    return obj;
  });

  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Dados");
  XLSX.writeFile(wb, `${filename}.xlsx`);
}

/** Exporta PLTable (DRE / Streams) cujos dados têm formato {name, values}. */
export function exportPLTableToExcel(
  rows: { name: string; values: Record<string, number> }[],
  columns: string[],
  filename: string
) {
  if (!rows.length) return;
  const data = rows.map(r => {
    const obj: Record<string, any> = { Linha: r.name };
    columns.forEach(c => { obj[c] = r.values[c] ?? ""; });
    return obj;
  });
  const ws = XLSX.utils.json_to_sheet(data);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Dados");
  XLSX.writeFile(wb, `${filename}.xlsx`);
}

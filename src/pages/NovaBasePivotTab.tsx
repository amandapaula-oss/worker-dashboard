import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Table, Spin, Button, Select, Card, Statistic } from "antd";
import { DownloadOutlined, SwapOutlined } from "@ant-design/icons";
import { getNovaBaseFilters, getNovaBasePivot } from "../api";
import { exportTableToExcel } from "../utils/exportExcel";
import { periodoLabel, toTitleCase } from "../utils/format";
import { theme } from "../theme";
import { useNovaBaseFilters } from "../contexts/NovaBaseFilters";

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const DIM_OPTIONS = [
  { value: "periodo",          label: "Período" },
  { value: "empresa",          label: "Empresa" },
  { value: "fonte_familia",    label: "Fonte (família)" },
  { value: "fonte",            label: "Fonte (origem)" },
  { value: "vertical",         label: "BU / Vertical" },
  { value: "apuracao",         label: "Apuração" },
  { value: "no_hierarquia",    label: "Centro de Lucro" },
  { value: "macro_area",       label: "Macro Área" },
  { value: "area",             label: "Área" },
  { value: "tipo_contrato",    label: "Tipo Contrato" },
  { value: "classificacao",    label: "Classificação" },
  { value: "nome_cliente",     label: "Cliente" },
  { value: "pep_base",         label: "PEP" },
  { value: "nome_pessoa",      label: "Pessoa" },
  { value: "centro_lucro",     label: "Centro de Lucro (orig)" },
  { value: "billable_category",label: "Billable" },
];

const METRIC_OPTIONS = [
  { value: "receita",        label: "Receita",         money: true },
  { value: "custo_rateado",  label: "Custo Rateado",   money: true },
  { value: "margem",         label: "Margem",          money: true },
  { value: "horas",          label: "Horas",           money: false },
  { value: "valor_liquido",  label: "Valor Líquido",   money: true },
  { value: "count",          label: "Contagem",        money: false },
];

const AGG_OPTIONS = [
  { value: "sum",   label: "Soma" },
  { value: "avg",   label: "Média" },
  { value: "count", label: "Contagem (linhas)" },
];

const dimLabel = (v: string) => DIM_OPTIONS.find(d => d.value === v)?.label ?? v;

function formatDimValue(field: string, value: any): string {
  if (value === null || value === undefined || value === "") return "(Vazio)";
  const s = String(value);
  if (field === "periodo") return periodoLabel(s);
  if (field === "nome_cliente" || field === "nome_pessoa") return toTitleCase(s);
  return s;
}

export default function NovaBasePivotTab() {
  const [filters, setFilters] = useState<any>({});
  const {
    selPeriodos, setSelPeriodos,
    selEmpresas, setSelEmpresas,
    selFontes, setSelFontes,
    selMacroAreas, setSelMacroAreas,
    selTipos, setSelTipos,
    selClassif, setSelClassif,
    selVerticais, setSelVerticais,
    selApuracoes, setSelApuracoes,
    selNoHier, setSelNoHier,
    resetFilters, hasAnyFilter,
  } = useNovaBaseFilters();

  const [rowDims, setRowDims] = useState<string[]>(["empresa"]);
  const [colDims, setColDims] = useState<string[]>(["periodo"]);
  const [metric, setMetric]   = useState<string>("receita");
  const [agg, setAgg]         = useState<string>("sum");

  const [data, setData]       = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getNovaBaseFilters().then(setFilters).catch(() => {});
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {
      rows: rowDims.join(","),
      cols: colDims.join(","),
      metric, agg,
    };
    if (selPeriodos.length)   params.periodos       = selPeriodos.join(",");
    if (selEmpresas.length)   params.empresas       = selEmpresas.join(",");
    if (selFontes.length)     params.fontes         = selFontes.join(",");
    if (selMacroAreas.length) params.macro_areas    = selMacroAreas.join(",");
    if (selTipos.length)      params.tipos_contrato = selTipos.join(",");
    if (selClassif.length)    params.classificacoes = selClassif.join(",");
    if (selVerticais.length)  params.verticais      = selVerticais.join(",");
    if (selApuracoes.length)  params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)     params.no_hierarquias = selNoHier.join(",");
    getNovaBasePivot(params)
      .then(r => setData(r.data || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [rowDims, colDims, metric, agg, selPeriodos, selEmpresas, selFontes,
      selMacroAreas, selTipos, selClassif, selVerticais, selApuracoes, selNoHier]);

  useEffect(() => { load(); }, [load]);

  const metricDef = METRIC_OPTIONS.find(m => m.value === metric)!;
  const fmt = (v: any): React.ReactNode => {
    const n = Number(v) || 0;
    if (metricDef.money) {
      return <span style={{ color: n < 0 ? "#c0392b" : theme.text }}>{brl(n)}</span>;
    }
    return n.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  };

  // Build pivot table
  const { tableRows, columns, totalsRow, grandTotal } = useMemo(() => {
    if (!data.length) return { tableRows: [], columns: [], totalsRow: null, grandTotal: 0 };

    // No dims: just total
    if (!rowDims.length && !colDims.length) {
      const v = Number(data[0]?._v) || 0;
      return {
        tableRows: [{ key: "t", _label: "Total", _v: v }],
        columns: [
          { title: "", dataIndex: "_label", key: "_label", width: 120, fixed: "left" as const },
          { title: metricDef.label, dataIndex: "_v", key: "_v", align: "right" as const, render: fmt },
        ],
        totalsRow: null, grandTotal: v,
      };
    }

    // Distinct column keys (concatenated values across colDims)
    const colKeySep = " | ";
    const colKeys = new Set<string>();
    for (const r of data) {
      const k = colDims.map(d => formatDimValue(d, r[d])).join(colKeySep);
      colKeys.add(k);
    }
    const colKeyList = Array.from(colKeys).sort();

    // Row map
    const rowMap = new Map<string, any>();
    for (const r of data) {
      const rk = rowDims.map(d => formatDimValue(d, r[d])).join(colKeySep);
      if (!rowMap.has(rk)) {
        const row: any = { key: rk };
        rowDims.forEach(d => { row[d] = formatDimValue(d, r[d]); });
        colKeyList.forEach(ck => { row[`__c__${ck}`] = 0; });
        row.__total__ = 0;
        rowMap.set(rk, row);
      }
      const row = rowMap.get(rk)!;
      const ck = colDims.map(d => formatDimValue(d, r[d])).join(colKeySep);
      const val = Number(r._v) || 0;
      if (colDims.length) {
        row[`__c__${ck}`] = (row[`__c__${ck}`] || 0) + val;
      }
      row.__total__ = (row.__total__ || 0) + val;
    }

    const trows = Array.from(rowMap.values()).sort((a, b) => (b.__total__ || 0) - (a.__total__ || 0));

    // Build column defs
    const cols: any[] = [];
    rowDims.forEach((d, i) => {
      cols.push({
        title: dimLabel(d),
        dataIndex: d,
        key: d,
        width: 160,
        fixed: i === 0 ? ("left" as const) : undefined,
        sorter: (a: any, b: any) => String(a[d] ?? "").localeCompare(String(b[d] ?? ""), "pt-BR"),
      });
    });

    if (colDims.length) {
      colKeyList.forEach(ck => {
        cols.push({
          title: ck,
          dataIndex: `__c__${ck}`,
          key: `__c__${ck}`,
          align: "right" as const,
          width: 130,
          sorter: (a: any, b: any) => (a[`__c__${ck}`] || 0) - (b[`__c__${ck}`] || 0),
          render: (v: any) => fmt(v),
        });
      });
    }

    cols.push({
      title: "Total",
      dataIndex: "__total__",
      key: "__total__",
      align: "right" as const,
      width: 140,
      defaultSortOrder: "descend" as const,
      sorter: (a: any, b: any) => (a.__total__ || 0) - (b.__total__ || 0),
      render: (v: any) => <strong>{fmt(v)}</strong>,
    });

    // Totals row
    const totals: any = { key: "__totals__", _isTotal: true };
    rowDims.forEach((d, i) => { totals[d] = i === 0 ? `TOTAL (${trows.length})` : ""; });
    colKeyList.forEach(ck => {
      totals[`__c__${ck}`] = trows.reduce((s, r) => s + (Number(r[`__c__${ck}`]) || 0), 0);
    });
    totals.__total__ = trows.reduce((s, r) => s + (Number(r.__total__) || 0), 0);

    return {
      tableRows: trows,
      columns: cols,
      totalsRow: totals,
      grandTotal: totals.__total__,
    };
  }, [data, rowDims, colDims, metric, metricDef]);

  const swap = () => { setRowDims(colDims); setColDims(rowDims); };

  const opt = (arr: string[]) => [
    ...(arr || []).map(v => ({ label: v, value: v })),
    { label: "(Vazio)", value: "__blank__" },
  ];

  return (
    <div>
      {/* Configurador */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "1rem 1.2rem", marginBottom: 12, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 2, minWidth: 240 }}>
          <div style={labelStyle}>Linhas</div>
          <Select mode="multiple" style={{ width: "100%" }} value={rowDims}
            onChange={setRowDims} options={DIM_OPTIONS}
            placeholder="Arraste campos para linhas" maxTagCount="responsive" allowClear />
        </div>
        <Button icon={<SwapOutlined />} onClick={swap} title="Inverter linhas/colunas" />
        <div style={{ flex: 2, minWidth: 240 }}>
          <div style={labelStyle}>Colunas</div>
          <Select mode="multiple" style={{ width: "100%" }} value={colDims}
            onChange={setColDims} options={DIM_OPTIONS}
            placeholder="Arraste campos para colunas" maxTagCount="responsive" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <div style={labelStyle}>Valor</div>
          <Select style={{ width: "100%" }} value={metric} onChange={setMetric}
            options={METRIC_OPTIONS.map(m => ({ value: m.value, label: m.label }))} />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Agregação</div>
          <Select style={{ width: "100%" }} value={agg} onChange={setAgg} options={AGG_OPTIONS} />
        </div>
      </div>

      {/* Filtros */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 12, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Período</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
            onChange={setSelPeriodos} options={opt(filters.periodos || [])}
            maxTagCount="responsive" placeholder="Todos" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Empresa</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
            onChange={setSelEmpresas} options={opt(filters.empresas || [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Fonte</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selFontes}
            onChange={setSelFontes} options={opt(filters.fontes || [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>BU</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selVerticais}
            onChange={setSelVerticais} options={opt(filters.verticais || [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Apuração</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selApuracoes}
            onChange={setSelApuracoes} options={opt(filters.apuracoes || [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Centro de Lucro</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selNoHier}
            onChange={setSelNoHier} options={opt(filters.no_hierarquias || [])}
            maxTagCount="responsive" placeholder="Todos" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Macro Área</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selMacroAreas}
            onChange={setSelMacroAreas} options={opt(filters.macro_areas || [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Tipo Contrato</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selTipos}
            onChange={setSelTipos} options={opt(filters.tipos_contrato || [])}
            maxTagCount="responsive" placeholder="Todos" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Classificação</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selClassif}
            onChange={setSelClassif} options={opt(filters.classificacoes || [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        {hasAnyFilter && (
          <Button onClick={resetFilters} danger>Limpar Filtros</Button>
        )}
      </div>

      {/* KPI total */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        <Card style={{ flex: 1, minWidth: 220, borderRadius: 10, border: "1px solid #dde3f0" }}
          styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}>
          <Statistic
            title={<span style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase" }}>
              Total ({AGG_OPTIONS.find(a => a.value === agg)?.label} · {metricDef.label})
            </span>}
            value={metricDef.money ? brl(grandTotal) : grandTotal.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
            valueStyle={{ color: grandTotal < 0 ? "#c0392b" : theme.text, fontSize: "1.4rem", fontWeight: 700 }}
          />
        </Card>
      </div>

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <Table
          dataSource={totalsRow ? [totalsRow, ...tableRows] : tableRows}
          columns={columns}
          size="small"
          pagination={{ defaultPageSize: 50, showSizeChanger: true, pageSizeOptions: ["20", "50", "100", "200", "500"] }}
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={(row: any) => ({ style: row?._isTotal ? { background: "#dce6f7", fontWeight: 700 } : {} })}
          title={() => (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#6b7fa3", fontSize: "0.8rem" }}>
                {tableRows.length} {tableRows.length === 1 ? "linha" : "linhas"}
              </span>
              <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                onClick={() => exportTableToExcel(columns, tableRows, "nova_base_visao_personalizada")}>
                Excel
              </Button>
            </div>
          )}
        />
      )}
    </div>
  );
}

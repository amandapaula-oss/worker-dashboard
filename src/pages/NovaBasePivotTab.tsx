import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Table, Spin, Button, Select, Card, Statistic, Input } from "antd";
import { DownloadOutlined, SwapOutlined, SearchOutlined } from "@ant-design/icons";
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
  { value: "agrupador_pl",     label: "Agrupador P&L" },
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

// "valor_liquido" removido: campo cru poluido (P&L Holding) — nao e metrica valida
type MetricKey = "receita" | "custo_rateado" | "margem" | "horas" | "count";

const METRIC_DEFS: Record<MetricKey, { label: string; money: boolean }> = {
  receita:       { label: "Receita",        money: true },
  custo_rateado: { label: "Custo Rateado",  money: true },
  margem:        { label: "Margem",         money: true },
  horas:         { label: "Horas",          money: false },
  count:         { label: "Contagem",       money: false },
};

const METRIC_OPTIONS = (Object.keys(METRIC_DEFS) as MetricKey[]).map(k => ({
  value: k, label: METRIC_DEFS[k].label,
}));

const AGG_OPTIONS = [
  { value: "sum",   label: "Soma" },
  { value: "avg",   label: "Média" },
  { value: "count", label: "Contagem (linhas)" },
];

const AGRUPADORES_PL = ["Receita", "Custo Direto", "Despesa", "Outros"];

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

  const [selAgrupPL, setSelAgrupPL] = useState<string[]>([]);
  const [rowDims, setRowDims] = useState<string[]>(["empresa"]);
  const [colDims, setColDims] = useState<string[]>(["periodo"]);
  const [selMetrics, setSelMetrics] = useState<MetricKey[]>(["receita", "custo_rateado", "margem"]);
  const [agg, setAgg] = useState<string>("sum");
  const [search, setSearch] = useState<string>("");

  const [data, setData]       = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getNovaBaseFilters().then(setFilters).catch(() => {});
  }, []);

  // Metricas a buscar no backend: tudo exceto margem, e se margem incluida garantir receita+custo
  const backendMetrics = useMemo(() => {
    const set = new Set<string>();
    for (const m of selMetrics) {
      if (m === "margem") { set.add("receita"); set.add("custo_rateado"); }
      else set.add(m);
    }
    if (set.size === 0) set.add("receita");
    return Array.from(set);
  }, [selMetrics]);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {
      rows: rowDims.join(","),
      cols: colDims.join(","),
      metrics: backendMetrics.join(","),
      agg,
    };
    if (search.trim())        params.search         = search.trim();
    if (selPeriodos.length)   params.periodos       = selPeriodos.join(",");
    if (selEmpresas.length)   params.empresas       = selEmpresas.join(",");
    if (selFontes.length)     params.fontes         = selFontes.join(",");
    if (selMacroAreas.length) params.macro_areas    = selMacroAreas.join(",");
    if (selTipos.length)      params.tipos_contrato = selTipos.join(",");
    if (selClassif.length)    params.classificacoes = selClassif.join(",");
    if (selVerticais.length)  params.verticais      = selVerticais.join(",");
    if (selApuracoes.length)  params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)     params.no_hierarquias = selNoHier.join(",");
    if (selAgrupPL.length)    params.agrupadores_pl = selAgrupPL.join(",");
    getNovaBasePivot(params)
      .then(r => setData(r.data || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [rowDims, colDims, backendMetrics, agg, search, selPeriodos, selEmpresas, selFontes,
      selMacroAreas, selTipos, selClassif, selVerticais, selApuracoes, selNoHier, selAgrupPL]);

  useEffect(() => { load(); }, [load]);

  // Pega o valor de uma metrica em uma linha do backend (computa margem aqui)
  const getMetric = (r: any, m: MetricKey): number => {
    if (m === "margem") {
      return (Number(r._v_receita) || 0) + (Number(r._v_custo_rateado) || 0);
    }
    return Number(r[`_v_${m}`]) || 0;
  };

  const fmtCell = (m: MetricKey, v: number): React.ReactNode => {
    const def = METRIC_DEFS[m];
    const n = Number(v) || 0;
    if (def.money) {
      const color = m === "custo_rateado" ? (n < 0 ? "#c0392b" : theme.text)
                  : m === "margem"        ? (n < 0 ? "#c0392b" : "#0a7a3e")
                  : (n < 0 ? "#c0392b" : theme.text);
      const weight = m === "margem" ? 700 : 500;
      return <span style={{ color, fontWeight: weight }}>{brl(n)}</span>;
    }
    return n.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  };

  // Build pivot
  const { tableRows, columns, totalsRow, grandTotals } = useMemo(() => {
    if (!data.length) return { tableRows: [], columns: [], totalsRow: null, grandTotals: {} as Record<MetricKey, number> };

    const metricsActive: MetricKey[] = selMetrics.length ? selMetrics : ["receita"];

    // Sem dimensoes: so total
    if (!rowDims.length && !colDims.length) {
      const r = data[0] || {};
      const row: any = { key: "t", _label: "Total" };
      const totals: Record<string, number> = {};
      metricsActive.forEach(m => {
        const v = getMetric(r, m);
        row[`m_${m}`] = v;
        totals[m] = v;
      });
      const cols: any[] = [{ title: "", dataIndex: "_label", key: "_label", width: 120, fixed: "left" as const }];
      metricsActive.forEach(m => {
        cols.push({
          title: METRIC_DEFS[m].label,
          dataIndex: `m_${m}`, key: `m_${m}`, align: "right" as const, width: 140,
          render: (v: number) => fmtCell(m, v),
        });
      });
      return { tableRows: [row], columns: cols, totalsRow: null, grandTotals: totals as any };
    }

    const sep = " | ";
    const colKeySet = new Set<string>();
    for (const r of data) {
      const k = colDims.length ? colDims.map(d => formatDimValue(d, r[d])).join(sep) : "";
      colKeySet.add(k);
    }
    const colKeyList = Array.from(colKeySet).sort();

    const rowMap = new Map<string, any>();
    for (const r of data) {
      const rk = rowDims.map(d => formatDimValue(d, r[d])).join(sep);
      if (!rowMap.has(rk)) {
        const row: any = { key: rk };
        rowDims.forEach(d => { row[d] = formatDimValue(d, r[d]); });
        colKeyList.forEach(ck => {
          metricsActive.forEach(m => { row[`c_${ck}_m_${m}`] = 0; });
        });
        metricsActive.forEach(m => { row[`total_m_${m}`] = 0; });
        rowMap.set(rk, row);
      }
      const row = rowMap.get(rk)!;
      const ck = colDims.length ? colDims.map(d => formatDimValue(d, r[d])).join(sep) : "";
      metricsActive.forEach(m => {
        const v = getMetric(r, m);
        if (colDims.length) row[`c_${ck}_m_${m}`] = (row[`c_${ck}_m_${m}`] || 0) + v;
        row[`total_m_${m}`] = (row[`total_m_${m}`] || 0) + v;
      });
    }

    // Sort by first metric total desc
    const sortMetric = metricsActive[0];
    const trows = Array.from(rowMap.values()).sort((a, b) =>
      Math.abs(b[`total_m_${sortMetric}`] || 0) - Math.abs(a[`total_m_${sortMetric}`] || 0)
    );

    const cols: any[] = [];
    rowDims.forEach((d, i) => {
      cols.push({
        title: dimLabel(d), dataIndex: d, key: d, width: 180,
        fixed: i === 0 ? ("left" as const) : undefined,
        sorter: (a: any, b: any) => String(a[d] ?? "").localeCompare(String(b[d] ?? ""), "pt-BR"),
      });
    });

    if (colDims.length) {
      colKeyList.forEach(ck => {
        cols.push({
          title: ck,
          children: metricsActive.map(m => ({
            title: METRIC_DEFS[m].label,
            dataIndex: `c_${ck}_m_${m}`,
            key: `c_${ck}_m_${m}`,
            align: "right" as const,
            width: 120,
            sorter: (a: any, b: any) => (a[`c_${ck}_m_${m}`] || 0) - (b[`c_${ck}_m_${m}`] || 0),
            render: (v: any) => fmtCell(m, v),
          })),
        });
      });
    }

    cols.push({
      title: "Total",
      children: metricsActive.map((m, idx) => ({
        title: METRIC_DEFS[m].label,
        dataIndex: `total_m_${m}`,
        key: `total_m_${m}`,
        align: "right" as const,
        width: 130,
        defaultSortOrder: idx === 0 ? ("descend" as const) : undefined,
        sorter: (a: any, b: any) => (a[`total_m_${m}`] || 0) - (b[`total_m_${m}`] || 0),
        render: (v: any) => <strong>{fmtCell(m, v)}</strong>,
      })),
    });

    // Totals row
    const totals: any = { key: "__totals__", _isTotal: true };
    rowDims.forEach((d, i) => { totals[d] = i === 0 ? `TOTAL (${trows.length})` : ""; });
    colKeyList.forEach(ck => {
      metricsActive.forEach(m => {
        totals[`c_${ck}_m_${m}`] = trows.reduce((s, r) => s + (Number(r[`c_${ck}_m_${m}`]) || 0), 0);
      });
    });
    const grand: Record<string, number> = {};
    metricsActive.forEach(m => {
      const t = trows.reduce((s, r) => s + (Number(r[`total_m_${m}`]) || 0), 0);
      totals[`total_m_${m}`] = t;
      grand[m] = t;
    });

    return { tableRows: trows, columns: cols, totalsRow: totals, grandTotals: grand as any };
  }, [data, rowDims, colDims, selMetrics]);

  const swap = () => { setRowDims(colDims); setColDims(rowDims); };

  const opt = (arr: string[]) => [
    ...(arr || []).map(v => ({ label: v, value: v })),
    { label: "(Vazio)", value: "__blank__" },
  ];

  const metricsActive: MetricKey[] = selMetrics.length ? selMetrics : ["receita"];
  const aggLabel = AGG_OPTIONS.find(a => a.value === agg)?.label ?? "Soma";

  return (
    <div>
      {/* Configurador pivot */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "1rem 1.2rem", marginBottom: 12, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 2, minWidth: 240 }}>
          <div style={labelStyle}>Linhas</div>
          <Select mode="multiple" style={{ width: "100%" }} value={rowDims}
            onChange={setRowDims} options={DIM_OPTIONS}
            placeholder="Campos nas linhas" maxTagCount="responsive" allowClear />
        </div>
        <Button icon={<SwapOutlined />} onClick={swap} title="Inverter linhas/colunas" />
        <div style={{ flex: 2, minWidth: 240 }}>
          <div style={labelStyle}>Colunas</div>
          <Select mode="multiple" style={{ width: "100%" }} value={colDims}
            onChange={setColDims} options={DIM_OPTIONS}
            placeholder="Campos nas colunas" maxTagCount="responsive" allowClear />
        </div>
        <div style={{ flex: 2, minWidth: 280 }}>
          <div style={labelStyle}>Valores</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selMetrics}
            onChange={(v) => setSelMetrics(v as MetricKey[])}
            options={METRIC_OPTIONS} maxTagCount="responsive"
            placeholder="Métricas (receita, margem, custo...)" />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Agregação</div>
          <Select style={{ width: "100%" }} value={agg} onChange={setAgg} options={AGG_OPTIONS} />
        </div>
      </div>

      {/* Filtros + busca */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 12, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 2, minWidth: 240 }}>
          <div style={labelStyle}>Busca (cliente, projeto, pessoa, empresa...)</div>
          <Input prefix={<SearchOutlined />} value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Digite e pressione Enter ou aguarde" allowClear />
        </div>
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
        <div style={{ flex: 1, minWidth: 160 }}>
          <div style={labelStyle}>Agrupador P&L</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selAgrupPL}
            onChange={setSelAgrupPL}
            options={AGRUPADORES_PL.map(v => ({ label: v, value: v }))}
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
        {(hasAnyFilter || selAgrupPL.length > 0 || search.trim()) && (
          <Button onClick={() => { resetFilters(); setSelAgrupPL([]); setSearch(""); }} danger>
            Limpar Filtros
          </Button>
        )}
      </div>

      {/* KPI por metrica */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        {metricsActive.map(m => {
          const v = Number((grandTotals as any)[m]) || 0;
          const def = METRIC_DEFS[m];
          const color = m === "custo_rateado" ? (v < 0 ? "#c0392b" : theme.text)
                      : m === "margem"        ? (v < 0 ? "#c0392b" : "#0a7a3e")
                      : (v < 0 ? "#c0392b" : theme.text);
          return (
            <Card key={m} style={{ flex: 1, minWidth: 180, borderRadius: 10, border: "1px solid #dde3f0" }}
              styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}>
              <Statistic
                title={<span style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase" }}>
                  {aggLabel} · {def.label}
                </span>}
                value={def.money ? brl(v) : v.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
                valueStyle={{ color, fontSize: "1.25rem", fontWeight: 700 }}
              />
            </Card>
          );
        })}
      </div>

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <Table
          dataSource={totalsRow ? [totalsRow, ...tableRows] : tableRows}
          columns={columns}
          size="small"
          bordered
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

import React, { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { Select, Table, message, Typography, Card, Statistic, Button, Popover, Checkbox } from "antd";
import { SettingOutlined, DownloadOutlined, FilterOutlined } from "@ant-design/icons";
import { exportTableToExcel } from "../utils/exportExcel";
import TableSkeleton from "../components/TableSkeleton";
import ErrorState from "../components/ErrorState";
import { getMargemFilters, getResumo } from "../api";
import { useDraggableColumns } from "../hooks/useDraggableColumns";
import { toTitleCase, periodoLabel } from "../utils/format";
import { theme } from "../theme";

const { Text } = Typography;

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

function MargemTag({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span style={{ color: "#aaa" }}>—</span>;
  const v = Number(value) * 100;
  const color = v >= 30 ? "#0a7a3e" : v >= 10 ? "#856404" : "#c0392b";
  const bg    = v >= 30 ? "#d4edda" : v >= 10 ? "#fff3cd" : "#fde8e8";
  return (
    <span style={{ background: bg, color, fontWeight: 700, padding: "2px 8px", borderRadius: 4, fontSize: "0.85rem" }}>
      {v.toFixed(1)}%
    </span>
  );
}


export default function ResumoTab({ apenasAtribuidos = false }: { apenasAtribuidos?: boolean }) {
  const [periodos, setPeriodos]               = useState<string[]>([]);
  const [empresas, setEmpresas]               = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas]         = useState<string[]>([]);
  const [categoriasBu, setCategoriasBu]       = useState<string[]>([]);
  const [selCategoriasBu, setSelCategoriasBu] = useState<string[]>([]);
  const [rawData, setRawData]                 = useState<any[]>([]);
  const [loading, setLoading]                 = useState(true);
  const [error, setError]                     = useState(false);
  const [filtersReady, setFiltersReady]       = useState(false);
  const [showFilters, setShowFilters]         = useState(false);
  const initialLoad = useRef(true);

  const loadInitial = useCallback(() => {
    setLoading(true); setError(false);
    const params: Record<string, string> = {};
    if (apenasAtribuidos) params.apenas_atribuidos = "true";
    Promise.all([getMargemFilters(), getResumo(params)])
      .then(([f, d]: [any, any]) => {
        const Q4_PERIODOS = ["2025-10", "2025-11", "2025-12"];
        setPeriodos((f.periodos || []).filter((p: string) => Q4_PERIODOS.includes(p)));
        setEmpresas(f.empresas); setSelEmpresas(f.empresas);
        if (f.categorias_bu?.length) { setCategoriasBu(f.categorias_bu); setSelCategoriasBu(f.categorias_bu); }
        setRawData(d); setFiltersReady(true); initialLoad.current = false;
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { loadInitial(); }, [loadInitial]);

  useEffect(() => {
    if (!filtersReady || initialLoad.current) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selCategoriasBu.length && selCategoriasBu.length < categoriasBu.length) params.categorias_bu = selCategoriasBu.join(",");
    if (apenasAtribuidos) params.apenas_atribuidos = "true";
    getResumo(params)
      .then((d: any) => setRawData(d))
      .catch(() => message.error("Erro ao carregar resumo"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selEmpresas, selCategoriasBu, apenasAtribuidos]);

  // Pivot: empresa × periodo
  const pivotData = useMemo(() => {
    const map = new Map<string, any>();
    for (const r of rawData) {
      const key = r.empresa;
      if (!map.has(key)) map.set(key, { empresa: r.empresa });
      const e = map.get(key)!;
      e[`${r.periodo}_receita`]     = (e[`${r.periodo}_receita`]     || 0) + (Number(r.receita)       || 0);
      e[`${r.periodo}_custo`]       = (e[`${r.periodo}_custo`]       || 0) + (Number(r.custo_rateado) || 0);
      e[`${r.periodo}_margem`]      = (e[`${r.periodo}_margem`]      || 0) + (Number(r.margem)        || 0);
    }
    return Array.from(map.values()).map(r => {
      const tot_rec = periodos.reduce((s, p) => s + (r[`${p}_receita`] || 0), 0);
      const tot_cus = periodos.reduce((s, p) => s + (r[`${p}_custo`]   || 0), 0);
      const tot_mar = periodos.reduce((s, p) => s + (r[`${p}_margem`]  || 0), 0);
      periodos.forEach(p => {
        const rec = r[`${p}_receita`] || 0;
        r[`${p}_margem_pct`] = rec !== 0 ? (r[`${p}_margem`] || 0) / rec : null;
      });
      return {
        ...r,
        total_receita: tot_rec,
        total_custo:   tot_cus,
        total_margem:  tot_mar,
        total_margem_pct: tot_rec !== 0 ? tot_mar / tot_rec : null,
      };
    }).sort((a, b) => b.total_receita - a.total_receita);
  }, [rawData, periodos]);

  // KPI totals
  const totReceita = pivotData.reduce((s, r) => s + (r.total_receita || 0), 0);
  const totCusto   = pivotData.reduce((s, r) => s + (r.total_custo   || 0), 0);
  const totMargem  = pivotData.reduce((s, r) => s + (r.total_margem  || 0), 0);
  const totPct     = totReceita !== 0 ? totMargem / totReceita : 0;

  // Table data with TOTAL row
  const tableData = useMemo(() => {
    const totRow: any = {
      key: "__t__", empresa: "TOTAL",
      total_receita: totReceita, total_custo: totCusto, total_margem: totMargem,
      total_margem_pct: totReceita !== 0 ? totMargem / totReceita : null,
      _isTotal: true,
    };
    periodos.forEach(p => {
      totRow[`${p}_receita`]    = pivotData.reduce((s, r) => s + (r[`${p}_receita`] || 0), 0);
      totRow[`${p}_custo`]      = pivotData.reduce((s, r) => s + (r[`${p}_custo`]   || 0), 0);
      totRow[`${p}_margem`]     = pivotData.reduce((s, r) => s + (r[`${p}_margem`]  || 0), 0);
      const rec = totRow[`${p}_receita`];
      const mar = totRow[`${p}_margem`];
      totRow[`${p}_margem_pct`] = rec !== 0 ? mar / rec : null;
    });
    return [totRow, ...pivotData.map((d, i) => ({ ...d, key: i }))];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pivotData, periodos, totReceita, totCusto, totMargem]);

  const ALL_METRICS = ["receita", "custo", "margem", "margem_pct"] as const;
  type Metric = typeof ALL_METRICS[number];
  const METRIC_LABELS: Record<Metric, string> = { receita: "Receita", custo: "Custo", margem: "Margem", margem_pct: "Margem %" };

  const [visibleMetrics, setVisibleMetrics] = useState<Set<Metric>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("tbl:resumo-metrics") || "null");
      if (Array.isArray(saved)) return new Set(saved as Metric[]);
    } catch {}
    return new Set(ALL_METRICS);
  });

  const toggleMetric = (m: Metric) => {
    setVisibleMetrics(prev => {
      const next = new Set(prev);
      if (next.has(m)) { if (next.size > 1) next.delete(m); }
      else next.add(m);
      localStorage.setItem("tbl:resumo-metrics", JSON.stringify(Array.from(next)));
      return next;
    });
  };

  const columnsDef = useMemo(() => {
    const numCol = (dataIndex: string, render?: (v: any) => React.ReactNode) => ({
      dataIndex, key: dataIndex,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a[dataIndex]) || 0) - (Number(b[dataIndex]) || 0),
      render,
    });

    const allChildren = (prefix: string, bold: boolean) => ([
      {
        ...numCol(`${prefix}_receita`), title: "Receita", width: bold ? 150 : 140,
        render: (v: number) => <span style={{ color: theme.text, fontWeight: bold ? 700 : 600 }}>{brl(v || 0)}</span>,
      },
      {
        ...numCol(`${prefix}_custo`), title: "Custo", width: bold ? 150 : 140,
        render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : theme.text, fontWeight: bold ? 700 : 600 }}>{brl(v || 0)}</span>,
      },
      {
        ...numCol(`${prefix}_margem`), title: "Margem", width: bold ? 150 : 140,
        render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span>,
      },
      {
        ...numCol(`${prefix}_margem_pct`, (v: any) => <MargemTag value={v} />),
        title: "%", width: bold ? 80 : 75,
      },
    ] as const).filter((_, i) => visibleMetrics.has(ALL_METRICS[i]));

    const periodoCols = periodos.map(p => ({
      title: periodoLabel(p),
      key: p,
      children: allChildren(p, false),
    }));

    return [
      {
        title: "Empresa", dataIndex: "empresa", key: "empresa", width: 145,
        fixed: "left" as const,
        sorter: (a: any, b: any) => String(a.empresa).localeCompare(String(b.empresa), "pt-BR"),
        render: (v: string) => toTitleCase(v) || "—",
      },
      ...periodoCols,
      {
        title: "Total",
        key: "__total__",
        children: allChildren("total", true),
      },
    ];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodos, visibleMetrics]);

  const [columns, periodSettings] = useDraggableColumns(columnsDef, "resumo-periodos");

  const metricsSettingsButton = (
    <Popover
      trigger="click"
      placement="bottomRight"
      title="Métricas visíveis"
      content={
        <div style={{ minWidth: 140 }}>
          {ALL_METRICS.map(m => (
            <div key={m} style={{ padding: "3px 0" }}>
              <Checkbox checked={visibleMetrics.has(m)} onChange={() => toggleMetric(m)}>
                {METRIC_LABELS[m]}
              </Checkbox>
            </div>
          ))}
        </div>
      }
    >
      <Button icon={<SettingOutlined />} size="small" type="text" style={{ color: "#6b7fa3" }} title="Métricas visíveis" />
    </Popover>
  );

  return (
    <div>
      {/* Filters */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={selEmpresas.length < empresas.length || selCategoriasBu.length < categoriasBu.length ? "primary" : "default"}
          style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>
      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
              onChange={v => setSelEmpresas(v)}
              options={empresas.map(e => ({ label: e, value: e }))}
              maxTagCount="responsive" />
          </div>
          {categoriasBu.length > 0 && (
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={labelStyle}>BU / Categoria</div>
              <Select mode="multiple" style={{ width: "100%" }} value={selCategoriasBu}
                onChange={v => setSelCategoriasBu(v)}
                options={categoriasBu.map(c => ({ label: c, value: c }))}
                maxTagCount="responsive" />
            </div>
          )}
          <Text type="secondary" style={{ fontSize: "0.78rem", paddingBottom: 2 }}>
            * Custo rateado disponível para out–dez/2025.
          </Text>
        </div>
      )}

      {/* KPI Cards */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        {[
          { label: "Receita Total",  value: `R$ ${totReceita.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`, color: theme.text },
          { label: "Custo Rateado",  value: `R$ ${totCusto.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`,   color: totCusto  < 0 ? "#c0392b" : theme.text },
          { label: "Margem Bruta",   value: `R$ ${totMargem.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`,   color: totMargem < 0 ? "#c0392b" : "#0a7a3e" },
          { label: "Margem %",       value: `${(totPct * 100).toFixed(1)}%`,                                                                     color: totPct < 0.1 ? "#c0392b" : totPct < 0.3 ? "#856404" : "#0a7a3e" },
        ].map(k => (
          <Card
            key={k.label}
            style={{ flex: 1, minWidth: 170, borderRadius: 10, border: "1px solid #dde3f0", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}
            styles={{ body: { padding: "1rem 1.2rem", textAlign: "center" } }}
          >
            <Statistic
              title={<span style={{ color: "#6b7fa3", fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{k.label}</span>}
              value={k.value}
              valueStyle={{ color: k.color, fontSize: "1.25rem", fontWeight: 700 }}
            />
          </Card>
        ))}
      </div>

      {loading ? <TableSkeleton rows={10} /> : error ? <ErrorState onRetry={loadInitial} /> : (
        <Table
          dataSource={tableData}
          columns={columns}
          title={() => (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 4, padding: "0 0 4px" }}>
              <span style={{ color: "#6b7fa3", fontSize: "0.75rem", marginLeft: 4, marginRight: 2, lineHeight: "24px" }}>Métricas:</span>
              {metricsSettingsButton}
              <span style={{ color: "#6b7fa3", fontSize: "0.75rem", marginLeft: 6, marginRight: 2, lineHeight: "24px" }}>Períodos:</span>
              {periodSettings}
              <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                onClick={() => exportTableToExcel(columns, pivotData, "resumo_por_empresa")}>Excel</Button>
            </div>
          )}
          pagination={false}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={row => ({ style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : {} })}
        />
      )}
    </div>
  );
}


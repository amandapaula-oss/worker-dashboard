import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Select, Table, Button, Card, Statistic, Popover, Checkbox } from "antd";
import { FilterOutlined, DownloadOutlined, SettingOutlined } from "@ant-design/icons";
import { getNovaBaseFilters, getNovaBaseResumo, getNovaBaseDre } from "../api";
import TableSkeleton from "../components/TableSkeleton";
import PLTable from "../components/PLTable";
import ErrorState from "../components/ErrorState";
import { theme } from "../theme";
import { exportTableToExcel, exportPLTableToExcel } from "../utils/exportExcel";
import { periodoLabel } from "../utils/format";


const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const ALL_METRICS = ["receita", "custo", "valor_liquido", "horas"] as const;
type Metric = typeof ALL_METRICS[number];
const METRIC_LABELS: Record<Metric, string> = {
  receita: "Receita", custo: "Custo", valor_liquido: "Vlr Líquido", horas: "Horas",
};

const AGRUPAR_LABELS: Record<string, string> = {
  empresa: "Empresa", fonte: "Fonte", macro_area: "Macro Área",
};

export default function NovaBaseResumoTab({ agruparPor = "empresa" }: { agruparPor?: string }) {
  const [filters, setFilters]           = useState<any>({});
  const [selPeriodos, setSelPeriodos]   = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas]   = useState<string[]>([]);
  const [selFontes, setSelFontes]       = useState<string[]>([]);
  const [rawData, setRawData]           = useState<any[]>([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [filtersReady, setFiltersReady] = useState(false);
  const [showFilters, setShowFilters]   = useState(false);
  const initialLoad = useRef(true);

  const [visibleMetrics, setVisibleMetrics] = useState<Set<Metric>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("tbl:nb-resumo-metrics") || "null");
      if (Array.isArray(saved)) return new Set(saved as Metric[]);
    } catch {}
    return new Set<Metric>(["receita", "custo", "valor_liquido"]);
  });

  const toggleMetric = (m: Metric) => {
    setVisibleMetrics(prev => {
      const next = new Set(prev);
      if (next.has(m)) { if (next.size > 1) next.delete(m); }
      else next.add(m);
      localStorage.setItem("tbl:nb-resumo-metrics", JSON.stringify(Array.from(next)));
      return next;
    });
  };

  useEffect(() => {
    getNovaBaseFilters()
      .then(f => { setFilters(f); setFiltersReady(true); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = { agrupar_por: agruparPor };
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selFontes.length)   params.fontes   = selFontes.join(",");
    getNovaBaseResumo(params)
      .then(r => { setRawData(r); initialLoad.current = false; setError(null); })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selPeriodos, selEmpresas, selFontes, agruparPor]);

  useEffect(() => { if (filtersReady) load(); }, [filtersReady, load]);

  const periodos = useMemo(() =>
    Array.from(new Set(rawData.map((r: any) => r.periodo))).filter(Boolean).sort() as string[],
  [rawData]);

  const pivotData = useMemo(() => {
    const map = new Map<string, any>();
    for (const r of rawData) {
      const key = r.grupo || "(sem grupo)";
      if (!map.has(key)) map.set(key, { grupo: key });
      const e = map.get(key)!;
      e[`${r.periodo}_receita`]       = (e[`${r.periodo}_receita`]       || 0) + (Number(r.receita)       || 0);
      e[`${r.periodo}_custo`]         = (e[`${r.periodo}_custo`]         || 0) + (Number(r.custo_rateado) || 0);
      e[`${r.periodo}_valor_liquido`] = (e[`${r.periodo}_valor_liquido`] || 0) + (Number(r.valor_liquido) || 0);
      e[`${r.periodo}_horas`]         = (e[`${r.periodo}_horas`]         || 0) + (Number(r.horas)         || 0);
    }
    return Array.from(map.values()).map(r => ({
      ...r,
      total_receita:       periodos.reduce((s, p) => s + (r[`${p}_receita`]       || 0), 0),
      total_custo:         periodos.reduce((s, p) => s + (r[`${p}_custo`]         || 0), 0),
      total_valor_liquido: periodos.reduce((s, p) => s + (r[`${p}_valor_liquido`] || 0), 0),
      total_horas:         periodos.reduce((s, p) => s + (r[`${p}_horas`]         || 0), 0),
    })).sort((a, b) => b.total_valor_liquido - a.total_valor_liquido);
  }, [rawData, periodos]);

  const totReceita = pivotData.reduce((s, r) => s + (r.total_receita || 0), 0);
  const totCusto   = pivotData.reduce((s, r) => s + (r.total_custo   || 0), 0);
  const totVL      = pivotData.reduce((s, r) => s + (r.total_valor_liquido || 0), 0);
  const totHoras   = pivotData.reduce((s, r) => s + (r.total_horas   || 0), 0);

  const tableData = useMemo(() => {
    const totRow: any = {
      key: "__t__", grupo: "TOTAL",
      total_receita: totReceita, total_custo: totCusto,
      total_valor_liquido: totVL, total_horas: totHoras,
      _isTotal: true,
    };
    periodos.forEach(p => {
      totRow[`${p}_receita`]       = pivotData.reduce((s, r) => s + (r[`${p}_receita`]       || 0), 0);
      totRow[`${p}_custo`]         = pivotData.reduce((s, r) => s + (r[`${p}_custo`]         || 0), 0);
      totRow[`${p}_valor_liquido`] = pivotData.reduce((s, r) => s + (r[`${p}_valor_liquido`] || 0), 0);
      totRow[`${p}_horas`]         = pivotData.reduce((s, r) => s + (r[`${p}_horas`]         || 0), 0);
    });
    return [totRow, ...pivotData.map((d, i) => ({ ...d, key: i }))];
  }, [pivotData, periodos, totReceita, totCusto, totVL, totHoras]);

  const columnsDef = useMemo(() => {
    type MetricKey = "receita" | "custo" | "valor_liquido" | "horas";
    const colDef = (prefix: string, metric: MetricKey, bold: boolean) => {
      const isHoras = metric === "horas";
      return {
        dataIndex: `${prefix}_${metric}`,
        key: `${prefix}_${metric}`,
        align: "right" as const,
        sorter: (a: any, b: any) =>
          (Number(a[`${prefix}_${metric}`]) || 0) - (Number(b[`${prefix}_${metric}`]) || 0),
        render: (v: number) => (
          <span style={{ fontWeight: bold ? 700 : 500, color: isHoras ? theme.text : (v || 0) < 0 ? "#c0392b" : theme.text }}>
            {isHoras
              ? (v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })
              : brl(v || 0)}
          </span>
        ),
      };
    };

    const metricChildDefs: { metric: MetricKey; title: string; width: number }[] = [
      { metric: "receita",       title: "Receita",    width: 140 },
      { metric: "custo",         title: "Custo",      width: 130 },
      { metric: "valor_liquido", title: "Vlr Líq.",   width: 130 },
      { metric: "horas",         title: "Horas",      width: 90  },
    ];

    const children = (prefix: string, bold: boolean) =>
      metricChildDefs
        .filter(m => visibleMetrics.has(m.metric))
        .map(m => ({ ...colDef(prefix, m.metric, bold), title: m.title, width: m.width }));

    const periodoCols = periodos.map(p => ({
      title: periodoLabel ? periodoLabel(p) : p,
      key: p,
      children: children(p, false),
    }));

    return [
      {
        title: AGRUPAR_LABELS[agruparPor] ?? "Grupo",
        dataIndex: "grupo", key: "grupo", width: 170, fixed: "left" as const,
        sorter: (a: any, b: any) => String(a.grupo).localeCompare(String(b.grupo), "pt-BR"),
      },
      ...periodoCols,
      {
        title: "Total",
        key: "__total__",
        children: children("total", true),
      },
    ];
  }, [periodos, visibleMetrics, agruparPor]);

  const opt = (arr: string[]) => arr.map(v => ({ label: v, value: v }));
  const hasActiveFilter = selPeriodos.length > 0 || selEmpresas.length > 0 || selFontes.length > 0;

  return (
    <div>
      {/* Filter bar */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Button
          icon={<FilterOutlined />}
          onClick={() => setShowFilters(v => !v)}
          type={hasActiveFilter ? "primary" : "default"}
          style={{ marginLeft: "auto" }}
        >
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>

      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Período</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
              onChange={setSelPeriodos} options={opt(filters.periodos ?? [])}
              maxTagCount="responsive" placeholder="Todos" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
              onChange={setSelEmpresas} options={opt(filters.empresas ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Fonte</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selFontes}
              onChange={setSelFontes} options={opt(filters.fontes ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
        </div>
      )}

      {/* KPI cards */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        {[
          { label: "Receita Total",   value: brl(totReceita), color: theme.text },
          { label: "Custo Total",     value: brl(totCusto),   color: totCusto   < 0 ? "#c0392b" : theme.text },
          { label: "Vlr Líquido",     value: brl(totVL),      color: totVL      < 0 ? "#c0392b" : "#0a7a3e" },
          { label: "Total de Horas",  value: totHoras.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }), color: theme.text },
        ].map(k => (
          <Card key={k.label}
            style={{ flex: 1, minWidth: 160, borderRadius: 10, border: "1px solid #dde3f0", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}
            styles={{ body: { padding: "1rem 1.2rem", textAlign: "center" } }}
          >
            <Statistic
              title={<span style={{ color: "#6b7fa3", fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{k.label}</span>}
              value={k.value}
              valueStyle={{ color: k.color, fontSize: "1.1rem", fontWeight: 700 }}
            />
          </Card>
        ))}
      </div>

      {loading ? <TableSkeleton rows={8} /> : error ? (
        <div style={{ background: "#fff1f0", border: "1px solid #ffa39e", borderRadius: 8, padding: "1rem 1.2rem", color: "#cf1322" }}>
          <strong>Erro ao carregar dados:</strong> {error}
        </div>
      ) : (
        <Table
          dataSource={tableData}
          columns={columnsDef}
          rowKey="key"
          size="small"
          pagination={false}
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={row => ({ style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : {} })}
          title={() => (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 6, padding: "0 0 4px" }}>
              <span style={{ color: "#6b7fa3", fontSize: "0.75rem", marginRight: 2, lineHeight: "24px" }}>Métricas:</span>
              <Popover trigger="click" placement="bottomRight" title="Métricas visíveis"
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
                <Button icon={<SettingOutlined />} size="small" type="text" style={{ color: "#6b7fa3" }} />
              </Popover>
              <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                onClick={() => exportTableToExcel(columnsDef, pivotData, "nb_resumo")}>Excel</Button>
            </div>
          )}
        />
      )}
    </div>
  );
}

// ── DRE Nova Base 2026 ─────────────────────────────────────────────────────────

export function NovaDreTab() {
  const [filters, setFilters]         = useState<any>({});
  const [selPeriodos, setSelPeriodos] = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [selFontes, setSelFontes]     = useState<string[]>([]);
  const [data, setData]               = useState<any>(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [filtersReady, setFiltersReady] = useState(false);
  const initialLoad = useRef(true);

  // Carga inicial: filtros primeiro, depois DRE (evita carga dupla do Excel no cold start)
  const loadInitial = useCallback(() => {
    setLoading(true); setError(null);
    getNovaBaseFilters()
      .then(f => { setFilters(f); return getNovaBaseDre({}); })
      .then(d => { setData(d); setFiltersReady(true); initialLoad.current = false; })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { loadInitial(); }, [loadInitial]);

  // Recarrega quando o usuário muda filtros (não na carga inicial)
  useEffect(() => {
    if (!filtersReady || initialLoad.current) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selFontes.length)   params.fontes   = selFontes.join(",");
    getNovaBaseDre(params)
      .then(d => { setData(d); setError(null); })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selPeriodos, selEmpresas, selFontes]);

  const opt = (arr: string[]) => arr.map((v: string) => ({ label: v, value: v }));
  const hasActiveFilter = selPeriodos.length > 0 || selEmpresas.length > 0 || selFontes.length > 0;

  const columns: string[] = useMemo(() => {
    if (!data?.columns) return [];
    return data.columns.map((c: string) =>
      c === "Total" ? "Total" : (periodoLabel ? periodoLabel(c) : c)
    );
  }, [data]);

  const rows = useMemo(() => {
    if (!data?.rows) return [];
    return data.rows.map((r: any) => {
      const renamedValues: Record<string, number> = {};
      (data.columns as string[]).forEach((raw: string, i: number) => {
        renamedValues[columns[i]] = r.values[raw] ?? 0;
      });
      return { ...r, values: renamedValues };
    });
  }, [data, columns]);

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={hasActiveFilter ? "primary" : "default"}
          style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>

      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Período</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
              onChange={setSelPeriodos} options={opt(filters.periodos ?? [])}
              maxTagCount="responsive" placeholder="Todos" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
              onChange={setSelEmpresas} options={opt(filters.empresas ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Fonte</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selFontes}
              onChange={setSelFontes} options={opt(filters.fontes ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
        </div>
      )}

      {loading ? <TableSkeleton rows={12} /> : error ? (
        <ErrorState onRetry={loadInitial} message="Não foi possível carregar o DRE. O servidor pode estar acordando — tente novamente." />
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
            <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
              onClick={() => exportPLTableToExcel(data?.rows || [], data?.columns || [], "nova_base_dre")}>
              Excel
            </Button>
          </div>
          <PLTable rows={rows} columns={columns} />
        </>
      )}
    </div>
  );
}

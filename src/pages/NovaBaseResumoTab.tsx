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

/* Timer que aparece após 5s de loading para informar sobre cold start */
function WarmUpNotice() {
  const [elapsed, setElapsed] = useState(0);
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t0 = Date.now();
    const id = setInterval(() => {
      const s = Math.floor((Date.now() - t0) / 1000);
      setElapsed(s);
      if (s >= 5) setShow(true);
    }, 1000);
    return () => clearInterval(id);
  }, []);
  if (!show) return null;
  return (
    <div style={{ marginTop: 16, color: "#6b7fa3", fontSize: "0.85rem", textAlign: "center" }}>
      <span style={{ fontSize: 18, marginRight: 6 }}>⏳</span>
      Aguardando servidor... <strong>{elapsed}s</strong>
      <div style={{ marginTop: 4, fontSize: "0.78rem", opacity: 0.7 }}>
        O servidor pode demorar até 2 min para acordar na primeira vez.
      </div>
    </div>
  );
}


const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const ALL_METRICS = ["receita", "custo", "margem", "margem_pct", "valor_liquido", "horas"] as const;
type Metric = typeof ALL_METRICS[number];
const METRIC_LABELS: Record<Metric, string> = {
  receita: "Receita", custo: "Custo", margem: "Margem", margem_pct: "Margem %", valor_liquido: "Lucro Bruto", horas: "Horas",
};

function MargemTag({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span style={{ color: "#aaa" }}>—</span>;
  const v = Number(value) * 100;
  const color = v >= 30 ? "#0a7a3e" : v >= 10 ? "#856404" : "#c0392b";
  const bg    = v >= 30 ? "#d4edda" : v >= 10 ? "#fff3cd" : "#fde8e8";
  return <span style={{ background: bg, color, fontWeight: 700, padding: "2px 8px", borderRadius: 4, fontSize: "0.85rem" }}>{v.toFixed(1)}%</span>;
}

const AGRUPAR_LABELS: Record<string, string> = {
  empresa: "Empresa", fonte: "Fonte", macro_area: "Macro Área", vertical: "BU",
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
    return Array.from(map.values()).map(r => {
      periodos.forEach(p => {
        r[`${p}_margem`] = (r[`${p}_receita`] || 0) + (r[`${p}_custo`] || 0);
        const rec = r[`${p}_receita`] || 0;
        r[`${p}_margem_pct`] = rec !== 0 ? r[`${p}_margem`] / rec : null;
      });
      const tot_rec = periodos.reduce((s, p) => s + (r[`${p}_receita`] || 0), 0);
      const tot_cus = periodos.reduce((s, p) => s + (r[`${p}_custo`]   || 0), 0);
      const tot_mar = tot_rec + tot_cus;
      return {
        ...r,
        total_receita:       tot_rec,
        total_custo:         tot_cus,
        total_margem:        tot_mar,
        total_margem_pct:    tot_rec !== 0 ? tot_mar / tot_rec : null,
        total_valor_liquido: periodos.reduce((s, p) => s + (r[`${p}_valor_liquido`] || 0), 0),
        total_horas:         periodos.reduce((s, p) => s + (r[`${p}_horas`]         || 0), 0),
      };
    }).sort((a, b) => b.total_receita - a.total_receita);
  }, [rawData, periodos]);

  const totReceita = pivotData.reduce((s, r) => s + (r.total_receita || 0), 0);
  const totCusto   = pivotData.reduce((s, r) => s + (r.total_custo   || 0), 0);
  const totMargem  = totReceita + totCusto;
  const totPct     = totReceita !== 0 ? totMargem / totReceita : 0;
  const totVL      = pivotData.reduce((s, r) => s + (r.total_valor_liquido || 0), 0);
  const totHoras   = pivotData.reduce((s, r) => s + (r.total_horas   || 0), 0);

  const tableData = useMemo(() => {
    const totRow: any = {
      key: "__t__", grupo: "TOTAL",
      total_receita: totReceita, total_custo: totCusto,
      total_margem: totMargem, total_margem_pct: totPct,
      total_valor_liquido: totVL, total_horas: totHoras,
      _isTotal: true,
    };
    periodos.forEach(p => {
      totRow[`${p}_receita`]       = pivotData.reduce((s, r) => s + (r[`${p}_receita`]       || 0), 0);
      totRow[`${p}_custo`]         = pivotData.reduce((s, r) => s + (r[`${p}_custo`]         || 0), 0);
      totRow[`${p}_margem`]        = (totRow[`${p}_receita`] || 0) + (totRow[`${p}_custo`] || 0);
      const rec = totRow[`${p}_receita`] || 0;
      totRow[`${p}_margem_pct`]    = rec !== 0 ? totRow[`${p}_margem`] / rec : null;
      totRow[`${p}_valor_liquido`] = pivotData.reduce((s, r) => s + (r[`${p}_valor_liquido`] || 0), 0);
      totRow[`${p}_horas`]         = pivotData.reduce((s, r) => s + (r[`${p}_horas`]         || 0), 0);
    });
    return [totRow, ...pivotData.map((d, i) => ({ ...d, key: i }))];
  }, [pivotData, periodos, totReceita, totCusto, totVL, totHoras]);

  const columnsDef = useMemo(() => {
    type MetricKey = "receita" | "custo" | "margem" | "margem_pct" | "valor_liquido" | "horas";
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

    const metricChildDefs: { metric: MetricKey; title: string; width: number; renderFn?: string }[] = [
      { metric: "receita",       title: "Receita",    width: 140 },
      { metric: "custo",         title: "Custo",      width: 130 },
      { metric: "margem",        title: "Margem",     width: 130 },
      { metric: "margem_pct",    title: "%",          width: 75, renderFn: "pct" },
      { metric: "valor_liquido", title: "Lucro Bruto", width: 130 },
      { metric: "horas",         title: "Horas",      width: 90  },
    ];

    const children = (prefix: string, bold: boolean) =>
      metricChildDefs
        .filter(m => visibleMetrics.has(m.metric))
        .map(m => {
          if (m.renderFn === "pct") {
            return {
              dataIndex: `${prefix}_${m.metric}`,
              key: `${prefix}_${m.metric}`,
              title: m.title, width: m.width,
              align: "right" as const,
              sorter: (a: any, b: any) => (Number(a[`${prefix}_${m.metric}`]) || 0) - (Number(b[`${prefix}_${m.metric}`]) || 0),
              render: (v: any) => <MargemTag value={v} />,
            };
          }
          const col = colDef(prefix, m.metric as any, bold);
          if (m.metric === "margem") {
            return { ...col, title: m.title, width: m.width,
              render: (v: number) => <span style={{ fontWeight: bold ? 700 : 600, color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(v || 0)}</span>,
            };
          }
          return { ...col, title: m.title, width: m.width };
        });

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
          { label: "Margem Bruta",    value: brl(totMargem),  color: totMargem  < 0 ? "#c0392b" : "#0a7a3e" },
          { label: "Margem %",        value: `${(totPct * 100).toFixed(1)}%`, color: totPct < 0.1 ? "#c0392b" : totPct < 0.3 ? "#856404" : "#0a7a3e" },
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
          bordered
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

      {loading ? (
        <div>
          <TableSkeleton rows={12} />
          <WarmUpNotice />
        </div>
      ) : error ? (
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

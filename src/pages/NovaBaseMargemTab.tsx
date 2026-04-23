import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Table, Spin, Button, Input, Breadcrumb, Card, Statistic, Select, Segmented, Popover, Checkbox } from "antd";
import { HomeOutlined, ArrowLeftOutlined, SearchOutlined, DownloadOutlined, FilterOutlined, SettingOutlined } from "@ant-design/icons";
import { periodoLabel } from "../utils/format";
import { getNovaBaseFilters, getNovaBaseMargemClientes, getNovaBaseMargemClienteDetalhe } from "../api";
import { exportTableToExcel } from "../utils/exportExcel";
import { toTitleCase } from "../utils/format";
import { theme } from "../theme";

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const ALL_METRICS = ["receita", "custo_rateado", "margem", "margem_pct", "horas"] as const;
type Metric = typeof ALL_METRICS[number];
const METRIC_LABELS: Record<Metric, string> = {
  receita: "Receita", custo_rateado: "Custo Rateado", margem: "Margem", margem_pct: "Margem %", horas: "Horas",
};

function MargemTag({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span style={{ color: "#aaa" }}>—</span>;
  const v = Number(value) * 100;
  const color = v >= 30 ? "#0a7a3e" : v >= 10 ? "#856404" : "#c0392b";
  const bg    = v >= 30 ? "#d4edda" : v >= 10 ? "#fff3cd" : "#fde8e8";
  return <span style={{ background: bg, color, fontWeight: 700, padding: "2px 8px", borderRadius: 4, fontSize: "0.85rem" }}>{v.toFixed(1)}%</span>;
}

export default function NovaBaseMargemTab() {
  const [filters, setFilters]         = useState<any>({});
  const [selPeriodos, setSelPeriodos] = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [selVerticais, setSelVerticais] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [loading, setLoading]         = useState(true);
  const [clientes, setClientes]       = useState<any[]>([]);
  const [search, setSearch]           = useState("");
  const [viewMode, setViewMode]       = useState<string>("Consolidado");

  // Drill-down
  const [selectedCliente, setSelectedCliente] = useState<string | null>(null);
  const [detalhe, setDetalhe]         = useState<any[]>([]);
  const [loadingDetalhe, setLoadingDetalhe] = useState(false);

  const [visibleMetrics, setVisibleMetrics] = useState<Set<Metric>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("tbl:nb-margem-cli-metrics") || "null");
      if (Array.isArray(saved)) return new Set(saved as Metric[]);
    } catch {}
    return new Set<Metric>(ALL_METRICS);
  });
  const toggleMetric = (m: Metric) => {
    setVisibleMetrics(prev => {
      const next = new Set(prev);
      if (next.has(m)) { if (next.size > 1) next.delete(m); }
      else next.add(m);
      localStorage.setItem("tbl:nb-margem-cli-metrics", JSON.stringify(Array.from(next)));
      return next;
    });
  };

  useEffect(() => {
    getNovaBaseFilters().then(f => setFilters(f)).catch(() => {});
  }, []);

  const loadClientes = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selVerticais.length) params.verticais = selVerticais.join(",");
    if (viewMode === "Por Mês") params.breakdown = "true";
    getNovaBaseMargemClientes(params)
      .then(setClientes)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selPeriodos, selEmpresas, selVerticais, viewMode]);

  useEffect(() => { loadClientes(); }, [loadClientes]);

  const abrirCliente = (nome: string) => {
    setSelectedCliente(nome);
    setLoadingDetalhe(true);
    const params: Record<string, string> = { nome_cliente: nome };
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selVerticais.length) params.verticais = selVerticais.join(",");
    getNovaBaseMargemClienteDetalhe(params)
      .then(setDetalhe)
      .catch(() => {})
      .finally(() => setLoadingDetalhe(false));
  };

  const voltarClientes = () => { setSelectedCliente(null); setDetalhe([]); };

  const filteredClientes = useMemo(() => {
    if (!search) return clientes;
    const q = search.toLowerCase();
    return clientes.filter(r => String(r.nome_cliente || "").toLowerCase().includes(q));
  }, [clientes, search]);

  const totRec  = filteredClientes.reduce((s, r) => s + (r.receita || 0), 0);
  const totCus  = filteredClientes.reduce((s, r) => s + (r.custo_rateado || 0), 0);
  const totMar  = totRec + totCus;
  const totPct  = totRec !== 0 ? totMar / totRec : 0;

  const isMensal = viewMode === "Por Mês";

  const clienteCols = useMemo(() => {
    const cols: any[] = [
      {
        title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", width: 220,
        render: (v: string) => (
          <Button type="link" style={{ padding: 0, fontWeight: 600 }} onClick={() => abrirCliente(v)}>
            {toTitleCase(v)}
          </Button>
        ),
        sorter: (a: any, b: any) => String(a.nome_cliente).localeCompare(String(b.nome_cliente), "pt-BR"),
      },
    ];
    if (isMensal) {
      cols.push({
        title: "Período", dataIndex: "periodo", key: "periodo", width: 100,
        sorter: (a: any, b: any) => String(a.periodo || "").localeCompare(String(b.periodo || "")),
        render: (v: string) => v ? periodoLabel(v) : "—",
      });
    }
    const metricCols: Record<Metric, any> = {
      receita: { title: "Receita", dataIndex: "receita", key: "receita", align: "right" as const, width: 150,
        sorter: (a: any, b: any) => (a.receita || 0) - (b.receita || 0), defaultSortOrder: "descend" as const,
        render: (v: number) => <span style={{ fontWeight: 600 }}>{brl(v || 0)}</span> },
      custo_rateado: { title: "Custo Rateado", dataIndex: "custo_rateado", key: "custo_rateado", align: "right" as const, width: 150,
        sorter: (a: any, b: any) => (a.custo_rateado || 0) - (b.custo_rateado || 0),
        render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : theme.text }}>{brl(v || 0)}</span> },
      margem: { title: "Margem", dataIndex: "margem", key: "margem", align: "right" as const, width: 150,
        sorter: (a: any, b: any) => (a.margem || 0) - (b.margem || 0),
        render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span> },
      margem_pct: { title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", align: "right" as const, width: 100,
        sorter: (a: any, b: any) => (a.margem_pct || 0) - (b.margem_pct || 0),
        render: (v: any) => <MargemTag value={v} /> },
      horas: { title: "Horas", dataIndex: "horas", key: "horas", align: "right" as const, width: 100,
        sorter: (a: any, b: any) => (a.horas || 0) - (b.horas || 0),
        render: (v: number) => (v || 0) > 0 ? v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—" },
    };
    ALL_METRICS.forEach(m => { if (visibleMetrics.has(m)) cols.push(metricCols[m]); });
    return cols;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMensal, visibleMetrics]);

  const detalheCols: any[] = [
    { title: "PEP", dataIndex: "pep", key: "pep", width: 160,
      sorter: (a: any, b: any) => String(a.pep).localeCompare(String(b.pep)) },
    { title: "Empresa", dataIndex: "empresa", width: 140 },
    { title: "BU", dataIndex: "categoria_bu", width: 100 },
    { title: "Vertical", dataIndex: "vertical", width: 140 },
    { title: "Receita", dataIndex: "receita", align: "right" as const, width: 140,
      sorter: (a: any, b: any) => (a.receita || 0) - (b.receita || 0), defaultSortOrder: "descend" as const,
      render: (v: number) => <span style={{ fontWeight: 600 }}>{brl(v || 0)}</span> },
    { title: "Custo Rateado", dataIndex: "custo_rateado", align: "right" as const, width: 140,
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : theme.text }}>{brl(v || 0)}</span> },
    { title: "Margem", dataIndex: "margem", align: "right" as const, width: 140,
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span> },
    { title: "Margem %", dataIndex: "margem_pct", align: "right" as const, width: 90,
      render: (v: any) => <MargemTag value={v} /> },
    { title: "Horas", dataIndex: "horas", align: "right" as const, width: 90,
      render: (v: number) => (v || 0) > 0 ? v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—" },
  ];

  const opt = (arr: string[]) => (arr || []).map(v => ({ label: v, value: v }));

  if (selectedCliente) {
    const totDetRec = detalhe.reduce((s, r) => s + (r.receita || 0), 0);
    const totDetCus = detalhe.reduce((s, r) => s + (r.custo_rateado || 0), 0);
    const totDetMar = totDetRec + totDetCus;
    return (
      <div>
        <Breadcrumb style={{ marginBottom: 12 }} items={[
          { title: <span style={{ cursor: "pointer" }} onClick={voltarClientes}><HomeOutlined /> Clientes</span> },
          { title: toTitleCase(selectedCliente) },
        ]} />
        <Button icon={<ArrowLeftOutlined />} onClick={voltarClientes} style={{ marginBottom: 12 }}>Voltar para clientes</Button>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
          {[
            { label: "Receita", value: brl(totDetRec), color: theme.text },
            { label: "Custo", value: brl(totDetCus), color: totDetCus < 0 ? "#c0392b" : theme.text },
            { label: "Margem", value: brl(totDetMar), color: totDetMar < 0 ? "#c0392b" : "#0a7a3e" },
            { label: "Margem %", value: totDetRec ? `${(totDetMar/totDetRec*100).toFixed(1)}%` : "—",
              color: totDetRec ? (totDetMar/totDetRec >= 0.3 ? "#0a7a3e" : totDetMar/totDetRec >= 0.1 ? "#856404" : "#c0392b") : "#aaa" },
          ].map(k => (
            <Card key={k.label} style={{ flex: 1, minWidth: 150, borderRadius: 10, border: "1px solid #dde3f0" }}
              styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}>
              <Statistic title={<span style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase" }}>{k.label}</span>}
                value={k.value} valueStyle={{ color: k.color, fontSize: "1.1rem", fontWeight: 700 }} />
            </Card>
          ))}
        </div>
        {loadingDetalhe ? <Spin /> : (
          <Table dataSource={detalhe.map((d, i) => ({ ...d, key: i }))} columns={detalheCols}
            size="small" pagination={false} scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden" }}
            title={() => (
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                  onClick={() => exportTableToExcel(detalheCols, detalhe, `margem_${selectedCliente}`)}>Excel</Button>
              </div>
            )}
            summary={() => {
              const tRec = detalhe.reduce((s, r) => s + (r.receita || 0), 0);
              const tCus = detalhe.reduce((s, r) => s + (r.custo_rateado || 0), 0);
              const tMar = tRec + tCus;
              const tHrs = detalhe.reduce((s, r) => s + (r.horas || 0), 0);
              return (
                <Table.Summary.Row style={{ fontWeight: 700, background: "#dce6f7" }}>
                  <Table.Summary.Cell index={0}>TOTAL</Table.Summary.Cell>
                  <Table.Summary.Cell index={1} />
                  <Table.Summary.Cell index={2} />
                  <Table.Summary.Cell index={3} />
                  <Table.Summary.Cell index={4} align="right">{brl(tRec)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right"><span style={{ color: "#c0392b" }}>{brl(tCus)}</span></Table.Summary.Cell>
                  <Table.Summary.Cell index={6} align="right"><span style={{ color: tMar < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(tMar)}</span></Table.Summary.Cell>
                  <Table.Summary.Cell index={7} align="right"><MargemTag value={tRec ? tMar/tRec : null} /></Table.Summary.Cell>
                  <Table.Summary.Cell index={8} align="right">{tHrs > 0 ? tHrs.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—"}</Table.Summary.Cell>
                </Table.Summary.Row>
              );
            }}
          />
        )}
      </div>
    );
  }

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Input prefix={<SearchOutlined />} placeholder="Buscar cliente..." value={search}
          onChange={e => setSearch(e.target.value)} style={{ maxWidth: 300 }} allowClear />
        <Segmented options={["Consolidado", "Por Mês"]} value={viewMode} onChange={v => setViewMode(v as string)} />
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={selPeriodos.length > 0 || selEmpresas.length > 0 || selVerticais.length > 0 ? "primary" : "default"} style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>
      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Período</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
              onChange={setSelPeriodos} options={opt(filters.periodos || [])} maxTagCount="responsive" placeholder="Todos" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
              onChange={setSelEmpresas} options={opt(filters.empresas || [])} maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Vertical</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selVerticais}
              onChange={setSelVerticais} options={opt(filters.verticais || [])} maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        {[
          { label: "Receita Total", value: brl(totRec), color: theme.text },
          { label: "Custo Total",   value: brl(totCus), color: totCus < 0 ? "#c0392b" : theme.text },
          { label: "Margem Bruta",  value: brl(totMar), color: totMar < 0 ? "#c0392b" : "#0a7a3e" },
          { label: "Margem %",      value: `${(totPct * 100).toFixed(1)}%`, color: totPct < 0.1 ? "#c0392b" : totPct < 0.3 ? "#856404" : "#0a7a3e" },
        ].map(k => (
          <Card key={k.label} style={{ flex: 1, minWidth: 160, borderRadius: 10, border: "1px solid #dde3f0" }}
            styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}>
            <Statistic title={<span style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase" }}>{k.label}</span>}
              value={k.value} valueStyle={{ color: k.color, fontSize: "1.1rem", fontWeight: 700 }} />
          </Card>
        ))}
      </div>

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <Table dataSource={filteredClientes.map((d, i) => ({ ...d, key: `${d.nome_cliente}_${d.periodo || ""}_${i}` }))} columns={clienteCols}
          size="small" pagination={{ defaultPageSize: 50, showSizeChanger: true, pageSizeOptions: ["20", "50", "100", "200"] }}
          scroll={{ x: 900 }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
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
                onClick={() => exportTableToExcel(clienteCols, filteredClientes, "nova_base_margem_clientes")}>Excel</Button>
            </div>
          )}
          summary={() => {
            const cells: React.ReactNode[] = [];
            let idx = 0;
            cells.push(<Table.Summary.Cell key="lbl" index={idx++}>TOTAL ({filteredClientes.length})</Table.Summary.Cell>);
            if (isMensal) cells.push(<Table.Summary.Cell key="per" index={idx++} />);
            ALL_METRICS.forEach(m => {
              if (!visibleMetrics.has(m)) return;
              if (m === "receita") cells.push(<Table.Summary.Cell key={m} index={idx++} align="right">{brl(totRec)}</Table.Summary.Cell>);
              else if (m === "custo_rateado") cells.push(<Table.Summary.Cell key={m} index={idx++} align="right"><span style={{ color: "#c0392b" }}>{brl(totCus)}</span></Table.Summary.Cell>);
              else if (m === "margem") cells.push(<Table.Summary.Cell key={m} index={idx++} align="right"><span style={{ color: totMar < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(totMar)}</span></Table.Summary.Cell>);
              else if (m === "margem_pct") cells.push(<Table.Summary.Cell key={m} index={idx++} align="right"><MargemTag value={totPct} /></Table.Summary.Cell>);
              else if (m === "horas") cells.push(<Table.Summary.Cell key={m} index={idx++} align="right">—</Table.Summary.Cell>);
            });
            return (
              <Table.Summary.Row style={{ fontWeight: 700, background: "#dce6f7" }}>
                {cells}
              </Table.Summary.Row>
            );
          }}
        />
      )}
    </div>
  );
}

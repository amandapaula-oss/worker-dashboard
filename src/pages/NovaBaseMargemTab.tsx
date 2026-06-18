import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Table, Spin, Button, Input, Breadcrumb, Card, Statistic, Select, Segmented, Popover, Checkbox } from "antd";
import { HomeOutlined, ArrowLeftOutlined, SearchOutlined, DownloadOutlined, FilterOutlined, SettingOutlined } from "@ant-design/icons";
import { periodoLabel } from "../utils/format";
import { getNovaBaseFilters, getNovaBaseMargemClientes, getNovaBaseMargemClienteDetalhe, getNovaBaseMargemProjetoPessoas, getNovaBaseMargemPessoaClientes } from "../api";
import { exportTableToExcel } from "../utils/exportExcel";
import { toTitleCase } from "../utils/format";
import { theme } from "../theme";
import DetalheCelulaModal from "../components/DetalheCelulaModal";
import { useNovaBaseFilters } from "../contexts/NovaBaseFilters";

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
  const {
    selPeriodos, setSelPeriodos,
    selEmpresas, setSelEmpresas,
    selVerticais, setSelVerticais,
    selFontes, setSelFontes,
    selApuracoes, setSelApuracoes,
    selNoHier, setSelNoHier,
    resetFilters, hasAnyFilter, periodoLocked,
  } = useNovaBaseFilters();
  const [showFilters, setShowFilters] = useState(false);
  const [loading, setLoading]         = useState(true);
  const [clientes, setClientes]       = useState<any[]>([]);
  const [search, setSearch]           = useState("");
  const [viewMode, setViewMode]       = useState<string>("Consolidado");

  // Drill-down
  const [selectedCliente, setSelectedCliente] = useState<string | null>(null);
  const [detalhe, setDetalhe]         = useState<any[]>([]);
  const [loadingDetalhe, setLoadingDetalhe] = useState(false);
  // 3o nivel: projeto (PEP) -> pessoas
  const [selectedPep, setSelectedPep] = useState<string | null>(null);
  const [pessoas, setPessoas]         = useState<any[]>([]);
  const [loadingPessoas, setLoadingPessoas] = useState(false);
  const [detalheMensal, setDetalheMensal] = useState(false);
  const [pessoaMensal, setPessoaMensal] = useState(false);
  const [selectedPessoa, setSelectedPessoa] = useState<string | null>(null);
  const [pessoaClientes, setPessoaClientes] = useState<any[]>([]);
  const [loadingPessoaClientes, setLoadingPessoaClientes] = useState(false);
  const [pessoaClientesMensal, setPessoaClientesMensal] = useState(false);

  const [drillOpen, setDrillOpen]       = useState(false);
  const [drillFilters, setDrillFilters] = useState<Record<string, string>>({});
  const [drillTitulo, setDrillTitulo]   = useState("");
  const [drillMetric, setDrillMetric]   = useState("");

  const openDrill = (cliente: string, prefix: string, metric: string, metricLabel: string, pep?: string, pessoa?: string) => {
    const filters: Record<string, string> = { nome_cliente: cliente };
    if (selPeriodos.length) filters.periodos = selPeriodos.join(",");
    if (selEmpresas.length) filters.empresas = selEmpresas.join(",");
    if (selVerticais.length) filters.verticais = selVerticais.join(",");
    if (selFontes.length) filters.fontes = selFontes.join(",");
    if (prefix !== "total") filters.periodos = prefix;
    if (metric) filters.metric = metric;
    if (pep) filters.pep = pep;
    if (pessoa) filters.nome_pessoa = pessoa;
    setDrillFilters(filters);
    const periodoTxt = prefix === "total" ? "Total" : periodoLabel(prefix);
    const pepTxt = pep ? ` · ${pep}` : "";
    const pessoaTxt = pessoa ? ` · ${toTitleCase(pessoa)}` : "";
    setDrillTitulo(`${toTitleCase(cliente)}${pepTxt}${pessoaTxt} · ${periodoTxt}`);
    setDrillMetric(metricLabel);
    setDrillOpen(true);
  };

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
    if (selPeriodos.length)  params.periodos       = selPeriodos.join(",");
    if (selEmpresas.length)  params.empresas       = selEmpresas.join(",");
    if (selVerticais.length) params.verticais      = selVerticais.join(",");
    if (selFontes.length)    params.fontes         = selFontes.join(",");
    if (selApuracoes.length) params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)    params.no_hierarquias = selNoHier.join(",");
    if (viewMode === "Por Mês") params.breakdown = "true";
    getNovaBaseMargemClientes(params)
      .then(setClientes)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selPeriodos, selEmpresas, selVerticais, selFontes, selApuracoes, selNoHier, viewMode]);

  useEffect(() => { loadClientes(); }, [loadClientes]);

  const abrirCliente = (nome: string, mensal = detalheMensal, periodos = selPeriodos) => {
    setSelectedCliente(nome);
    setLoadingDetalhe(true);
    const params: Record<string, string> = { nome_cliente: nome };
    if (mensal)              params.breakdown      = "true";
    if (periodos.length)     params.periodos       = periodos.join(",");
    if (selEmpresas.length)  params.empresas       = selEmpresas.join(",");
    if (selVerticais.length) params.verticais      = selVerticais.join(",");
    if (selFontes.length)    params.fontes         = selFontes.join(",");
    if (selApuracoes.length) params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)    params.no_hierarquias = selNoHier.join(",");
    getNovaBaseMargemClienteDetalhe(params)
      .then(setDetalhe)
      .catch(() => {})
      .finally(() => setLoadingDetalhe(false));
  };

  const voltarClientes = () => { setSelectedCliente(null); setDetalhe([]); setSelectedPep(null); setPessoas([]); setSelectedPessoa(null); setPessoaClientes([]); };
  const voltarPeps = () => { setSelectedPep(null); setPessoas([]); setSelectedPessoa(null); setPessoaClientes([]); };
  const voltarPessoas = () => { setSelectedPessoa(null); setPessoaClientes([]); };

  const abrirPessoa = (nome: string, mensal = pessoaClientesMensal, periodos = selPeriodos) => {
    if (!nome) return;
    setSelectedPessoa(nome);
    setLoadingPessoaClientes(true);
    const params: Record<string, string> = { nome_pessoa: nome };
    if (mensal)              params.breakdown      = "true";
    if (periodos.length)     params.periodos       = periodos.join(",");
    if (selEmpresas.length)  params.empresas       = selEmpresas.join(",");
    if (selVerticais.length) params.verticais      = selVerticais.join(",");
    if (selFontes.length)    params.fontes         = selFontes.join(",");
    if (selApuracoes.length) params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)    params.no_hierarquias = selNoHier.join(",");
    getNovaBaseMargemPessoaClientes(params)
      .then(setPessoaClientes)
      .catch(() => setPessoaClientes([]))
      .finally(() => setLoadingPessoaClientes(false));
  };

  const abrirPep = (pep: string, mensal = pessoaMensal, periodos = selPeriodos) => {
    if (!selectedCliente || !pep) return;
    setSelectedPep(pep);
    setLoadingPessoas(true);
    const params: Record<string, string> = { nome_cliente: selectedCliente, pep };
    if (mensal)              params.breakdown      = "true";
    if (periodos.length)     params.periodos       = periodos.join(",");
    if (selEmpresas.length)  params.empresas       = selEmpresas.join(",");
    if (selVerticais.length) params.verticais      = selVerticais.join(",");
    if (selFontes.length)    params.fontes         = selFontes.join(",");
    if (selApuracoes.length) params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)    params.no_hierarquias = selNoHier.join(",");
    getNovaBaseMargemProjetoPessoas(params)
      .then(setPessoas)
      .catch(() => setPessoas([]))
      .finally(() => setLoadingPessoas(false));
  };

  const filteredClientes = useMemo(() => {
    if (!search) return clientes;
    const q = search.toLowerCase();
    return clientes.filter(r => String(r.nome_cliente || "").toLowerCase().includes(q));
  }, [clientes, search]);

  const totRec  = filteredClientes.reduce((s, r) => s + (r.receita || 0), 0);
  const totCus  = filteredClientes.reduce((s, r) => s + (r.custo_rateado || 0), 0);
  // Margem Bruta vem do backend: NG real + Eco a 33,3%
  const totMar  = filteredClientes.reduce((s, r) => s + (r.margem || 0), 0);
  const totPct  = totRec !== 0 ? totMar / totRec : 0;

  const isMensal = viewMode === "Por Mês";

  const periodosMensal = useMemo(() =>
    Array.from(new Set(clientes.map((r: any) => r.periodo))).filter(Boolean).sort() as string[],
    [clientes]
  );

  const pivotClientes = useMemo(() => {
    if (!isMensal) return [] as any[];
    const map = new Map<string, any>();
    for (const r of filteredClientes) {
      const key = String(r.nome_cliente || "");
      if (!map.has(key)) map.set(key, { nome_cliente: key });
      const e = map.get(key)!;
      e[`${r.periodo}_receita`]       = (e[`${r.periodo}_receita`]       || 0) + (Number(r.receita)       || 0);
      e[`${r.periodo}_custo_rateado`] = (e[`${r.periodo}_custo_rateado`] || 0) + (Number(r.custo_rateado) || 0);
      e[`${r.periodo}_horas`]         = (e[`${r.periodo}_horas`]         || 0) + (Number(r.horas)         || 0);
      // Margem Bruta ja vem calculada do backend: NG real + Eco a 33,3%
      e[`${r.periodo}_margem`]        = (e[`${r.periodo}_margem`]        || 0) + (Number(r.margem)        || 0);
    }
    return Array.from(map.values()).map(r => {
      periodosMensal.forEach(p => {
        const rec = r[`${p}_receita`] || 0;
        r[`${p}_margem_pct`] = rec !== 0 ? (r[`${p}_margem`] || 0) / rec : null;
      });
      const tot_rec = periodosMensal.reduce((s, p) => s + (r[`${p}_receita`]       || 0), 0);
      const tot_cus = periodosMensal.reduce((s, p) => s + (r[`${p}_custo_rateado`] || 0), 0);
      const tot_mar = periodosMensal.reduce((s, p) => s + (r[`${p}_margem`]        || 0), 0);
      return {
        ...r,
        total_receita:       tot_rec,
        total_custo_rateado: tot_cus,
        total_margem:        tot_mar,
        total_margem_pct:    tot_rec !== 0 ? tot_mar / tot_rec : null,
        total_horas:         periodosMensal.reduce((s, p) => s + (r[`${p}_horas`] || 0), 0),
      };
    }).sort((a, b) => b.total_receita - a.total_receita);
  }, [filteredClientes, periodosMensal, isMensal]);

  const pivotTableData = useMemo(() => {
    if (!isMensal) return [] as any[];
    const totRow: any = { key: "__t__", nome_cliente: `TOTAL (${pivotClientes.length})`, _isTotal: true };
    periodosMensal.forEach(p => {
      totRow[`${p}_receita`]       = pivotClientes.reduce((s, r) => s + (r[`${p}_receita`]       || 0), 0);
      totRow[`${p}_custo_rateado`] = pivotClientes.reduce((s, r) => s + (r[`${p}_custo_rateado`] || 0), 0);
      totRow[`${p}_margem`]        = pivotClientes.reduce((s, r) => s + (r[`${p}_margem`]        || 0), 0);
      const rec = totRow[`${p}_receita`] || 0;
      totRow[`${p}_margem_pct`]    = rec !== 0 ? totRow[`${p}_margem`] / rec : null;
      totRow[`${p}_horas`]         = pivotClientes.reduce((s, r) => s + (r[`${p}_horas`]         || 0), 0);
    });
    totRow.total_receita       = pivotClientes.reduce((s, r) => s + (r.total_receita       || 0), 0);
    totRow.total_custo_rateado = pivotClientes.reduce((s, r) => s + (r.total_custo_rateado || 0), 0);
    totRow.total_margem        = pivotClientes.reduce((s, r) => s + (r.total_margem        || 0), 0);
    totRow.total_margem_pct    = totRow.total_receita !== 0 ? totRow.total_margem / totRow.total_receita : null;
    totRow.total_horas         = pivotClientes.reduce((s, r) => s + (r.total_horas || 0), 0);
    return [totRow, ...pivotClientes.map((r, i) => ({ ...r, key: `${r.nome_cliente}_${i}` }))];
  }, [pivotClientes, periodosMensal, isMensal]);

  const clienteCols = useMemo(() => {
    const metricApiKey: Record<string, string> = {
      receita: "receita", custo_rateado: "custo_rateado", margem: "",
      margem_pct: "", horas: "horas",
    };
    const metricLabelMap: Record<string, string> = {
      receita: "Receita", custo_rateado: "Custo Rateado", margem: "Margem",
      margem_pct: "Margem %", horas: "Horas",
    };
    const clickable = (row: any, prefix: string, metric: string, content: React.ReactNode, v: any) => (
      <span
        style={{ cursor: row?._isTotal ? "default" : "pointer", borderBottom: "1px dashed transparent" }}
        onClick={(e) => {
          if (row?._isTotal) return;
          if (!v && v !== 0) return;
          e.stopPropagation();
          openDrill(row.nome_cliente, prefix, metricApiKey[metric] || "", metricLabelMap[metric]);
        }}
        onMouseEnter={(e) => { if (!row?._isTotal) (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed #6b7fa3"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed transparent"; }}
      >
        {content}
      </span>
    );

    if (!isMensal) {
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
        { title: "BU", dataIndex: "vertical", key: "vertical", width: 140, ellipsis: true,
          sorter: (a: any, b: any) => String(a.vertical || "").localeCompare(String(b.vertical || "")) },
        { title: "Centro de Lucro", dataIndex: "no_hierarquia", key: "no_hierarquia", width: 170, ellipsis: true,
          sorter: (a: any, b: any) => String(a.no_hierarquia || "").localeCompare(String(b.no_hierarquia || "")) },
      ];
      const metricCols: Record<Metric, any> = {
        receita: { title: "Receita", dataIndex: "receita", key: "receita", align: "right" as const, width: 150,
          sorter: (a: any, b: any) => (a.receita || 0) - (b.receita || 0), defaultSortOrder: "descend" as const,
          render: (v: number, row: any) => clickable(row, "total", "receita", <span style={{ fontWeight: 600 }}>{brl(v || 0)}</span>, v) },
        custo_rateado: { title: "Custo Rateado", dataIndex: "custo_rateado", key: "custo_rateado", align: "right" as const, width: 150,
          sorter: (a: any, b: any) => (a.custo_rateado || 0) - (b.custo_rateado || 0),
          render: (v: number, row: any) => clickable(row, "total", "custo_rateado", <span style={{ color: (v || 0) < 0 ? "#c0392b" : theme.text }}>{brl(v || 0)}</span>, v) },
        margem: { title: "Margem", dataIndex: "margem", key: "margem", align: "right" as const, width: 150,
          sorter: (a: any, b: any) => (a.margem || 0) - (b.margem || 0),
          render: (v: number, row: any) => clickable(row, "total", "margem", <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span>, v) },
        margem_pct: { title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", align: "right" as const, width: 100,
          sorter: (a: any, b: any) => (a.margem_pct || 0) - (b.margem_pct || 0),
          render: (v: any) => <MargemTag value={v} /> },
        horas: { title: "Horas", dataIndex: "horas", key: "horas", align: "right" as const, width: 100,
          sorter: (a: any, b: any) => (a.horas || 0) - (b.horas || 0),
          render: (v: number, row: any) => clickable(row, "total", "horas", <span>{(v || 0) > 0 ? v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—"}</span>, v) },
      };
      ALL_METRICS.forEach(m => { if (visibleMetrics.has(m)) cols.push(metricCols[m]); });
      return cols;
    }

    // Pivot layout (Por Mês) — igual Resumo por BU
    const metricDefs: Record<Metric, { title: string; width: number; render: (v: any, row: any, prefix: string) => React.ReactNode }> = {
      receita:       { title: "Receita", width: 120, render: (v, row, p) => clickable(row, p, "receita", <span style={{ fontWeight: 600 }}>{brl(v || 0)}</span>, v) },
      custo_rateado: { title: "Custo",   width: 120, render: (v, row, p) => clickable(row, p, "custo_rateado", <span style={{ color: (v || 0) < 0 ? "#c0392b" : theme.text }}>{brl(v || 0)}</span>, v) },
      margem:        { title: "Margem",  width: 120, render: (v, row, p) => clickable(row, p, "margem", <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span>, v) },
      margem_pct:    { title: "%",       width: 70,  render: (v: any)    => <MargemTag value={v} /> },
      horas:         { title: "Horas",   width: 90,  render: (v, row, p) => clickable(row, p, "horas", <span>{(v || 0) > 0 ? v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—"}</span>, v) },
    };
    const children = (prefix: string) =>
      ALL_METRICS.filter(m => visibleMetrics.has(m)).map(m => ({
        title: metricDefs[m].title,
        dataIndex: `${prefix}_${m}`,
        key: `${prefix}_${m}`,
        width: metricDefs[m].width,
        align: "right" as const,
        sorter: (a: any, b: any) => (Number(a[`${prefix}_${m}`]) || 0) - (Number(b[`${prefix}_${m}`]) || 0),
        render: (v: any, row: any) => metricDefs[m].render(v, row, prefix),
      }));

    const periodoCols = periodosMensal.map(p => ({
      title: periodoLabel(p),
      key: p,
      children: children(p),
    }));

    return [
      {
        title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", width: 220, fixed: "left" as const,
        render: (v: string, row: any) => row._isTotal
          ? <span style={{ fontWeight: 700 }}>{v}</span>
          : <Button type="link" style={{ padding: 0, fontWeight: 600 }} onClick={() => abrirCliente(v)}>{toTitleCase(v)}</Button>,
        sorter: (a: any, b: any) => String(a.nome_cliente).localeCompare(String(b.nome_cliente), "pt-BR"),
      },
      ...periodoCols,
      { title: "Total", key: "__total__", children: children("total") },
    ];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMensal, visibleMetrics, periodosMensal, selPeriodos, selEmpresas, selVerticais]);

  const detalheCols: any[] = [
    ...(detalheMensal ? [{
      title: "Período", dataIndex: "periodo", key: "periodo", width: 90,
      render: (v: string) => periodoLabel(v),
      sorter: (a: any, b: any) => String(a.periodo).localeCompare(String(b.periodo)),
    }] : []),
    { title: "PEP", dataIndex: "pep", key: "pep", width: 160,
      sorter: (a: any, b: any) => String(a.pep).localeCompare(String(b.pep)),
      render: (v: string) => (
        <Button type="link" style={{ padding: 0, fontWeight: 600 }} onClick={() => abrirPep(v)}>{v}</Button>
      ) },
    { title: "Empresa", dataIndex: "empresa", width: 140 },
    { title: "Vertical", dataIndex: "vertical", width: 140 },
    { title: "Centro de Lucro", dataIndex: "no_hierarquia", width: 170, ellipsis: true,
      sorter: (a: any, b: any) => String(a.no_hierarquia || "").localeCompare(String(b.no_hierarquia || "")) },
    { title: "Receita", dataIndex: "receita", align: "right" as const, width: 140,
      sorter: (a: any, b: any) => (a.receita || 0) - (b.receita || 0), defaultSortOrder: "descend" as const,
      render: (v: number, row: any) => (
        <span style={{ cursor: "pointer", borderBottom: "1px dashed transparent", fontWeight: 600 }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed #6b7fa3"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed transparent"; }}
          onClick={() => openDrill(selectedCliente || "", row.periodo || "total", "receita", "Receita", row.pep)}>
          {brl(v || 0)}
        </span>) },
    { title: "Custo Rateado", dataIndex: "custo_rateado", align: "right" as const, width: 140,
      render: (v: number, row: any) => (
        <span style={{ cursor: "pointer", borderBottom: "1px dashed transparent",
          color: (v || 0) < 0 ? "#c0392b" : theme.text }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed #6b7fa3"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed transparent"; }}
          onClick={() => openDrill(selectedCliente || "", row.periodo || "total", "custo_rateado", "Custo Rateado", row.pep)}>
          {brl(v || 0)}
        </span>) },
    { title: "Margem", dataIndex: "margem", align: "right" as const, width: 140,
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span> },
    { title: "Margem %", dataIndex: "margem_pct", align: "right" as const, width: 90,
      render: (v: any) => <MargemTag value={v} /> },
    { title: "Horas", dataIndex: "horas", align: "right" as const, width: 90,
      render: (v: number) => (v || 0) > 0 ? v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—" },
  ];

  const pessoaCols: any[] = [
    { title: "Pessoa", dataIndex: "nome_pessoa", key: "nome_pessoa", width: 240, ellipsis: true,
      render: (v: string) => (
        <Button type="link" style={{ padding: 0, fontWeight: 600 }} onClick={() => abrirPessoa(v)}>{toTitleCase(v)}</Button>
      ),
      sorter: (a: any, b: any) => String(a.nome_pessoa).localeCompare(String(b.nome_pessoa), "pt-BR") },
    ...(pessoaMensal ? [{
      title: "Período", dataIndex: "periodo", key: "periodo", width: 90,
      render: (v: string) => periodoLabel(v),
      sorter: (a: any, b: any) => String(a.periodo).localeCompare(String(b.periodo)),
    }] : []),
    { title: "Empresa", dataIndex: "empresa", width: 130 },
    { title: "Fonte", dataIndex: "fonte", width: 120 },
    { title: "Receita", dataIndex: "receita", align: "right" as const, width: 140,
      sorter: (a: any, b: any) => (a.receita || 0) - (b.receita || 0), defaultSortOrder: "descend" as const,
      render: (v: number, row: any) => (
        <span style={{ cursor: "pointer", borderBottom: "1px dashed transparent", fontWeight: 600 }}
          onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed #6b7fa3"}
          onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed transparent"}
          onClick={() => openDrill(selectedCliente || "", row.periodo || "total", "receita", "Receita", selectedPep || undefined, row.nome_pessoa)}>
          {brl(v || 0)}
        </span>
      ) },
    { title: "Custo Rateado", dataIndex: "custo_rateado", align: "right" as const, width: 140,
      render: (v: number, row: any) => (
        <span style={{ cursor: "pointer", borderBottom: "1px dashed transparent", color: (v || 0) < 0 ? "#c0392b" : theme.text }}
          onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed #6b7fa3"}
          onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed transparent"}
          onClick={() => openDrill(selectedCliente || "", row.periodo || "total", "custo_rateado", "Custo Rateado", selectedPep || undefined, row.nome_pessoa)}>
          {brl(v || 0)}
        </span>
      ) },
    { title: "Margem", dataIndex: "margem", align: "right" as const, width: 140,
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span> },
    { title: "Margem %", dataIndex: "margem_pct", align: "right" as const, width: 90,
      render: (v: any) => <MargemTag value={v} /> },
    { title: "Horas", dataIndex: "horas", align: "right" as const, width: 90,
      render: (v: number) => (v || 0) > 0 ? v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—" },
  ];

  const opt = (arr: string[]) => [
    ...(arr || []).map(v => ({ label: v, value: v })),
    { label: "(Vazio)", value: "__blank__" },
  ];

  // 4o nivel: detalhe de uma pessoa — receita/custo por cliente (e por mes)
  if (selectedPessoa) {
    const pcCols: any[] = [
      { title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", width: 240, ellipsis: true,
        render: (v: string) => <span style={{ fontWeight: 600 }}>{toTitleCase(v)}</span>,
        sorter: (a: any, b: any) => String(a.nome_cliente).localeCompare(String(b.nome_cliente), "pt-BR") },
      ...(pessoaClientesMensal ? [{
        title: "Período", dataIndex: "periodo", key: "periodo", width: 90,
        render: (v: string) => periodoLabel(v),
        sorter: (a: any, b: any) => String(a.periodo).localeCompare(String(b.periodo)),
      }] : []),
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
    const pRec = pessoaClientes.reduce((s, r) => s + (r.receita || 0), 0);
    const pCus = pessoaClientes.reduce((s, r) => s + (r.custo_rateado || 0), 0);
    const pMar = pRec + pCus;
    const pHrs = pessoaClientes.reduce((s, r) => s + (r.horas || 0), 0);
    return (
      <div>
        <Breadcrumb style={{ marginBottom: 12 }} items={[
          { title: <span style={{ cursor: "pointer" }} onClick={voltarClientes}><HomeOutlined /> Clientes</span> },
          ...(selectedCliente ? [{ title: <span style={{ cursor: "pointer" }} onClick={voltarPeps}>{toTitleCase(selectedCliente)}</span> }] : []),
          ...(selectedPep ? [{ title: <span style={{ cursor: "pointer" }} onClick={voltarPessoas}>{selectedPep}</span> }] : []),
          { title: toTitleCase(selectedPessoa) },
        ]} />
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
          <Button icon={<ArrowLeftOutlined />} onClick={voltarPessoas}>Voltar</Button>
          <Segmented options={["Consolidado", "Por Mês"]}
            value={pessoaClientesMensal ? "Por Mês" : "Consolidado"}
            onChange={(v) => { const m = v === "Por Mês"; setPessoaClientesMensal(m); abrirPessoa(selectedPessoa, m); }} />
          <Select mode="multiple" style={{ minWidth: 240 }} placeholder="Período (todos)"
            value={selPeriodos} options={opt(filters.periodos || [])} maxTagCount="responsive" allowClear
            onChange={(v) => { setSelPeriodos(v); abrirPessoa(selectedPessoa, pessoaClientesMensal, v); }} />
        </div>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
          {[
            { label: "Receita", value: brl(pRec), color: theme.text },
            { label: "Custo", value: brl(pCus), color: pCus < 0 ? "#c0392b" : theme.text },
            { label: "Margem", value: brl(pMar), color: pMar < 0 ? "#c0392b" : "#0a7a3e" },
            { label: "Margem %", value: pRec ? `${(pMar/pRec*100).toFixed(1)}%` : "—",
              color: pRec ? (pMar/pRec >= 0.3 ? "#0a7a3e" : pMar/pRec >= 0.1 ? "#856404" : "#c0392b") : "#aaa" },
          ].map(k => (
            <Card key={k.label} style={{ flex: 1, minWidth: 150, borderRadius: 10, border: "1px solid #dde3f0" }}
              styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}>
              <Statistic title={<span style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase" }}>{k.label}</span>}
                value={k.value} valueStyle={{ color: k.color, fontSize: "1.1rem", fontWeight: 700 }} />
            </Card>
          ))}
        </div>
        {loadingPessoaClientes ? <Spin /> : (
          <Table dataSource={pessoaClientes.map((d, i) => ({ ...d, key: i }))} columns={pcCols}
            size="small" pagination={false} scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden" }}
            title={() => (
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                  onClick={() => exportTableToExcel(pcCols, pessoaClientes, `margem_pessoa_${selectedPessoa}`)}>Excel</Button>
              </div>
            )}
            summary={() => (
              <Table.Summary.Row style={{ fontWeight: 700, background: "#dce6f7" }}>
                <Table.Summary.Cell index={0}>TOTAL</Table.Summary.Cell>
                {pessoaClientesMensal && <Table.Summary.Cell index={1} />}
                <Table.Summary.Cell index={2} align="right">{brl(pRec)}</Table.Summary.Cell>
                <Table.Summary.Cell index={3} align="right"><span style={{ color: "#c0392b" }}>{brl(pCus)}</span></Table.Summary.Cell>
                <Table.Summary.Cell index={4} align="right"><span style={{ color: pMar < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(pMar)}</span></Table.Summary.Cell>
                <Table.Summary.Cell index={5} align="right"><MargemTag value={pRec ? pMar/pRec : null} /></Table.Summary.Cell>
                <Table.Summary.Cell index={6} align="right">{pHrs > 0 ? pHrs.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—"}</Table.Summary.Cell>
              </Table.Summary.Row>
            )}
          />
        )}
        <DetalheCelulaModal
          open={drillOpen}
          onClose={() => setDrillOpen(false)}
          filters={drillFilters}
          titulo={drillTitulo}
          metricLabel={drillMetric}
        />
      </div>
    );
  }

  // 3o nivel: pessoas dentro de um projeto (PEP)
  if (selectedPep && selectedCliente) {
    const tRec = pessoas.reduce((s, r) => s + (r.receita || 0), 0);
    const tCus = pessoas.reduce((s, r) => s + (r.custo_rateado || 0), 0);
    const tMar = tRec + tCus;
    const tHrs = pessoas.reduce((s, r) => s + (r.horas || 0), 0);
    return (
      <div>
        <Breadcrumb style={{ marginBottom: 12 }} items={[
          { title: <span style={{ cursor: "pointer" }} onClick={voltarClientes}><HomeOutlined /> Clientes</span> },
          { title: <span style={{ cursor: "pointer" }} onClick={voltarPeps}>{toTitleCase(selectedCliente)}</span> },
          { title: selectedPep },
        ]} />
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
          <Button icon={<ArrowLeftOutlined />} onClick={voltarPeps}>Voltar para projetos</Button>
          <Segmented options={["Consolidado", "Por Mês"]}
            value={pessoaMensal ? "Por Mês" : "Consolidado"}
            onChange={(v) => { const m = v === "Por Mês"; setPessoaMensal(m); abrirPep(selectedPep, m); }} />
          <Select mode="multiple" style={{ minWidth: 240 }} placeholder="Período (todos)"
            value={selPeriodos} options={opt(filters.periodos || [])} maxTagCount="responsive" allowClear
            onChange={(v) => { setSelPeriodos(v); abrirPep(selectedPep, pessoaMensal, v); }} />
        </div>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
          {[
            { label: "Receita", value: brl(tRec), color: theme.text, metric: "receita", metricLabel: "Receita" },
            { label: "Custo", value: brl(tCus), color: tCus < 0 ? "#c0392b" : theme.text, metric: "custo_rateado", metricLabel: "Custo Rateado" },
            { label: "Margem", value: brl(tMar), color: tMar < 0 ? "#c0392b" : "#0a7a3e", metric: "", metricLabel: "Margem" },
            { label: "Margem %", value: tRec ? `${(tMar/tRec*100).toFixed(1)}%` : "—",
              color: tRec ? (tMar/tRec >= 0.3 ? "#0a7a3e" : tMar/tRec >= 0.1 ? "#856404" : "#c0392b") : "#aaa", metric: "", metricLabel: "Margem %" },
          ].map(k => (
            <Card key={k.label} style={{ flex: 1, minWidth: 150, borderRadius: 10, border: "1px solid #dde3f0", cursor: k.metric ? "pointer" : "default" }}
              styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}
              onClick={() => { if (k.metric && selectedCliente) openDrill(selectedCliente, "total", k.metric, k.metricLabel, selectedPep || undefined); }}>
              <Statistic title={<span style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase" }}>{k.label}</span>}
                value={k.value} valueStyle={{ color: k.color, fontSize: "1.1rem", fontWeight: 700 }} />
            </Card>
          ))}
        </div>
        {loadingPessoas ? <Spin /> : (
          <Table dataSource={pessoas.map((d, i) => ({ ...d, key: i }))} columns={pessoaCols}
            size="small" pagination={false} scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden" }}
            title={() => (
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                  onClick={() => exportTableToExcel(pessoaCols, pessoas, `margem_${selectedCliente}_${selectedPep}`)}>Excel</Button>
              </div>
            )}
            summary={() => (
              <Table.Summary.Row style={{ fontWeight: 700, background: "#dce6f7" }}>
                <Table.Summary.Cell index={0}>TOTAL</Table.Summary.Cell>
                {pessoaMensal && <Table.Summary.Cell index={1} />}
                <Table.Summary.Cell index={2} />
                <Table.Summary.Cell index={3} />
                <Table.Summary.Cell index={4} align="right">{brl(tRec)}</Table.Summary.Cell>
                <Table.Summary.Cell index={5} align="right"><span style={{ color: "#c0392b" }}>{brl(tCus)}</span></Table.Summary.Cell>
                <Table.Summary.Cell index={6} align="right"><span style={{ color: tMar < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(tMar)}</span></Table.Summary.Cell>
                <Table.Summary.Cell index={7} align="right"><MargemTag value={tRec ? tMar/tRec : null} /></Table.Summary.Cell>
                <Table.Summary.Cell index={8} align="right">{tHrs > 0 ? tHrs.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—"}</Table.Summary.Cell>
              </Table.Summary.Row>
            )}
          />
        )}
        <DetalheCelulaModal
          open={drillOpen}
          onClose={() => setDrillOpen(false)}
          filters={drillFilters}
          titulo={drillTitulo}
          metricLabel={drillMetric}
        />
      </div>
    );
  }

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
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
          <Button icon={<ArrowLeftOutlined />} onClick={voltarClientes}>Voltar para clientes</Button>
          <Segmented options={["Consolidado", "Por Mês"]}
            value={detalheMensal ? "Por Mês" : "Consolidado"}
            onChange={(v) => { const m = v === "Por Mês"; setDetalheMensal(m); abrirCliente(selectedCliente, m); }} />
          <Select mode="multiple" style={{ minWidth: 240 }} placeholder="Período (todos)"
            value={selPeriodos} options={opt(filters.periodos || [])} maxTagCount="responsive" allowClear
            onChange={(v) => { setSelPeriodos(v); abrirCliente(selectedCliente, detalheMensal, v); }} />
        </div>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
          {[
            { label: "Receita", value: brl(totDetRec), color: theme.text, metric: "receita", metricLabel: "Receita" },
            { label: "Custo", value: brl(totDetCus), color: totDetCus < 0 ? "#c0392b" : theme.text, metric: "custo_rateado", metricLabel: "Custo Rateado" },
            { label: "Margem", value: brl(totDetMar), color: totDetMar < 0 ? "#c0392b" : "#0a7a3e", metric: "", metricLabel: "Margem" },
            { label: "Margem %", value: totDetRec ? `${(totDetMar/totDetRec*100).toFixed(1)}%` : "—",
              color: totDetRec ? (totDetMar/totDetRec >= 0.3 ? "#0a7a3e" : totDetMar/totDetRec >= 0.1 ? "#856404" : "#c0392b") : "#aaa", metric: "", metricLabel: "Margem %" },
          ].map(k => (
            <Card key={k.label} style={{ flex: 1, minWidth: 150, borderRadius: 10, border: "1px solid #dde3f0", cursor: k.metric ? "pointer" : "default" }}
              styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}
              onClick={() => { if (k.metric && selectedCliente) openDrill(selectedCliente, "total", k.metric, k.metricLabel); }}>
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
              let ci = 0;
              return (
                <Table.Summary.Row style={{ fontWeight: 700, background: "#dce6f7" }}>
                  {detalheMensal && <Table.Summary.Cell index={ci++} />}
                  <Table.Summary.Cell index={ci++}>TOTAL</Table.Summary.Cell>
                  <Table.Summary.Cell index={ci++} />
                  <Table.Summary.Cell index={ci++} />
                  <Table.Summary.Cell index={ci++} align="right">{brl(tRec)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={ci++} align="right"><span style={{ color: "#c0392b" }}>{brl(tCus)}</span></Table.Summary.Cell>
                  <Table.Summary.Cell index={ci++} align="right"><span style={{ color: tMar < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(tMar)}</span></Table.Summary.Cell>
                  <Table.Summary.Cell index={ci++} align="right"><MargemTag value={tRec ? tMar/tRec : null} /></Table.Summary.Cell>
                  <Table.Summary.Cell index={ci++} align="right">{tHrs > 0 ? tHrs.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "—"}</Table.Summary.Cell>
                </Table.Summary.Row>
              );
            }}
          />
        )}
        <DetalheCelulaModal
          open={drillOpen}
          onClose={() => setDrillOpen(false)}
          filters={drillFilters}
          titulo={drillTitulo}
          metricLabel={drillMetric}
        />
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
          type={hasAnyFilter ? "primary" : "default"} style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
        {hasAnyFilter && (
          <Button onClick={resetFilters} danger>
            Limpar Filtros
          </Button>
        )}
      </div>
      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Período</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
              onChange={setSelPeriodos} options={opt(filters.periodos || [])} maxTagCount="responsive" placeholder="Todos" allowClear disabled={periodoLocked} />
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
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Fonte</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selFontes}
              onChange={setSelFontes} options={opt(filters.fontes || [])} maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 130 }}>
            <div style={labelStyle}>Apuração</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selApuracoes}
              onChange={setSelApuracoes} options={opt(filters.apuracoes || [])} maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Centro de Lucro</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selNoHier}
              onChange={setSelNoHier} options={opt(filters.no_hierarquias || [])} maxTagCount="responsive" placeholder="Todos" allowClear />
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
        <Table
          dataSource={isMensal
            ? pivotTableData
            : filteredClientes.map((d, i) => ({ ...d, key: `${d.nome_cliente}_${i}` }))}
          columns={clienteCols}
          size="small"
          pagination={isMensal
            ? false
            : { defaultPageSize: 50, showSizeChanger: true, pageSizeOptions: ["20", "50", "100", "200"] }}
          scroll={{ x: isMensal ? "max-content" : 900 }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={(row: any) => ({ style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : {} })}
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
                onClick={() => exportTableToExcel(clienteCols, isMensal ? pivotClientes : filteredClientes, "nova_base_margem_clientes")}>Excel</Button>
            </div>
          )}
          summary={isMensal ? undefined : () => {
            const cells: React.ReactNode[] = [];
            let idx = 0;
            cells.push(<Table.Summary.Cell key="lbl" index={idx++}>TOTAL ({filteredClientes.length})</Table.Summary.Cell>);
            cells.push(<Table.Summary.Cell key="bu" index={idx++} />);
            cells.push(<Table.Summary.Cell key="cl" index={idx++} />);
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
      <DetalheCelulaModal
        open={drillOpen}
        onClose={() => setDrillOpen(false)}
        filters={drillFilters}
        titulo={drillTitulo}
        metricLabel={drillMetric}
      />
    </div>
  );
}

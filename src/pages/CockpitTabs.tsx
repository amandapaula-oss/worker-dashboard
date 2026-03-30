import React, { useCallback, useEffect, useRef, useState } from "react";
import { Select, Table, message, Button } from "antd";
import { DownloadOutlined, FilterOutlined } from "@ant-design/icons";
import { getNexusFilters, getDre, getStreams, getMatricial } from "../api";
import { useDraggableColumns } from "../hooks/useDraggableColumns";
import { exportTableToExcel, exportPLTableToExcel } from "../utils/exportExcel";
import PLTable from "../components/PLTable";
import TableSkeleton from "../components/TableSkeleton";
import ErrorState from "../components/ErrorState";
import { theme } from "../theme";


const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const filterBox: React.CSSProperties = {
  background: "#fff", border: "1px solid #dde3f0", borderRadius: 10,
  padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap",
};

// ── DRE por Empresa ────────────────────────────────────────────────────────────

export function DreTab() {
  const [filters, setFilters] = useState<{ anos: number[]; empresas: string[] }>({ anos: [], empresas: [] });
  const [selAnos, setSelAnos] = useState<number[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [tipo, setTipo] = useState("Actual");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filtersReady, setFiltersReady] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const initialLoad = useRef(true);

  const loadInitial = useCallback(() => {
    setLoading(true); setError(false);
    Promise.all([getNexusFilters(), getDre({ tipo })])
      .then(([f, d]) => {
        setFilters(f); setSelAnos(f.anos); setSelEmpresas(f.empresas); setData(d);
        setFiltersReady(true); initialLoad.current = false;
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { loadInitial(); }, [loadInitial]);

  useEffect(() => {
    if (!filtersReady || initialLoad.current) return;
    if (!selAnos.length && filters.anos.length) return;
    setLoading(true);
    const params: Record<string, string> = { tipo };
    if (selAnos.length) params.anos = selAnos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    getDre(params).then(d => setData(d)).catch(() => message.error("Erro ao carregar DRE")).finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selAnos, selEmpresas, tipo]);

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={selAnos.length < filters.anos.length || selEmpresas.length < filters.empresas.length || tipo !== "Actual" ? "primary" : "default"}
          style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>
      {showFilters && (
        <div style={filterBox}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Ano</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selAnos} onChange={setSelAnos}
              options={filters.anos.map(a => ({ label: a, value: a }))} maxTagCount="responsive" />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Tipo</div>
            <Select style={{ width: "100%" }} value={tipo} onChange={setTipo}
              options={[{ label: "Actual", value: "Actual" }, { label: "Budget", value: "Budget" }]} />
          </div>
          <div style={{ flex: 2, minWidth: 200 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas} onChange={setSelEmpresas}
              options={filters.empresas.map(e => ({ label: e, value: e }))} maxTagCount="responsive" />
          </div>
        </div>
      )}
      {loading ? <TableSkeleton rows={12} /> : error ? <ErrorState onRetry={loadInitial} /> : (
        <>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
            <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
              onClick={() => exportPLTableToExcel(data?.rows || [], data?.columns || [], "dre")}>Excel</Button>
          </div>
          <PLTable rows={data?.rows || []} columns={data?.columns || []} />
        </>
      )}
    </div>
  );
}

// ── P&L por Stream ─────────────────────────────────────────────────────────────

export function StreamsTab() {
  const [filters, setFilters] = useState<{ anos: number[]; empresas: string[]; streams: string[] }>({ anos: [], empresas: [], streams: [] });
  const [selAnos, setSelAnos] = useState<number[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [selStreams, setSelStreams] = useState<string[]>([]);
  const [tipo, setTipo] = useState("Actual");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filtersReady, setFiltersReady] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const initialLoad = useRef(true);

  const loadInitial = useCallback(() => {
    setLoading(true); setError(false);
    Promise.all([getNexusFilters(), getStreams({ tipo })])
      .then(([f, d]) => {
        setFilters(f); setSelAnos(f.anos); setSelEmpresas(f.empresas); setSelStreams(f.streams); setData(d);
        setFiltersReady(true); initialLoad.current = false;
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { loadInitial(); }, [loadInitial]);

  useEffect(() => {
    if (!filtersReady || initialLoad.current) return;
    if (!selAnos.length && filters.anos.length) return;
    setLoading(true);
    const params: Record<string, string> = { tipo };
    if (selAnos.length) params.anos = selAnos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selStreams.length) params.streams = selStreams.join(",");
    getStreams(params).then(d => setData(d)).catch(() => message.error("Erro ao carregar Streams")).finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selAnos, selEmpresas, selStreams, tipo]);

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={selAnos.length < filters.anos.length || selEmpresas.length < filters.empresas.length || selStreams.length < filters.streams.length || tipo !== "Actual" ? "primary" : "default"}
          style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>
      {showFilters && (
        <div style={filterBox}>
          <div style={{ flex: 1, minWidth: 120 }}>
            <div style={labelStyle}>Ano</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selAnos} onChange={setSelAnos}
              options={filters.anos.map(a => ({ label: a, value: a }))} maxTagCount="responsive" />
          </div>
          <div style={{ flex: 1, minWidth: 120 }}>
            <div style={labelStyle}>Tipo</div>
            <Select style={{ width: "100%" }} value={tipo} onChange={setTipo}
              options={[{ label: "Actual", value: "Actual" }, { label: "Budget", value: "Budget" }]} />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas} onChange={setSelEmpresas}
              options={filters.empresas.map(e => ({ label: e, value: e }))} maxTagCount="responsive" />
          </div>
          <div style={{ flex: 2, minWidth: 200 }}>
            <div style={labelStyle}>Stream</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selStreams} onChange={setSelStreams}
              options={filters.streams.map(s => ({ label: s, value: s }))} maxTagCount="responsive" />
          </div>
        </div>
      )}
      {loading ? <TableSkeleton rows={12} /> : error ? <ErrorState onRetry={loadInitial} /> : (
        <>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
            <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
              onClick={() => exportPLTableToExcel(data?.rows || [], data?.columns || [], "streams")}>Excel</Button>
          </div>
          <PLTable rows={data?.rows || []} columns={data?.columns || []} />
        </>
      )}
    </div>
  );
}

// ── P&L Matricial ──────────────────────────────────────────────────────────────

export function MatricialTab() {
  const [filters, setFilters] = useState<{ anos: number[] }>({ anos: [] });
  const [selAnos, setSelAnos] = useState<number[]>([]);
  const [tipo, setTipo] = useState("Actual");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filtersReady, setFiltersReady] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const initialLoad = useRef(true);

  const loadInitial = useCallback(() => {
    setLoading(true); setError(false);
    Promise.all([getNexusFilters(), getMatricial({ tipo })])
      .then(([f, d]) => {
        setFilters(f); setSelAnos(f.anos); setData(d);
        setFiltersReady(true); initialLoad.current = false;
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { loadInitial(); }, [loadInitial]);

  useEffect(() => {
    if (!filtersReady || initialLoad.current) return;
    if (!selAnos.length && filters.anos.length) return;
    setLoading(true);
    const params: Record<string, string> = { tipo };
    if (selAnos.length) params.anos = selAnos.join(",");
    getMatricial(params).then(d => setData(d)).catch(() => message.error("Erro ao carregar Matricial")).finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selAnos, tipo]);

  const pctCols: string[] = data?.pct_cols || [];

  const columnsDef = (data?.columns || []).map((col: string) => ({
    title: col,
    dataIndex: col,
    key: col,
    align: col === "Empresa" ? "left" as const : "right" as const,
    render: (v: number | string) => {
      if (typeof v !== "number") return <strong>{v}</strong>;
      const isPct = pctCols.includes(col);
      const formatted = isPct ? `${(v * 100).toFixed(1)}%` : v.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
      const color = v < 0 ? "#c0392b" : theme.text;
      return <span style={{ color }}>{formatted}</span>;
    },
  }));

  const [columns, colSettings] = useDraggableColumns(columnsDef, "matricial");

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={selAnos.length < filters.anos.length || tipo !== "Actual" ? "primary" : "default"}
          style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>
      {showFilters && (
        <div style={filterBox}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Ano</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selAnos} onChange={setSelAnos}
              options={filters.anos.map(a => ({ label: a, value: a }))} maxTagCount="responsive" />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Tipo</div>
            <Select style={{ width: "100%" }} value={tipo} onChange={setTipo}
              options={[{ label: "Actual", value: "Actual" }, { label: "Budget", value: "Budget" }]} />
          </div>
        </div>
      )}
      {loading ? <TableSkeleton rows={8} /> : error ? <ErrorState onRetry={loadInitial} /> : (
        <Table
          dataSource={(data?.data || []).map((d: any, i: number) => ({ ...d, key: i }))}
          columns={columns}
          title={() => (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 4, padding: "0 0 4px" }}>
              {colSettings}
              <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                onClick={() => exportTableToExcel(columns, data?.data || [], "matricial")}>Excel</Button>
            </div>
          )}
          pagination={false}
          size="small"
          scroll={{ x: "max-content" }}
          rowClassName={(record: any) => record["Empresa"] === "Total" ? "total-row" : ""}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
        />
      )}
    </div>
  );
}

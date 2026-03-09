import React, { useEffect, useState } from "react";
import { Select, Spin, Table } from "antd";
import { getNexusFilters, getDre, getStreams, getMatricial } from "../api";
import PLTable from "../components/PLTable";

const { Title } = Typography;

const labelStyle: React.CSSProperties = {
  color: "#3a4f7a", fontSize: "0.8rem", fontWeight: 600,
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

  useEffect(() => {
    getNexusFilters().then(f => {
      setFilters(f);
      setSelAnos(f.anos);
      setSelEmpresas(f.empresas);
    });
  }, []);

  useEffect(() => {
    if (!selAnos.length && filters.anos.length) return;
    setLoading(true);
    const params: Record<string, string> = { tipo };
    if (selAnos.length) params.anos = selAnos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    getDre(params).then(d => { setData(d); setLoading(false); });
  }, [selAnos, selEmpresas, tipo, filters]);

  return (
    <div>
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
      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <PLTable rows={data?.rows || []} columns={data?.columns || []} />
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

  useEffect(() => {
    getNexusFilters().then(f => {
      setFilters(f);
      setSelAnos(f.anos);
      setSelEmpresas(f.empresas);
      setSelStreams(f.streams);
    });
  }, []);

  useEffect(() => {
    if (!selAnos.length && filters.anos.length) return;
    setLoading(true);
    const params: Record<string, string> = { tipo };
    if (selAnos.length) params.anos = selAnos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selStreams.length) params.streams = selStreams.join(",");
    getStreams(params).then(d => { setData(d); setLoading(false); });
  }, [selAnos, selEmpresas, selStreams, tipo, filters]);

  return (
    <div>
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
      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <PLTable rows={data?.rows || []} columns={data?.columns || []} />
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

  useEffect(() => {
    getNexusFilters().then(f => { setFilters(f); setSelAnos(f.anos); });
  }, []);

  useEffect(() => {
    if (!selAnos.length && filters.anos.length) return;
    setLoading(true);
    const params: Record<string, string> = { tipo };
    if (selAnos.length) params.anos = selAnos.join(",");
    getMatricial(params).then(d => { setData(d); setLoading(false); });
  }, [selAnos, tipo, filters]);

  const pctCols: string[] = data?.pct_cols || [];

  const columns = (data?.columns || []).map((col: string) => ({
    title: col,
    dataIndex: col,
    key: col,
    align: col === "Empresa" ? "left" as const : "right" as const,
    render: (v: number | string) => {
      if (typeof v !== "number") return <strong>{v}</strong>;
      const isPct = pctCols.includes(col);
      const formatted = isPct ? `${(v * 100).toFixed(1)}%` : v.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
      const color = v < 0 ? "#c0392b" : "#1a2e5a";
      return <span style={{ color }}>{formatted}</span>;
    },
  }));

  return (
    <div>
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
      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <Table
          dataSource={(data?.data || []).map((d: any, i: number) => ({ ...d, key: i }))}
          columns={columns}
          pagination={false}
          size="small"
          scroll={{ x: "max-content" }}
          rowClassName={(record) => record["Empresa"] === "Total" ? "total-row" : ""}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
        />
      )}
    </div>
  );
}

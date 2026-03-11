import React, { useEffect, useState } from "react";
import { Select, Table, Spin, message, Card, Statistic } from "antd";
import { getRazaoFilters, getRazaoComparativo } from "../api";

const labelStyle: React.CSSProperties = {
  color: "#3a4f7a", fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function DiffCell({ value }: { value: number }) {
  if (value === 0) return <span style={{ color: "#888" }}>—</span>;
  const color = Math.abs(value) < 1 ? "#888" : value > 0 ? "#0a7a3e" : "#c0392b";
  const sign  = value > 0 ? "+" : "";
  return <span style={{ color, fontWeight: 600 }}>{sign}{brl(value)}</span>;
}

export default function CheckLucasTab() {
  const [periodos, setPeriodos]       = useState<string[]>([]);
  const [selPeriodos, setSelPeriodos] = useState<string[]>([]);
  const [empresas, setEmpresas]       = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [filtersReady, setFiltersReady] = useState(false);

  const [rows, setRows]     = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRazaoFilters()
      .then(f => {
        // Only show oct-dec 2025 by default (our cost data range)
        const defaultPeriodos = f.periodos.filter((p: string) => p >= "2025-10");
        setPeriodos(f.periodos);
        setSelPeriodos(defaultPeriodos.length ? defaultPeriodos : f.periodos);
        setEmpresas(f.empresas);
        setSelEmpresas(f.empresas);
        setFiltersReady(true);
      })
      .catch(() => { message.error("Erro ao carregar filtros"); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!filtersReady) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    getRazaoComparativo(params)
      .then(d => setRows(d))
      .catch(() => message.error("Erro ao carregar comparativo"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selPeriodos, selEmpresas]);

  const totReceita    = rows.reduce((s, r) => s + (Number(r.receita)       || 0), 0);
  const totRecRazao  = rows.reduce((s, r) => s + (Number(r.receita_razao) || 0), 0);
  const totCusto     = rows.reduce((s, r) => s + (Number(r.custo_rateado) || 0), 0);
  const totCusRazao  = rows.reduce((s, r) => s + (Number(r.custo_razao)   || 0), 0);
  const totMargem    = rows.reduce((s, r) => s + (Number(r.margem)        || 0), 0);
  const totMarRazao  = rows.reduce((s, r) => s + (Number(r.margem_razao)  || 0), 0);

  const columns = [
    {
      title: "Período", dataIndex: "periodo", key: "periodo", width: 100,
      sorter: (a: any, b: any) => String(a.periodo).localeCompare(String(b.periodo)),
    },
    {
      title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130,
      sorter: (a: any, b: any) => String(a.empresa).localeCompare(String(b.empresa)),
    },
    // Receita
    {
      title: "Receita (RAC)", dataIndex: "receita", key: "receita", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Net Revenue (Razão)", dataIndex: "receita_razao", key: "receita_razao", width: 175,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita_razao) || 0) - (Number(b.receita_razao) || 0),
      render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Δ Receita", dataIndex: "diff_receita", key: "diff_receita", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.diff_receita) || 0) - (Number(b.diff_receita) || 0),
      render: (v: number) => <DiffCell value={v || 0} />,
    },
    // Custo
    {
      title: "Custo Rateado (RAC)", dataIndex: "custo_rateado", key: "custo_rateado", width: 175,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_rateado) || 0) - (Number(b.custo_rateado) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Payroll+3P (Razão)", dataIndex: "custo_razao", key: "custo_razao", width: 175,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_razao) || 0) - (Number(b.custo_razao) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Δ Custo", dataIndex: "diff_custo", key: "diff_custo", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.diff_custo) || 0) - (Number(b.diff_custo) || 0),
      render: (v: number) => <DiffCell value={v || 0} />,
    },
    // Margem
    {
      title: "Margem (RAC)", dataIndex: "margem", key: "margem", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.margem) || 0) - (Number(b.margem) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Margem (Razão)", dataIndex: "margem_razao", key: "margem_razao", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.margem_razao) || 0) - (Number(b.margem_razao) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Δ Margem", dataIndex: "diff_margem", key: "diff_margem", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.diff_margem) || 0) - (Number(b.diff_margem) || 0),
      render: (v: number) => <DiffCell value={v || 0} />,
    },
  ];

  const kpis = [
    { label: "Receita RAC",     value: totReceita,   sub: `Razão: ${brl(totRecRazao)}`,  color: "#1a2e5a" },
    { label: "Δ Receita",       value: totReceita - totRecRazao,  sub: "RAC − Razão", color: Math.abs(totReceita - totRecRazao) < 1 ? "#888" : (totReceita - totRecRazao) > 0 ? "#0a7a3e" : "#c0392b" },
    { label: "Custo RAC",       value: totCusto,     sub: `Razão: ${brl(totCusRazao)}`,  color: totCusto < 0 ? "#c0392b" : "#1a2e5a" },
    { label: "Δ Custo",         value: totCusto - totCusRazao,    sub: "RAC − Razão", color: Math.abs(totCusto - totCusRazao) < 1 ? "#888" : (totCusto - totCusRazao) > 0 ? "#0a7a3e" : "#c0392b" },
    { label: "Margem RAC",      value: totMargem,    sub: `Razão: ${brl(totMarRazao)}`,  color: totMargem < 0 ? "#c0392b" : "#0a7a3e" },
    { label: "Δ Margem",        value: totMargem - totMarRazao,   sub: "RAC − Razão", color: Math.abs(totMargem - totMarRazao) < 1 ? "#888" : (totMargem - totMarRazao) > 0 ? "#0a7a3e" : "#c0392b" },
  ];

  return (
    <div>
      {/* Filtros */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Período</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
            onChange={v => setSelPeriodos(v)}
            options={periodos.map(p => ({ label: p, value: p }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Empresa</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
            onChange={v => setSelEmpresas(v)}
            options={empresas.map(e => ({ label: e, value: e }))} maxTagCount="responsive" />
        </div>
      </div>

      {/* KPI cards */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        {kpis.map(k => (
          <Card key={k.label} style={{ flex: 1, minWidth: 160, borderRadius: 10, border: "1px solid #dde3f0", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}
            styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}>
            <Statistic
              title={<span style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{k.label}</span>}
              value={brl(k.value)}
              valueStyle={{ color: k.color, fontSize: "1.1rem", fontWeight: 700 }}
            />
            <div style={{ color: "#888", fontSize: "0.72rem", marginTop: 2 }}>{k.sub}</div>
          </Card>
        ))}
      </div>

      {/* Tabela */}
      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <Table
          dataSource={rows.map((d, i) => ({ ...d, key: i }))}
          columns={columns}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          summary={() => (
            <Table.Summary.Row style={{ background: "#dce6f7", fontWeight: 700 }}>
              <Table.Summary.Cell index={0} colSpan={2}>Total</Table.Summary.Cell>
              <Table.Summary.Cell index={1} align="right"><span style={{ color: "#1a2e5a" }}>{brl(totReceita)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={2} align="right"><span style={{ color: "#1a2e5a" }}>{brl(totRecRazao)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={3} align="right"><DiffCell value={totReceita - totRecRazao} /></Table.Summary.Cell>
              <Table.Summary.Cell index={4} align="right"><span style={{ color: totCusto < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(totCusto)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={5} align="right"><span style={{ color: totCusRazao < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(totCusRazao)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={6} align="right"><DiffCell value={totCusto - totCusRazao} /></Table.Summary.Cell>
              <Table.Summary.Cell index={7} align="right"><span style={{ color: totMargem < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(totMargem)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={8} align="right"><span style={{ color: totMarRazao < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(totMarRazao)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={9} align="right"><DiffCell value={totMargem - totMarRazao} /></Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      )}
    </div>
  );
}

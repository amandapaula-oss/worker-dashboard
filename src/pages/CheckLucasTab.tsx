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
  if (Math.abs(value) < 1) return <span style={{ color: "#888" }}>—</span>;
  const color = value > 0 ? "#0a7a3e" : "#c0392b";
  const sign  = value > 0 ? "+" : "";
  return <span style={{ color, fontWeight: 600 }}>{sign}{brl(value)}</span>;
}

export default function CheckLucasTab() {
  const [periodos, setPeriodos]       = useState<string[]>([]);
  const [selPeriodos, setSelPeriodos] = useState<string[]>([]);
  const [empresas, setEmpresas]       = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [filtersReady, setFiltersReady] = useState(false);

  const [rows, setRows]       = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRazaoFilters()
      .then(f => {
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

  const sum = (field: string) => rows.reduce((s, r) => s + (Number(r[field]) || 0), 0);

  const totReceita     = sum("receita");
  const totRecRazao    = sum("receita_razao");
  const totCusClt      = sum("custo_clt");
  const totPayroll     = sum("payroll_razao");
  const totCusPj       = sum("custo_pj");
  const totThirdParty  = sum("thirdparty_razao");
  const totMargemRac   = sum("margem_rac");
  const totMargemRazao = sum("margem_razao");

  const columns = [
    {
      title: "Período", dataIndex: "periodo", key: "periodo", width: 100,
      sorter: (a: any, b: any) => String(a.periodo).localeCompare(String(b.periodo)),
    },
    {
      title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130,
      sorter: (a: any, b: any) => String(a.empresa).localeCompare(String(b.empresa)),
    },
    // ── Receita ──────────────────────────────────────────────────────────────
    {
      title: "Receita (RAC)", dataIndex: "receita", key: "receita", width: 150,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Net Revenue (Razão)", dataIndex: "receita_razao", key: "receita_razao", width: 170,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita_razao) || 0) - (Number(b.receita_razao) || 0),
      render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Δ Receita", dataIndex: "diff_receita", key: "diff_receita", width: 145,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.diff_receita) || 0) - (Number(b.diff_receita) || 0),
      render: (v: number) => <DiffCell value={v || 0} />,
    },
    // ── Custo CLT ─────────────────────────────────────────────────────────────
    {
      title: "Custo CLT (RAC)", dataIndex: "custo_clt", key: "custo_clt", width: 150,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_clt) || 0) - (Number(b.custo_clt) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Payroll Costs (Razão)", dataIndex: "payroll_razao", key: "payroll_razao", width: 175,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.payroll_razao) || 0) - (Number(b.payroll_razao) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Δ CLT", dataIndex: "diff_clt", key: "diff_clt", width: 130,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.diff_clt) || 0) - (Number(b.diff_clt) || 0),
      render: (v: number) => <DiffCell value={v || 0} />,
    },
    // ── Custo PJ ──────────────────────────────────────────────────────────────
    {
      title: "Custo PJ (RAC)", dataIndex: "custo_pj", key: "custo_pj", width: 150,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_pj) || 0) - (Number(b.custo_pj) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Third-party Costs (Razão)", dataIndex: "thirdparty_razao", key: "thirdparty_razao", width: 200,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.thirdparty_razao) || 0) - (Number(b.thirdparty_razao) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Δ PJ", dataIndex: "diff_pj", key: "diff_pj", width: 130,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.diff_pj) || 0) - (Number(b.diff_pj) || 0),
      render: (v: number) => <DiffCell value={v || 0} />,
    },
    // ── Margem ────────────────────────────────────────────────────────────────
    {
      title: "Margem (RAC)", dataIndex: "margem_rac", key: "margem_rac", width: 150,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.margem_rac) || 0) - (Number(b.margem_rac) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Margem (Razão)", dataIndex: "margem_razao", key: "margem_razao", width: 150,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.margem_razao) || 0) - (Number(b.margem_razao) || 0),
      render: (v: number) => <span style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span>,
    },
    {
      title: "Δ Margem", dataIndex: "diff_margem", key: "diff_margem", width: 145,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.diff_margem) || 0) - (Number(b.diff_margem) || 0),
      render: (v: number) => <DiffCell value={v || 0} />,
    },
  ];

  const kpis = [
    { label: "Receita RAC",    value: totReceita,               sub: `Razão: ${brl(totRecRazao)}`,   color: "#1a2e5a" },
    { label: "Δ Receita",      value: totReceita - totRecRazao, sub: "RAC − Razão",                  color: Math.abs(totReceita - totRecRazao) < 1 ? "#888" : totReceita > totRecRazao ? "#0a7a3e" : "#c0392b" },
    { label: "Custo CLT (RAC)",value: totCusClt,                sub: `Payroll: ${brl(totPayroll)}`,  color: totCusClt < 0 ? "#c0392b" : "#1a2e5a" },
    { label: "Δ CLT",          value: totCusClt - totPayroll,   sub: "RAC − Razão",                  color: Math.abs(totCusClt - totPayroll) < 1 ? "#888" : totCusClt > totPayroll ? "#0a7a3e" : "#c0392b" },
    { label: "Custo PJ (RAC)", value: totCusPj,                 sub: `3P: ${brl(totThirdParty)}`,    color: totCusPj < 0 ? "#c0392b" : "#1a2e5a" },
    { label: "Δ PJ",           value: totCusPj - totThirdParty, sub: "RAC − Razão",                  color: Math.abs(totCusPj - totThirdParty) < 1 ? "#888" : totCusPj > totThirdParty ? "#0a7a3e" : "#c0392b" },
    { label: "Margem RAC",     value: totMargemRac,             sub: `Razão: ${brl(totMargemRazao)}`,color: totMargemRac < 0 ? "#c0392b" : "#0a7a3e" },
    { label: "Δ Margem",       value: totMargemRac - totMargemRazao, sub: "RAC − Razão",             color: Math.abs(totMargemRac - totMargemRazao) < 1 ? "#888" : totMargemRac > totMargemRazao ? "#0a7a3e" : "#c0392b" },
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
          <Card key={k.label} style={{ flex: 1, minWidth: 150, borderRadius: 10, border: "1px solid #dde3f0", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}
            styles={{ body: { padding: "0.8rem 1rem", textAlign: "center" } }}>
            <Statistic
              title={<span style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{k.label}</span>}
              value={brl(k.value)}
              valueStyle={{ color: k.color, fontSize: "1rem", fontWeight: 700 }}
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
              <Table.Summary.Cell index={1}  align="right"><span style={{ color: "#1a2e5a" }}>{brl(totReceita)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={2}  align="right"><span style={{ color: "#1a2e5a" }}>{brl(totRecRazao)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={3}  align="right"><DiffCell value={totReceita - totRecRazao} /></Table.Summary.Cell>
              <Table.Summary.Cell index={4}  align="right"><span style={{ color: totCusClt < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(totCusClt)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={5}  align="right"><span style={{ color: totPayroll < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(totPayroll)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={6}  align="right"><DiffCell value={totCusClt - totPayroll} /></Table.Summary.Cell>
              <Table.Summary.Cell index={7}  align="right"><span style={{ color: totCusPj < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(totCusPj)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={8}  align="right"><span style={{ color: totThirdParty < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(totThirdParty)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={9}  align="right"><DiffCell value={totCusPj - totThirdParty} /></Table.Summary.Cell>
              <Table.Summary.Cell index={10} align="right"><span style={{ color: totMargemRac < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(totMargemRac)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={11} align="right"><span style={{ color: totMargemRazao < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(totMargemRazao)}</span></Table.Summary.Cell>
              <Table.Summary.Cell index={12} align="right"><DiffCell value={totMargemRac - totMargemRazao} /></Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      )}
    </div>
  );
}

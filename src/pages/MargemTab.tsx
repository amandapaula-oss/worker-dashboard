import React, { useEffect, useState, useMemo } from "react";
import { Select, Table, Spin, message, Button, Typography, Breadcrumb, Card, Statistic, Input } from "antd";
import { HomeOutlined, ArrowLeftOutlined, SearchOutlined } from "@ant-design/icons";
import { getMargemFilters, getMargemProjetos, getMargemPessoas } from "../api";

const { Text } = Typography;

const labelStyle: React.CSSProperties = {
  color: "#3a4f7a", fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function MargemTag({ value }: { value: number | "" }) {
  if (value === "" || value === null || value === undefined) return <span>—</span>;
  const v = Number(value) * 100;
  const color = v >= 30 ? "#0a7a3e" : v >= 10 ? "#856404" : "#c0392b";
  const bg    = v >= 30 ? "#d4edda" : v >= 10 ? "#fff3cd" : "#fde8e8";
  return (
    <span style={{ background: bg, color, fontWeight: 700, padding: "2px 8px", borderRadius: 4, fontSize: "0.85rem" }}>
      {v.toFixed(1)}%
    </span>
  );
}

export default function MargemTab() {
  const [periodos, setPeriodos]       = useState<string[]>([]);
  const [selPeriodos, setSelPeriodos] = useState<string[]>([]);
  const [empresas, setEmpresas]       = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [filtersReady, setFiltersReady] = useState(false);

  const [projetos, setProjetos] = useState<any[]>([]);
  const [pessoas, setPessoas]   = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);

  const [selectedPep, setSelectedPep] = useState<{ pep: string; nome_cliente: string } | null>(null);
  const [searchCliente, setSearchCliente] = useState<string>("");
  const [searchPep, setSearchPep]         = useState<string>("");

  useEffect(() => {
    getMargemFilters()
      .then(f => {
        setPeriodos(f.periodos);
        setSelPeriodos(f.periodos);
        setEmpresas(f.empresas);
        setSelEmpresas(f.empresas);
        setFiltersReady(true);
      })
      .catch(() => { message.error("Erro ao carregar filtros"); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!filtersReady || selectedPep) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    getMargemProjetos(params)
      .then(d => setProjetos(d))
      .catch(() => message.error("Erro ao carregar projetos"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selPeriodos, selEmpresas, selectedPep]);

  useEffect(() => {
    if (!selectedPep) return;
    setLoading(true);
    const params: Record<string, string> = { pep: selectedPep.pep };
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    getMargemPessoas(params)
      .then(d => setPessoas(d))
      .catch(() => message.error("Erro ao carregar pessoas"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPep, selPeriodos, selEmpresas]);

  const filteredProjetos = useMemo(() => {
    let rows = projetos;
    if (searchCliente.trim()) {
      const q = searchCliente.trim().toLowerCase();
      rows = rows.filter(r => String(r.nome_cliente || "").toLowerCase().includes(q));
    }
    if (searchPep.trim()) {
      const q = searchPep.trim().toLowerCase();
      rows = rows.filter(r => String(r.pep || "").toLowerCase().includes(q));
    }
    return rows;
  }, [projetos, searchCliente, searchPep]);

  const colProjetos = [
    {
      title: "PEP", dataIndex: "pep", key: "pep", width: 190,
      sorter: (a: any, b: any) => String(a.pep).localeCompare(String(b.pep)),
    },
    {
      title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true,
      sorter: (a: any, b: any) => String(a.nome_cliente).localeCompare(String(b.nome_cliente)),
    },
    {
      title: "Empresa", dataIndex: "empresa", key: "empresa", width: 120,
      sorter: (a: any, b: any) => String(a.empresa).localeCompare(String(b.empresa)),
    },
    {
      title: "Receita", dataIndex: "receita", key: "receita", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>,
    },
    {
      title: "Custo Rateado", dataIndex: "custo_rateado", key: "custo_rateado", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_rateado) || 0) - (Number(b.custo_rateado) || 0),
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>
      ),
    },
    {
      title: "Margem (R$)", dataIndex: "margem", key: "margem", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.margem) || 0) - (Number(b.margem) || 0),
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v)}</span>
      ),
    },
    {
      title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", width: 100,
      align: "center" as const,
      sorter: (a: any, b: any) => (Number(a.margem_pct) || 0) - (Number(b.margem_pct) || 0),
      render: (v: number | "") => <MargemTag value={v} />,
    },
    {
      title: "Horas", dataIndex: "horas_total", key: "horas_total", width: 80,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.horas_total) || 0) - (Number(b.horas_total) || 0),
      render: (v: number) => v > 0 ? v.toLocaleString("pt-BR") : "—",
    },
  ];

  const colPessoas = [
    {
      title: "Nome", dataIndex: "nome", key: "nome", ellipsis: true,
      sorter: (a: any, b: any) => String(a.nome).localeCompare(String(b.nome)),
    },
    {
      title: "CPF", dataIndex: "cpf", key: "cpf", width: 160,
      sorter: (a: any, b: any) => String(a.cpf).localeCompare(String(b.cpf)),
    },
    {
      title: "Empresa", dataIndex: "empresa", key: "empresa", width: 120,
      sorter: (a: any, b: any) => String(a.empresa).localeCompare(String(b.empresa)),
    },
    {
      title: "Horas", dataIndex: "horas", key: "horas", width: 80,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.horas) || 0) - (Number(b.horas) || 0),
      render: (v: number) => v > 0 ? v.toLocaleString("pt-BR") : "—",
    },
    {
      title: "Receita", dataIndex: "receita", key: "receita", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>,
    },
    {
      title: "Custo Rateado", dataIndex: "custo_rateado", key: "custo_rateado", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_rateado) || 0) - (Number(b.custo_rateado) || 0),
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>
      ),
    },
    {
      title: "Margem (R$)", dataIndex: "margem", key: "margem", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.margem) || 0) - (Number(b.margem) || 0),
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v)}</span>
      ),
    },
    {
      title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", width: 100,
      align: "center" as const,
      sorter: (a: any, b: any) => (Number(a.margem_pct) || 0) - (Number(b.margem_pct) || 0),
      render: (v: number | "") => <MargemTag value={v} />,
    },
  ];

  function summaryRow(rows: any[], colSpan: number, extraCols: number) {
    const receita       = rows.reduce((s, r) => s + (Number(r.receita)       || 0), 0);
    const custo_rateado = rows.reduce((s, r) => s + (Number(r.custo_rateado) || 0), 0);
    const margem        = rows.reduce((s, r) => s + (Number(r.margem)        || 0), 0);
    const margem_pct    = receita !== 0 ? margem / receita : null;
    return (
      <Table.Summary.Row style={{ background: "#dce6f7", fontWeight: 700 }}>
        <Table.Summary.Cell index={0} colSpan={colSpan}>Total</Table.Summary.Cell>
        <Table.Summary.Cell index={1} align="right">
          <span style={{ color: "#1a2e5a" }}>{brl(receita)}</span>
        </Table.Summary.Cell>
        <Table.Summary.Cell index={2} align="right">
          <span style={{ color: custo_rateado < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(custo_rateado)}</span>
        </Table.Summary.Cell>
        <Table.Summary.Cell index={3} align="right">
          <span style={{ color: margem < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(margem)}</span>
        </Table.Summary.Cell>
        <Table.Summary.Cell index={4} align="center">
          <MargemTag value={margem_pct ?? ""} />
        </Table.Summary.Cell>
        {Array.from({ length: extraCols }).map((_, i) => (
          <Table.Summary.Cell key={i} index={5 + i} />
        ))}
      </Table.Summary.Row>
    );
  }

  const breadcrumb = [
    {
      title: (
        <span style={{ cursor: "pointer", color: "#2d50a0" }} onClick={() => setSelectedPep(null)}>
          <HomeOutlined /> Projetos
        </span>
      ),
    },
    ...(selectedPep ? [{
      title: (
        <span style={{ color: "#1a2e5a", fontWeight: 600 }}>
          {selectedPep.pep} — {selectedPep.nome_cliente}
        </span>
      ),
    }] : []),
  ];

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Período</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
            onChange={v => { setSelPeriodos(v); setSelectedPep(null); }}
            options={periodos.map(p => ({ label: p, value: p }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Empresa</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
            onChange={v => { setSelEmpresas(v); setSelectedPep(null); }}
            options={empresas.map(e => ({ label: e, value: e }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Cliente</div>
          <Input
            allowClear
            placeholder="Buscar cliente..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={searchCliente}
            onChange={e => { setSearchCliente(e.target.value); setSelectedPep(null); }}
          />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Projeto (PEP)</div>
          <Input
            allowClear
            placeholder="Buscar PEP..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={searchPep}
            onChange={e => { setSearchPep(e.target.value); setSelectedPep(null); }}
          />
        </div>
        <Text type="secondary" style={{ fontSize: "0.78rem", paddingBottom: 2 }}>
          * Custo rateado disponível para out–dez/2025. Períodos sem custo exibem receita apenas.
        </Text>
      </div>

      {!selectedPep && (() => {
        const receita       = filteredProjetos.reduce((s, r) => s + (Number(r.receita)       || 0), 0);
        const custo_rateado = filteredProjetos.reduce((s, r) => s + (Number(r.custo_rateado) || 0), 0);
        const margem        = filteredProjetos.reduce((s, r) => s + (Number(r.margem)        || 0), 0);
        const margem_pct    = receita !== 0 ? margem / receita : 0;
        return (
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
            {[
              { label: "Receita Total",    value: receita,       color: "#1a2e5a", fmt: "brl" },
              { label: "Custo Rateado",    value: custo_rateado, color: custo_rateado < 0 ? "#c0392b" : "#1a2e5a", fmt: "brl" },
              { label: "Margem Bruta",     value: margem,        color: margem < 0 ? "#c0392b" : "#0a7a3e", fmt: "brl" },
              { label: "Margem %",         value: margem_pct,    color: margem_pct < 0.1 ? "#c0392b" : margem_pct < 0.3 ? "#856404" : "#0a7a3e", fmt: "pct" },
            ].map(k => (
              <Card key={k.label} style={{ flex: 1, minWidth: 170, borderRadius: 10, border: "1px solid #dde3f0", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}
                styles={{ body: { padding: "1rem 1.2rem", textAlign: "center" } }}>
                <Statistic
                  title={<span style={{ color: "#6b7fa3", fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{k.label}</span>}
                  value={k.fmt === "pct"
                    ? `${(k.value * 100).toFixed(1)}%`
                    : `R$ ${k.value.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
                  valueStyle={{ color: k.color, fontSize: "1.25rem", fontWeight: 700 }}
                />
              </Card>
            ))}
          </div>
        );
      })()}

      <Breadcrumb items={breadcrumb} style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 16 }} />

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : selectedPep ? (
        <>
          <Button icon={<ArrowLeftOutlined />} type="link" style={{ color: "#2d50a0", paddingLeft: 0, marginBottom: 12 }}
            onClick={() => setSelectedPep(null)}>
            Voltar para projetos
          </Button>
          <Table
            dataSource={(() => {
              const rec = pessoas.reduce((s,r)=>s+(Number(r.receita)||0),0);
              const cus = pessoas.reduce((s,r)=>s+(Number(r.custo_rateado)||0),0);
              const mar = pessoas.reduce((s,r)=>s+(Number(r.margem)||0),0);
              return [{ key:"__t__", nome:"TOTAL", cpf:"", empresa:"", horas:0, receita:rec, custo_rateado:cus, margem:mar, margem_pct: rec!==0?mar/rec:null, _isTotal:true }, ...pessoas.map((d,i)=>({...d,key:i}))];
            })()}
            columns={colPessoas}
            pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
            size="small"
            scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
            onRow={row => row._isTotal ? { style: { background: "#dce6f7", fontWeight: 700 } } : {}}
          />
        </>
      ) : (
        <Table
          dataSource={(() => {
            const rec = filteredProjetos.reduce((s,r)=>s+(Number(r.receita)||0),0);
            const cus = filteredProjetos.reduce((s,r)=>s+(Number(r.custo_rateado)||0),0);
            const mar = filteredProjetos.reduce((s,r)=>s+(Number(r.margem)||0),0);
            const pct = rec!==0 ? mar/rec : null;
            return [{ key:"__t__", pep:"TOTAL", nome_cliente:"", empresa:"", receita:rec, custo_rateado:cus, margem:mar, margem_pct:pct, horas_total:0, _isTotal:true }, ...filteredProjetos.map((d,i)=>({...d,key:i}))];
          })()}
          columns={colProjetos}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={row => ({
            onClick: () => !row._isTotal && row.horas_total > 0 && setSelectedPep({ pep: row.pep, nome_cliente: row.nome_cliente }),
            style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: row.horas_total > 0 ? "pointer" : "default" },
          })}
        />
      )}
    </div>
  );
}

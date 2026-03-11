import React, { useEffect, useState, useMemo } from "react";
import { Select, Table, Spin, message, Button, Typography, Breadcrumb, Card, Statistic, Input } from "antd";
import { HomeOutlined, ArrowLeftOutlined, SearchOutlined } from "@ant-design/icons";
import { getMargemFilters, getMargemProjetos, getMargemPessoas } from "../api";
import { useDraggableColumns } from "../hooks/useDraggableColumns";

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

  const [selectedCliente, setSelectedCliente] = useState<string | null>(null);
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

  // Projetos filtrados por texto
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

  // Agrupado por cliente (view principal)
  const clientesData = useMemo(() => {
    const map = new Map<string, { nome_cliente: string; receita: number; custo_rateado: number; margem: number; num_projetos: number }>();
    for (const r of filteredProjetos) {
      const k = r.nome_cliente || "";
      if (!map.has(k)) map.set(k, { nome_cliente: k, receita: 0, custo_rateado: 0, margem: 0, num_projetos: 0 });
      const e = map.get(k)!;
      e.receita       += Number(r.receita)       || 0;
      e.custo_rateado += Number(r.custo_rateado) || 0;
      e.margem        += Number(r.margem)        || 0;
      e.num_projetos  += 1;
    }
    return Array.from(map.values())
      .map(r => ({ ...r, margem_pct: r.receita !== 0 ? r.margem / r.receita : null }))
      .sort((a, b) => a.nome_cliente.localeCompare(b.nome_cliente, "pt-BR"));
  }, [filteredProjetos]);

  // Projetos do cliente selecionado
  const projetosCliente = useMemo(() => {
    if (!selectedCliente) return [];
    return filteredProjetos.filter(r => r.nome_cliente === selectedCliente);
  }, [filteredProjetos, selectedCliente]);

  const colClientes = [
    {
      title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true,
      sorter: (a: any, b: any) => String(a.nome_cliente).localeCompare(String(b.nome_cliente), "pt-BR"),
    },
    {
      title: "Projetos", dataIndex: "num_projetos", key: "num_projetos", width: 90,
      align: "center" as const,
      sorter: (a: any, b: any) => (a.num_projetos || 0) - (b.num_projetos || 0),
      render: (v: number) => v || "—",
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

  const colProjetos = [
    {
      title: "PEP", dataIndex: "pep", key: "pep", width: 190,
      sorter: (a: any, b: any) => String(a.pep).localeCompare(String(b.pep)),
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

  const draggableClientes = useDraggableColumns(colClientes);
  const draggableProjetos = useDraggableColumns(colProjetos);
  const draggablePessoas  = useDraggableColumns(colPessoas);

  const breadcrumb = [
    {
      title: (
        <span style={{ cursor: "pointer", color: "#2d50a0" }}
          onClick={() => { setSelectedCliente(null); setSelectedPep(null); }}>
          <HomeOutlined /> Clientes
        </span>
      ),
    },
    ...(selectedCliente ? [{
      title: selectedPep ? (
        <span style={{ cursor: "pointer", color: "#2d50a0" }}
          onClick={() => setSelectedPep(null)}>
          {selectedCliente}
        </span>
      ) : (
        <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{selectedCliente}</span>
      ),
    }] : []),
    ...(selectedPep ? [{
      title: (
        <span style={{ color: "#1a2e5a", fontWeight: 600 }}>
          {selectedPep.pep}
        </span>
      ),
    }] : []),
  ];

  // KPI cards (visíveis só na view de clientes)
  const kpiBlock = !selectedCliente && !selectedPep && (() => {
    const receita       = clientesData.reduce((s, r) => s + r.receita, 0);
    const custo_rateado = clientesData.reduce((s, r) => s + r.custo_rateado, 0);
    const margem        = clientesData.reduce((s, r) => s + r.margem, 0);
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
  })();

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Período</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
            onChange={v => { setSelPeriodos(v); setSelectedCliente(null); setSelectedPep(null); }}
            options={periodos.map(p => ({ label: p, value: p }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Empresa</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
            onChange={v => { setSelEmpresas(v); setSelectedCliente(null); setSelectedPep(null); }}
            options={empresas.map(e => ({ label: e, value: e }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Cliente</div>
          <Input
            allowClear
            placeholder="Buscar cliente..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={searchCliente}
            onChange={e => { setSearchCliente(e.target.value); setSelectedCliente(null); setSelectedPep(null); }}
          />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Projeto (PEP)</div>
          <Input
            allowClear
            placeholder="Buscar PEP..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={searchPep}
            onChange={e => { setSearchPep(e.target.value); setSelectedCliente(null); setSelectedPep(null); }}
          />
        </div>
        <Text type="secondary" style={{ fontSize: "0.78rem", paddingBottom: 2 }}>
          * Custo rateado disponível para out–dez/2025. Períodos sem custo exibem receita apenas.
        </Text>
      </div>

      {kpiBlock}

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
            columns={draggablePessoas}
            pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
            size="small"
            scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
            onRow={row => row._isTotal ? { style: { background: "#dce6f7", fontWeight: 700 } } : {}}
          />
        </>
      ) : selectedCliente ? (
        <>
          <Button icon={<ArrowLeftOutlined />} type="link" style={{ color: "#2d50a0", paddingLeft: 0, marginBottom: 12 }}
            onClick={() => setSelectedCliente(null)}>
            Voltar para clientes
          </Button>
          <Table
            dataSource={(() => {
              const rec = projetosCliente.reduce((s,r)=>s+(Number(r.receita)||0),0);
              const cus = projetosCliente.reduce((s,r)=>s+(Number(r.custo_rateado)||0),0);
              const mar = projetosCliente.reduce((s,r)=>s+(Number(r.margem)||0),0);
              const pct = rec!==0 ? mar/rec : null;
              return [{ key:"__t__", pep:"TOTAL", empresa:"", receita:rec, custo_rateado:cus, margem:mar, margem_pct:pct, horas_total:0, _isTotal:true }, ...projetosCliente.map((d,i)=>({...d,key:i}))];
            })()}
            columns={draggableProjetos}
            pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
            size="small"
            scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
            onRow={row => ({
              onClick: () => !row._isTotal && row.horas_total > 0 && setSelectedPep({ pep: row.pep, nome_cliente: selectedCliente }),
              style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: row.horas_total > 0 ? "pointer" : "default" },
            })}
          />
        </>
      ) : (
        <Table
          dataSource={(() => {
            const rec = clientesData.reduce((s,r)=>s+r.receita,0);
            const cus = clientesData.reduce((s,r)=>s+r.custo_rateado,0);
            const mar = clientesData.reduce((s,r)=>s+r.margem,0);
            const pct = rec!==0 ? mar/rec : null;
            return [{ key:"__t__", nome_cliente:"TOTAL", receita:rec, custo_rateado:cus, margem:mar, margem_pct:pct, num_projetos: clientesData.reduce((s,r)=>s+r.num_projetos,0), _isTotal:true }, ...clientesData.map((d,i)=>({...d,key:i}))];
          })()}
          columns={draggableClientes}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={row => ({
            onClick: () => !(row as any)._isTotal && setSelectedCliente(row.nome_cliente),
            style: (row as any)._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: "pointer" },
          })}
        />
      )}
    </div>
  );
}

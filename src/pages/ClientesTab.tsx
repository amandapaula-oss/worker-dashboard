import React, { useEffect, useState, useMemo, useRef } from "react";
import { Table, Input, Select, Spin, message, Button, Breadcrumb, Typography, Tag } from "antd";
import { HomeOutlined, SearchOutlined, EditOutlined, CheckOutlined, CloseOutlined } from "@ant-design/icons";
import { getClientes, updateClienteAe, getMargemProjetos, getMargemPessoas } from "../api";

const { Text } = Typography;

const brl = (v: any) =>
  Number(v) ? Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "—";

function MargemTag({ value }: { value: any }) {
  if (value === "" || value === null || value === undefined || value === 0) return <span style={{ color: "#aaa" }}>—</span>;
  const v = Number(value) * 100;
  const color = v >= 30 ? "#0a7a3e" : v >= 10 ? "#856404" : "#c0392b";
  const bg    = v >= 30 ? "#d4edda" : v >= 10 ? "#fff3cd" : "#fde8e8";
  return (
    <span style={{ background: bg, color, fontWeight: 700, padding: "2px 8px", borderRadius: 4, fontSize: "0.85rem" }}>
      {v.toFixed(1)}%
    </span>
  );
}

const labelStyle: React.CSSProperties = {
  color: "#3a4f7a", fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const BU_COLORS: Record<string, string> = {
  "Finance": "#1677ff",
  "Retail": "#52c41a",
  "Health": "#eb2f96",
  "Multisector": "#fa8c16",
  "Grupo Mult": "#722ed1",
};

function BuTag({ bu }: { bu: string }) {
  const color = BU_COLORS[bu] || "#aaa";
  return <Tag color={color} style={{ fontWeight: 600 }}>{bu || "—"}</Tag>;
}

function AeCell({ row, onSave }: { row: any; onSave: (nome: string, ae: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(row.ae || "");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<any>(null);

  useEffect(() => { setValue(row.ae || ""); }, [row.ae]);
  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  const save = async () => {
    setSaving(true);
    try {
      await onSave(row.nome_cliente, value);
      setEditing(false);
    } catch {
      message.error("Erro ao salvar AE");
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => { setValue(row.ae || ""); setEditing(false); };

  if (editing) {
    return (
      <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <Input
          ref={inputRef}
          size="small"
          value={value}
          onChange={e => setValue(e.target.value)}
          onPressEnter={save}
          onKeyDown={e => e.key === "Escape" && cancel()}
          style={{ width: 220 }}
        />
        <Button size="small" type="link" icon={<CheckOutlined />} loading={saving} onClick={save} style={{ color: "#0a7a3e", padding: 0 }} />
        <Button size="small" type="link" icon={<CloseOutlined />} onClick={cancel} style={{ color: "#c0392b", padding: 0 }} />
      </span>
    );
  }
  return (
    <span style={{ display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }}
      onClick={e => { e.stopPropagation(); setEditing(true); }}>
      <span style={{ color: value ? "#1a2e5a" : "#aaa" }}>{value || "— sem AE"}</span>
      <EditOutlined style={{ color: "#aab4cc", fontSize: 12 }} />
    </span>
  );
}

export default function ClientesTab() {
  const [clientes, setClientes]           = useState<any[]>([]);
  const [loading, setLoading]             = useState(true);
  const [search, setSearch]               = useState("");
  const [selBu, setSelBu]                 = useState<string[]>([]);
  const [selAe, setSelAe]                 = useState<string[]>([]);
  const [selectedCliente, setSelectedCliente] = useState<string | null>(null);
  const [projetos, setProjetos]           = useState<any[]>([]);
  const [loadingProj, setLoadingProj]     = useState(false);
  const [selectedPep, setSelectedPep]     = useState<{ pep: string; nome_cliente: string } | null>(null);
  const [pessoas, setPessoas]             = useState<any[]>([]);
  const [loadingPess, setLoadingPess]     = useState(false);

  useEffect(() => {
    setLoading(true);
    getClientes()
      .then((d: any[]) => setClientes(d))
      .catch(() => message.error("Erro ao carregar clientes"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedCliente) return;
    setLoadingProj(true);
    getMargemProjetos({ nome_cliente: selectedCliente })
      .then((d: any[]) => setProjetos(d))
      .catch(() => message.error("Erro ao carregar projetos"))
      .finally(() => setLoadingProj(false));
  }, [selectedCliente]);

  useEffect(() => {
    if (!selectedPep) return;
    setLoadingPess(true);
    getMargemPessoas({ pep: selectedPep.pep })
      .then((d: any[]) => setPessoas(d))
      .catch(() => message.error("Erro ao carregar pessoas"))
      .finally(() => setLoadingPess(false));
  }, [selectedPep]);

  const bus   = useMemo(() => [...new Set(clientes.map(c => c.bu).filter(Boolean))].sort(), [clientes]);
  const aes   = useMemo(() => [...new Set(clientes.map(c => c.ae).filter(Boolean))].sort(), [clientes]);

  const filtered = useMemo(() => {
    let rows = clientes;
    if (search.trim()) {
      const q = search.trim().toUpperCase();
      rows = rows.filter(r => String(r.nome_cliente || "").toUpperCase().includes(q));
    }
    if (selBu.length) rows = rows.filter(r => selBu.includes(r.bu));
    if (selAe.length) rows = rows.filter(r => selAe.includes(r.ae));
    return rows;
  }, [clientes, search, selBu, selAe]);

  const handleSaveAe = async (nome_cliente: string, ae: string) => {
    await updateClienteAe(nome_cliente, ae);
    setClientes(prev => prev.map(c => c.nome_cliente === nome_cliente ? { ...c, ae } : c));
  };

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
      title: <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{selectedPep.pep}</span>,
    }] : []),
  ];

  // ── Columns ────────────────────────────────────────────────────────────────

  const colClientes = [
    {
      title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true,
      sorter: (a: any, b: any) => String(a.nome_cliente).localeCompare(String(b.nome_cliente), "pt-BR"),
    },
    {
      title: "BU", dataIndex: "bu", key: "bu", width: 130,
      render: (v: string) => <BuTag bu={v} />,
      sorter: (a: any, b: any) => String(a.bu).localeCompare(String(b.bu)),
    },
    {
      title: "AE", dataIndex: "ae", key: "ae", width: 260,
      render: (_: any, row: any) => <AeCell row={row} onSave={handleSaveAe} />,
      sorter: (a: any, b: any) => String(a.ae || "").localeCompare(String(b.ae || ""), "pt-BR"),
    },
    {
      title: "Receita", dataIndex: "receita", key: "receita", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: any) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>,
    },
    {
      title: "Custo", dataIndex: "custo_rateado", key: "custo_rateado", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_rateado) || 0) - (Number(b.custo_rateado) || 0),
      render: (v: any) => <span style={{ color: Number(v) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>,
    },
    {
      title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", width: 100,
      align: "center" as const,
      sorter: (a: any, b: any) => (Number(a.margem_pct) || 0) - (Number(b.margem_pct) || 0),
      render: (v: any) => <MargemTag value={v} />,
    },
    {
      title: "Projetos", dataIndex: "num_projetos", key: "num_projetos", width: 85,
      align: "center" as const,
      sorter: (a: any, b: any) => (Number(a.num_projetos) || 0) - (Number(b.num_projetos) || 0),
      render: (v: any) => v || "—",
    },
  ];

  const colProjetos = [
    { title: "PEP", dataIndex: "pep", key: "pep", width: 190,
      sorter: (a: any, b: any) => String(a.pep).localeCompare(String(b.pep)) },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 120 },
    { title: "Nó Hierarquia", dataIndex: "no_hierarquia", key: "no_hierarquia", width: 130 },
    { title: "BU", dataIndex: "categoria_bu", key: "categoria_bu", width: 110 },
    { title: "Receita", dataIndex: "receita", key: "receita", width: 155, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: any) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Custo", dataIndex: "custo_rateado", key: "custo_rateado", width: 155, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_rateado) || 0) - (Number(b.custo_rateado) || 0),
      render: (v: any) => <span style={{ color: Number(v) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", width: 100, align: "center" as const,
      sorter: (a: any, b: any) => (Number(a.margem_pct) || 0) - (Number(b.margem_pct) || 0),
      render: (v: any) => <MargemTag value={v} /> },
    { title: "Horas", dataIndex: "horas_total", key: "horas_total", width: 80, align: "right" as const,
      render: (v: any) => Number(v) > 0 ? Number(v).toLocaleString("pt-BR") : "—" },
  ];

  const colPessoas = [
    { title: "Nome", dataIndex: "nome", key: "nome", ellipsis: true,
      sorter: (a: any, b: any) => String(a.nome).localeCompare(String(b.nome), "pt-BR") },
    { title: "ID", dataIndex: "numero_pessoal", key: "numero_pessoal", width: 110 },
    { title: "CPF", dataIndex: "cpf", key: "cpf", width: 150 },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 120 },
    { title: "Horas", dataIndex: "horas", key: "horas", width: 80, align: "right" as const,
      render: (v: any) => Number(v) > 0 ? Number(v).toLocaleString("pt-BR") : "—" },
    { title: "Receita", dataIndex: "receita", key: "receita", width: 155, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: any) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Custo", dataIndex: "custo_rateado", key: "custo_rateado", width: 155, align: "right" as const,
      render: (v: any) => <span style={{ color: Number(v) < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", width: 100, align: "center" as const,
      render: (v: any) => <MargemTag value={v} /> },
  ];

  // ── Render ─────────────────────────────────────────────────────────────────

  const tableStyle = { borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" };
  const pagination = { pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] };

  return (
    <div>
      {/* Filter bar */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 2, minWidth: 200 }}>
          <div style={labelStyle}>Buscar cliente</div>
          <Input
            allowClear
            placeholder="Nome do cliente..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div style={{ flex: 1, minWidth: 150 }}>
          <div style={labelStyle}>BU</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selBu}
            onChange={v => setSelBu(v)}
            options={bus.map(b => ({ label: b, value: b }))}
            maxTagCount="responsive" placeholder="Todas" />
        </div>
        <div style={{ flex: 2, minWidth: 200 }}>
          <div style={labelStyle}>AE</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selAe}
            onChange={v => setSelAe(v)}
            options={aes.map(a => ({ label: a, value: a }))}
            maxTagCount="responsive" placeholder="Todos" />
        </div>
      </div>

      <Breadcrumb items={breadcrumb} style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 16 }} />

      {loading ? <Spin style={{ display: "block", margin: "3rem auto" }} /> :

      selectedPep ? (
        <>
          <Button type="link" style={{ color: "#2d50a0", paddingLeft: 0, marginBottom: 12 }}
            onClick={() => setSelectedPep(null)}>← Voltar para projetos</Button>
          {loadingPess ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
            <Table
              dataSource={pessoas.map((d, i) => ({ ...d, key: i }))}
              columns={colPessoas}
              pagination={pagination}
              size="small"
              scroll={{ x: "max-content" }}
              style={tableStyle}
            />
          )}
        </>
      ) : selectedCliente ? (
        <>
          <Button type="link" style={{ color: "#2d50a0", paddingLeft: 0, marginBottom: 12 }}
            onClick={() => { setSelectedCliente(null); setSelectedPep(null); }}>← Voltar para clientes</Button>
          {loadingProj ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
            <Table
              dataSource={projetos.map((d, i) => ({ ...d, key: i }))}
              columns={colProjetos}
              pagination={pagination}
              size="small"
              scroll={{ x: "max-content" }}
              style={tableStyle}
              onRow={row => ({
                onClick: () => setSelectedPep({ pep: row.pep, nome_cliente: selectedCliente }),
                style: { cursor: "pointer" },
              })}
            />
          )}
        </>
      ) : (
        <Table
          dataSource={filtered.map((d, i) => ({ ...d, key: i }))}
          columns={colClientes}
          pagination={pagination}
          size="small"
          scroll={{ x: "max-content" }}
          style={tableStyle}
          onRow={row => ({
            onClick: () => setSelectedCliente(row.nome_cliente),
            style: { cursor: "pointer" },
          })}
        />
      )}
    </div>
  );
}

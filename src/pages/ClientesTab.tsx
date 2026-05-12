import React, { useEffect, useState, useMemo, useRef } from "react";
import { Table, Input, Select, Spin, message, Button, Breadcrumb, Tag } from "antd";
import { HomeOutlined, SearchOutlined, EditOutlined, CheckOutlined, CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { getClientes, updateClienteAe, getMargemProjetos, getMargemPessoas } from "../api";
import { useDraggableColumns } from "../hooks/useDraggableColumns";
import { exportTableToExcel } from "../utils/exportExcel";
import { toTitleCase } from "../utils/format";
import { theme } from "../theme";

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
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const BU_COLORS: Record<string, { color: string; bg: string }> = {
  "Finance":    { color: theme.cat1.main, bg: theme.cat1.bg },
  "Retail":     { color: theme.cat4.main, bg: theme.cat4.bg },
  "Health":     { color: theme.cat3.main, bg: theme.cat3.bg },
  "Multisector":{ color: theme.cat3.main, bg: theme.cat3.bg },
  "Grupo Mult": { color: theme.cat3.main, bg: theme.cat3.bg },
};

function BuTag({ bu }: { bu: string }) {
  const colors = BU_COLORS[bu] || { color: theme.cat2.main, bg: theme.cat2.bg };
  return (
    <span style={{ background: colors.bg, color: colors.color, fontWeight: 600, padding: "2px 8px", borderRadius: 4, fontSize: "0.85rem", display: "inline-block" }}>
      {bu || "—"}
    </span>
  );
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
      <span style={{ color: value ? theme.text : "#aaa" }}>{value || "— sem AE"}</span>
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
    getMargemPessoas({ pep: selectedPep.pep, breakdown: "true" })
      .then((d: any[]) => setPessoas(d))
      .catch(() => message.error("Erro ao carregar pessoas"))
      .finally(() => setLoadingPess(false));
  }, [selectedPep]);

  // Pivota pessoas por (pessoa, mes) — colunas dinâmicas por período
  const pessoasPivot = useMemo(() => {
    if (!pessoas.length) return { rows: [] as any[], periodos: [] as string[] };
    const periodos = Array.from(new Set(pessoas.map(p => p.periodo).filter(Boolean))).sort() as string[];
    const map = new Map<string, any>();
    for (const p of pessoas) {
      const key = `${p.cpf}|${p.nome}|${p.empresa}`;
      if (!map.has(key)) {
        map.set(key, {
          cpf: p.cpf, nome: p.nome, empresa: p.empresa,
          numero_pessoal: p.numero_pessoal || "",
          total_receita: 0, total_custo: 0, total_horas: 0,
        });
      }
      const e = map.get(key);
      const rec = Number(p.receita) || 0;
      const cus = Number(p.custo_rateado) || 0;
      const hrs = Number(p.horas) || 0;
      e[`${p.periodo}_receita`] = (e[`${p.periodo}_receita`] || 0) + rec;
      e[`${p.periodo}_custo`]   = (e[`${p.periodo}_custo`]   || 0) + cus;
      e[`${p.periodo}_horas`]   = (e[`${p.periodo}_horas`]   || 0) + hrs;
      e.total_receita += rec;
      e.total_custo   += cus;
      e.total_horas   += hrs;
    }
    const rows = Array.from(map.values()).map(r => ({
      ...r,
      total_margem: r.total_receita + r.total_custo,
      total_margem_pct: r.total_receita !== 0 ? (r.total_receita + r.total_custo) / r.total_receita : null,
    })).sort((a, b) => (b.total_receita || 0) - (a.total_receita || 0));
    return { rows, periodos };
  }, [pessoas]);

  // Info do projeto (quando pessoas vazias — WIP, etc)
  const projetoSelecionado = useMemo(() => {
    if (!selectedPep) return null;
    return projetos.find(p => p.pep === selectedPep.pep) || null;
  }, [projetos, selectedPep]);

  const bus   = useMemo(() => Array.from(new Set(clientes.map(c => c.bu).filter(Boolean))).sort(), [clientes]);
  const aes   = useMemo(() => Array.from(new Set(clientes.map(c => c.ae).filter(Boolean))).sort(), [clientes]);
  const wss   = useMemo(() => Array.from(new Set(clientes.map(c => c.ws).filter(Boolean))).sort(), [clientes]);
  const [selWs, setSelWs] = useState<string[]>([]);

  const filtered = useMemo(() => {
    let rows = clientes;
    if (search.trim()) {
      const q = search.trim().toUpperCase();
      rows = rows.filter(r =>
        String(r.nome_cliente || "").toUpperCase().includes(q) ||
        String(r.nome_base || "").toUpperCase().includes(q)
      );
    }
    if (selBu.length) rows = rows.filter(r => selBu.includes(r.bu));
    if (selAe.length) rows = rows.filter(r => selAe.includes(r.ae));
    if (selWs.length) rows = rows.filter(r => selWs.includes(r.ws));
    return rows;
  }, [clientes, search, selBu, selAe, selWs]);

  const handleSaveAe = async (nome_cliente: string, ae: string) => {
    await updateClienteAe(nome_cliente, ae);
    setClientes(prev => prev.map(c => c.nome_cliente === nome_cliente ? { ...c, ae } : c));
  };

  const breadcrumb = [
    {
      title: (
        <span style={{ cursor: "pointer", color: theme.link }}
          onClick={() => { setSelectedCliente(null); setSelectedPep(null); }}>
          <HomeOutlined /> Clientes
        </span>
      ),
    },
    ...(selectedCliente ? [{
      title: selectedPep ? (
        <span style={{ cursor: "pointer", color: theme.link }}
          onClick={() => setSelectedPep(null)}>
          {selectedCliente}
        </span>
      ) : (
        <span style={{ color: theme.text, fontWeight: 600 }}>{selectedCliente}</span>
      ),
    }] : []),
    ...(selectedPep ? [{
      title: <span style={{ color: theme.text, fontWeight: 600 }}>{selectedPep.pep}</span>,
    }] : []),
  ];

  // ── Columns ────────────────────────────────────────────────────────────────

  const colClientes = [
    {
      title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true,
      sorter: (a: any, b: any) => String(a.nome_cliente).localeCompare(String(b.nome_cliente), "pt-BR"),
      render: (v: string) => toTitleCase(v) || "—",
    },
    {
      title: "BU", dataIndex: "bu", key: "bu", width: 130,
      render: (v: string) => <BuTag bu={v} />,
      sorter: (a: any, b: any) => String(a.bu).localeCompare(String(b.bu)),
    },
    {
      title: "WS", dataIndex: "ws", key: "ws", width: 110,
      sorter: (a: any, b: any) => String(a.ws || "").localeCompare(String(b.ws || ""), "pt-BR"),
      render: (v: string) => v ? <Tag>{v}</Tag> : <span style={{ color: "#aaa" }}>—</span>,
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
      render: (v: any) => <span style={{ color: theme.text, fontWeight: 600 }}>{brl(v)}</span>,
    },
    {
      title: "Custo", dataIndex: "custo_rateado", key: "custo_rateado", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_rateado) || 0) - (Number(b.custo_rateado) || 0),
      render: (v: any) => <span style={{ color: Number(v) < 0 ? "#c0392b" : theme.text, fontWeight: 600 }}>{brl(v)}</span>,
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
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 120, render: (v: string) => toTitleCase(v) || "—" },
    { title: "Nó Hierarquia", dataIndex: "no_hierarquia", key: "no_hierarquia", width: 130 },
    { title: "BU", dataIndex: "categoria_bu", key: "categoria_bu", width: 110 },
    { title: "Receita", dataIndex: "receita", key: "receita", width: 155, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: any) => <span style={{ color: theme.text, fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Custo", dataIndex: "custo_rateado", key: "custo_rateado", width: 155, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_rateado) || 0) - (Number(b.custo_rateado) || 0),
      render: (v: any) => <span style={{ color: Number(v) < 0 ? "#c0392b" : theme.text, fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", width: 100, align: "center" as const,
      sorter: (a: any, b: any) => (Number(a.margem_pct) || 0) - (Number(b.margem_pct) || 0),
      render: (v: any) => <MargemTag value={v} /> },
    { title: "Horas", dataIndex: "horas_total", key: "horas_total", width: 80, align: "right" as const,
      render: (v: any) => Number(v) > 0 ? Number(v).toLocaleString("pt-BR") : "—" },
  ];

  const colPessoas = useMemo(() => {
    const base: any[] = [
      { title: "Nome", dataIndex: "nome", key: "nome", width: 220, fixed: "left", ellipsis: true,
        sorter: (a: any, b: any) => String(a.nome).localeCompare(String(b.nome), "pt-BR"),
        render: (v: string) => toTitleCase(v) || "—" },
      { title: "ID",  dataIndex: "numero_pessoal", key: "numero_pessoal", width: 90 },
      { title: "CPF", dataIndex: "cpf", key: "cpf", width: 130 },
      { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 110,
        render: (v: string) => toTitleCase(v) || "—" },
    ];
    // Colunas dinâmicas por período (receita/custo/horas por mês)
    for (const p of pessoasPivot.periodos) {
      base.push({
        title: p, key: `g_${p}`,
        children: [
          { title: "Receita", dataIndex: `${p}_receita`, key: `${p}_r`, width: 110, align: "right" as const,
            render: (v: any) => v ? brl(v) : "—" },
          { title: "Custo", dataIndex: `${p}_custo`, key: `${p}_c`, width: 110, align: "right" as const,
            render: (v: any) => v ? <span style={{ color: Number(v) < 0 ? "#c0392b" : theme.text }}>{brl(v)}</span> : "—" },
          { title: "Horas", dataIndex: `${p}_horas`, key: `${p}_h`, width: 70, align: "right" as const,
            render: (v: any) => Number(v) > 0 ? Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) : "—" },
        ]
      });
    }
    base.push({
      title: "Total", key: "tot",
      children: [
        { title: "Receita", dataIndex: "total_receita", key: "tr", width: 130, align: "right" as const,
          fixed: "right",
          sorter: (a: any, b: any) => (Number(a.total_receita) || 0) - (Number(b.total_receita) || 0),
          render: (v: any) => <span style={{ color: theme.text, fontWeight: 700 }}>{brl(v)}</span> },
        { title: "Custo", dataIndex: "total_custo", key: "tc", width: 130, align: "right" as const,
          fixed: "right",
          render: (v: any) => <span style={{ color: Number(v) < 0 ? "#c0392b" : theme.text, fontWeight: 700 }}>{brl(v)}</span> },
        { title: "Margem %", dataIndex: "total_margem_pct", key: "tm", width: 100, align: "center" as const,
          fixed: "right",
          render: (v: any) => <MargemTag value={v} /> },
      ]
    });
    return base;
  }, [pessoasPivot.periodos]);

  const [colsClientes,  settingsClientes]  = useDraggableColumns(colClientes, "clientes-main");
  const [colsProjetos,  settingsProjetos]  = useDraggableColumns(colProjetos, "clientes-projetos");
  const [colsPessoas,   settingsPessoas]   = useDraggableColumns(colPessoas, "clientes-pessoas");

  // ── Render ─────────────────────────────────────────────────────────────────

  const tableStyle = { borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" };
  const pagination = { defaultPageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] };

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
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>WS</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selWs}
            onChange={v => setSelWs(v)}
            options={wss.map(w => ({ label: w, value: w }))}
            maxTagCount="responsive" placeholder="Todas" />
        </div>
      </div>

      <Breadcrumb items={breadcrumb} style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 16 }} />

      {loading ? <Spin style={{ display: "block", margin: "3rem auto" }} /> :

      selectedPep ? (
        <>
          <Button type="link" style={{ color: theme.link, paddingLeft: 0, marginBottom: 12 }}
            onClick={() => setSelectedPep(null)}>← Voltar para projetos</Button>
          {loadingPess ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
            <>
              {pessoasPivot.rows.length === 0 && projetoSelecionado && (
                <div style={{ background: "#fffbe6", border: "1px solid #ffe58f", borderRadius: 8, padding: "0.9rem 1.2rem", marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>Sem alocação de pessoas neste PEP</div>
                  <div style={{ color: theme.secondary, fontSize: "0.85rem" }}>
                    Tipo: <b>{projetoSelecionado.tipos || "—"}</b> • Receita total: <b>{brl(projetoSelecionado.receita)}</b> • Custo: <b>{brl(projetoSelecionado.custo_rateado)}</b> • Margem: <b>{projetoSelecionado.margem_pct != null ? `${(projetoSelecionado.margem_pct*100).toFixed(1)}%` : "—"}</b>
                  </div>
                </div>
              )}
              <Table
                dataSource={pessoasPivot.rows.map((d, i) => ({ ...d, key: i }))}
                columns={colsPessoas}
                title={() => (
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 4, padding: "0 0 4px" }}>
                    {settingsPessoas}
                    <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                      onClick={() => exportTableToExcel(colsPessoas, pessoasPivot.rows, "pessoas")}>Excel</Button>
                  </div>
                )}
                pagination={pagination}
                size="small"
                scroll={{ x: "max-content" }}
                style={tableStyle}
              />
            </>
          )}
        </>
      ) : selectedCliente ? (
        <>
          <Button type="link" style={{ color: theme.link, paddingLeft: 0, marginBottom: 12 }}
            onClick={() => { setSelectedCliente(null); setSelectedPep(null); }}>← Voltar para clientes</Button>
          {loadingProj ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
            <Table
              dataSource={projetos.map((d, i) => ({ ...d, key: i }))}
              columns={colsProjetos}
              title={() => (
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 4, padding: "0 0 4px" }}>
                  {settingsProjetos}
                  <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                    onClick={() => exportTableToExcel(colsProjetos, projetos, "projetos")}>Excel</Button>
                </div>
              )}
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
          columns={colsClientes}
          title={() => (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 4, padding: "0 0 4px" }}>
              {settingsClientes}
              <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                onClick={() => exportTableToExcel(colsClientes, filtered, "clientes")}>Excel</Button>
            </div>
          )}
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

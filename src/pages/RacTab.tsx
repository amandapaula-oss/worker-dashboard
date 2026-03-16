import React, { useEffect, useState, useMemo } from "react";
import { Select, Table, Spin, message, Button, Breadcrumb, Input } from "antd";
import { HomeOutlined, ArrowLeftOutlined, SearchOutlined } from "@ant-design/icons";
import { getRacFilters, getRacProjetos, getRacPessoas, getRacPessoaProjetos } from "../api";
import { useDraggableColumns } from "../hooks/useDraggableColumns";


const labelStyle: React.CSSProperties = {
  color: "#3a4f7a", fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function RacTab() {
  const [filters, setFilters] = useState<{ periodos: string[]; empresas: string[]; tipos: string[] }>({
    periodos: [], empresas: [], tipos: [],
  });
  const [selPeriodos, setSelPeriodos] = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [selTipos, setSelTipos]       = useState<string[]>([]);
  const [filtersReady, setFiltersReady] = useState(false);

  const [projetos, setProjetos] = useState<any[]>([]);
  const [pessoas, setPessoas]   = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);

  // drill-down state
  const [selectedPep, setSelectedPep] = useState<{ pep: string; nome_cliente: string } | null>(null);
  const [selectedPessoa, setSelectedPessoa] = useState<{ cpf: string; nome: string; numero_pessoal: string } | null>(null);
  const [pessoaProjetos, setPessoaProjetos] = useState<any[]>([]);
  const [loadingPessoaProj, setLoadingPessoaProj] = useState(false);
  const [searchCliente, setSearchCliente] = useState("");
  const [searchPep, setSearchPep]         = useState("");
  const [searchPessoa, setSearchPessoa]   = useState("");

  // load filters
  useEffect(() => {
    getRacFilters()
      .then(f => {
        setFilters(f);
        setSelPeriodos(f.periodos);
        setSelEmpresas(f.empresas);
        setSelTipos(f.tipos);
        setFiltersReady(true);
      })
      .catch(() => { message.error("Erro ao carregar filtros"); setLoading(false); });
  }, []);

  // load projetos
  useEffect(() => {
    if (!filtersReady || selectedPep) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selTipos.length)    params.tipos    = selTipos.join(",");
    getRacProjetos(params)
      .then(d => setProjetos(d))
      .catch(() => message.error("Erro ao carregar projetos"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selPeriodos, selEmpresas, selTipos, selectedPep]);

  // load all pessoas (for search) or specific PEP (for drill-down)
  useEffect(() => {
    if (!filtersReady) return;
    const params: Record<string, string> = {};
    if (selectedPep) params.pep = selectedPep.pep;
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    getRacPessoas(params)
      .then(d => setPessoas(d))
      .catch(() => message.error("Erro ao carregar pessoas"));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selectedPep, selPeriodos, selEmpresas]);

  // load projetos for a selected pessoa
  useEffect(() => {
    if (!selectedPessoa) return;
    setLoadingPessoaProj(true);
    const params: Record<string, string> = {};
    if (selectedPessoa.cpf) params.cpf = selectedPessoa.cpf;
    else if (selectedPessoa.numero_pessoal) params.numero_pessoal = selectedPessoa.numero_pessoal;
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    getRacPessoaProjetos(params)
      .then(d => setPessoaProjetos(d))
      .catch(() => message.error("Erro ao carregar projetos da pessoa"))
      .finally(() => setLoadingPessoaProj(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPessoa, selPeriodos, selEmpresas]);

  const colProjetos = [
    { title: "PEP", dataIndex: "pep", key: "pep", width: 200 },
    { title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130 },
    {
      title: "Valor Líquido",
      dataIndex: "valor_liquido",
      key: "valor_liquido",
      width: 160,
      align: "right" as const,
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>
      ),
    },
  ];

  const colPessoas = [
    { title: "ID", dataIndex: "numero_pessoal", key: "numero_pessoal", width: 120 },
    { title: "CPF", dataIndex: "cpf", key: "cpf", width: 160 },
    { title: "Nome", dataIndex: "nome", key: "nome", ellipsis: true },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130 },
    {
      title: "Valor Líquido",
      dataIndex: "valor_liquido",
      key: "valor_liquido",
      width: 160,
      align: "right" as const,
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>
      ),
    },
  ];

  const colPessoaProjetos = [
    { title: "PEP", dataIndex: "pep", key: "pep", width: 200 },
    { title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130 },
    {
      title: "Valor Líquido",
      dataIndex: "valor_liquido",
      key: "valor_liquido",
      width: 160,
      align: "right" as const,
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>
      ),
    },
  ];

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

  const filteredPessoas = useMemo(() => {
    const q = searchPessoa.trim().toLowerCase();
    if (!q) return pessoas;
    const qDigits = q.replace(/\D/g, "");
    return pessoas.filter(r => {
      const cpfDigits = String(r.cpf || "").replace(/\D/g, "");
      return (
        String(r.nome || "").toLowerCase().includes(q) ||
        (qDigits && cpfDigits.includes(qDigits)) ||
        String(r.numero_pessoal || "").toLowerCase().includes(q)
      );
    });
  }, [pessoas, searchPessoa]);

  const totalProjetos = filteredProjetos.reduce((s, r) => s + r.valor_liquido, 0);
  const totalPessoas  = filteredPessoas.reduce((s, r) => s + r.valor_liquido, 0);
  const totalPessoaProj = pessoaProjetos.reduce((s, r) => s + (Number(r.valor_liquido) || 0), 0);

  const draggableProjetos     = useDraggableColumns(colProjetos);
  const draggablePessoas      = useDraggableColumns(colPessoas);
  const draggablePessoaProj   = useDraggableColumns(colPessoaProjetos);

  const breadcrumb = [
    {
      title: (
        <span style={{ cursor: "pointer", color: "#2d50a0" }} onClick={() => { setSelectedPep(null); setSelectedPessoa(null); }}>
          <HomeOutlined /> Projetos
        </span>
      ),
    },
    ...(selectedPep ? [{
      title: (
        <span style={{ cursor: "pointer", color: "#2d50a0" }} onClick={() => setSelectedPessoa(null)}>
          {selectedPep.pep} — {selectedPep.nome_cliente}
        </span>
      ),
    }] : []),
    ...(selectedPessoa ? [{
      title: (
        <span style={{ color: "#1a2e5a", fontWeight: 600 }}>
          {selectedPessoa.nome}
        </span>
      ),
    }] : []),
  ];

  return (
    <div>
      {/* Filtros */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={labelStyle}>Período</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos} onChange={v => { setSelPeriodos(v); setSelectedPep(null); setSelectedPessoa(null); }}
            options={filters.periodos.map(p => ({ label: p, value: p }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Empresa</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas} onChange={v => { setSelEmpresas(v); setSelectedPep(null); setSelectedPessoa(null); }}
            options={filters.empresas.map(e => ({ label: e, value: e }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 0, minWidth: 200 }}>
          <div style={labelStyle}>Tipo</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selTipos} onChange={v => { setSelTipos(v); setSelectedPep(null); setSelectedPessoa(null); }}
            options={filters.tipos.map(t => ({ label: t, value: t }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Cliente</div>
          <Input allowClear placeholder="Buscar cliente..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={searchCliente} onChange={e => { setSearchCliente(e.target.value); setSelectedPep(null); setSelectedPessoa(null); }} />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Projeto (PEP)</div>
          <Input allowClear placeholder="Buscar PEP..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={searchPep} onChange={e => { setSearchPep(e.target.value); setSelectedPep(null); setSelectedPessoa(null); }} />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Pessoa (nome, CPF ou ID)</div>
          <Input allowClear placeholder="Buscar pessoa..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={searchPessoa} onChange={e => { setSearchPessoa(e.target.value); setSelectedPessoa(null); }} />
        </div>
      </div>

      {/* Breadcrumb */}
      <Breadcrumb items={breadcrumb} style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 16 }} />

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : selectedPessoa ? (
        <>
          <Button icon={<ArrowLeftOutlined />} type="link" style={{ color: "#2d50a0", paddingLeft: 0, marginBottom: 12 }}
            onClick={() => setSelectedPessoa(null)}>
            Voltar para pessoas
          </Button>
          {loadingPessoaProj ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
            <Table
              dataSource={[{ key:"__t__", pep:"TOTAL", nome_cliente:"", empresa:"", valor_liquido: totalPessoaProj, _isTotal:true }, ...pessoaProjetos.map((d,i)=>({...d,key:i}))]}
              columns={draggablePessoaProj}
              pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
              size="small"
              scroll={{ x: "max-content" }}
              style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
              onRow={row => row._isTotal ? { style: { background: "#dce6f7", fontWeight: 700 } } : {}}
            />
          )}
        </>
      ) : (selectedPep || searchPessoa.trim()) ? (
        <>
          {selectedPep && (
            <div style={{ marginBottom: 12 }}>
              <Button icon={<ArrowLeftOutlined />} type="link" style={{ color: "#2d50a0", paddingLeft: 0 }} onClick={() => setSelectedPep(null)}>
                Voltar para projetos
              </Button>
            </div>
          )}
          <Table
            dataSource={[{ key:"__t__", numero_pessoal:"TOTAL", cpf:"", nome:"", empresa:"", valor_liquido: totalPessoas, _isTotal:true }, ...filteredPessoas.map((d,i)=>({...d,key:i}))]}
            columns={draggablePessoas}
            pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
            size="small"
            scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
            onRow={row => ({
              onClick: () => !row._isTotal && setSelectedPessoa({ cpf: row.cpf, nome: row.nome, numero_pessoal: row.numero_pessoal }),
              style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: "pointer" },
            })}
          />
        </>
      ) : (
        <Table
          dataSource={[{ key:"__t__", pep:"TOTAL", nome_cliente:"", empresa:"", valor_liquido: totalProjetos, _isTotal:true }, ...filteredProjetos.map((d,i)=>({...d,key:i}))]}
          columns={draggableProjetos}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={row => ({
            onClick: () => !row._isTotal && setSelectedPep({ pep: row.pep, nome_cliente: row.nome_cliente }),
            style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: "pointer" },
          })}
        />
      )}
    </div>
  );
}

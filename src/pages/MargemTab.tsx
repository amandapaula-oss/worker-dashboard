import React, { useEffect, useState, useMemo } from "react";
import { Select, Table, Spin, message, Button, Typography, Breadcrumb, Card, Statistic, Input, Segmented } from "antd";
import { HomeOutlined, ArrowLeftOutlined, SearchOutlined } from "@ant-design/icons";
import { getMargemFilters, getMargemProjetos, getMargemPessoas, getMargemPessoaProjetos } from "../api";
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

  const [projetos, setProjetos]                     = useState<any[]>([]);
  const [projetosMensal, setProjetosMensal]         = useState<any[]>([]);
  const [pessoas, setPessoas]                       = useState<any[]>([]);
  const [pessoasMensal, setPessoasMensal]           = useState<any[]>([]);
  const [pessoaProjetos, setPessoaProjetos]         = useState<any[]>([]);
  const [pessoaProjetosMensal, setPessoaProjetosMensal] = useState<any[]>([]);
  const [loading, setLoading]                       = useState(true);
  const [viewMode, setViewMode]                     = useState<"total" | "mensal">("total");

  const [selectedCliente, setSelectedCliente] = useState<string | null>(null);
  const [selectedPep, setSelectedPep] = useState<{ pep: string; nome_cliente: string } | null>(null);
  const [selectedPessoa, setSelectedPessoa] = useState<{ cpf: string; nome: string; numero_pessoal: string } | null>(null);
  const [loadingPessoaProj, setLoadingPessoaProj] = useState(false);
  const [searchCliente, setSearchCliente] = useState<string>("");
  const [searchPep, setSearchPep]         = useState<string>("");
  const [searchPessoa, setSearchPessoa]   = useState<string>("");

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
    Promise.all([
      getMargemProjetos(params),
      getMargemProjetos({ ...params, breakdown: "true" }),
    ])
      .then(([total, mensal]) => { setProjetos(total); setProjetosMensal(mensal); })
      .catch(() => message.error("Erro ao carregar projetos"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selPeriodos, selEmpresas, selectedPep]);

  // load all pessoas (for global search) or specific PEP (for drill-down)
  useEffect(() => {
    if (!filtersReady) return;
    const params: Record<string, string> = {};
    if (selectedPep) params.pep = selectedPep.pep;
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    Promise.all([
      getMargemPessoas(params),
      getMargemPessoas({ ...params, breakdown: "true" }),
    ])
      .then(([total, mensal]) => { setPessoas(total); setPessoasMensal(mensal); })
      .catch(() => message.error("Erro ao carregar pessoas"));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selectedPep, selPeriodos, selEmpresas]);

  // load projetos for selected pessoa
  useEffect(() => {
    if (!selectedPessoa) return;
    setLoadingPessoaProj(true);
    const params: Record<string, string> = { cpf: selectedPessoa.cpf };
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    Promise.all([
      getMargemPessoaProjetos(params),
      getMargemPessoaProjetos({ ...params, breakdown: "true" }),
    ])
      .then(([total, mensal]) => { setPessoaProjetos(total); setPessoaProjetosMensal(mensal); })
      .catch(() => message.error("Erro ao carregar projetos da pessoa"))
      .finally(() => setLoadingPessoaProj(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPessoa, selPeriodos, selEmpresas]);

  // Pessoas filtradas por nome/CPF
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
      title: "ID", dataIndex: "numero_pessoal", key: "numero_pessoal", width: 120,
      sorter: (a: any, b: any) => String(a.numero_pessoal).localeCompare(String(b.numero_pessoal)),
    },
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

  const colPessoaProjetos = [
    {
      title: "PEP", dataIndex: "pep", key: "pep", width: 190,
      sorter: (a: any, b: any) => String(a.pep).localeCompare(String(b.pep)),
    },
    { title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 120 },
    {
      title: "Receita", dataIndex: "receita", key: "receita", width: 155,
      align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita) || 0) - (Number(b.receita) || 0),
      render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>,
    },
    {
      title: "Custo Rateado", dataIndex: "custo_rateado", key: "custo_rateado", width: 155,
      align: "right" as const,
      render: (v: number) => <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>,
    },
    {
      title: "Margem (R$)", dataIndex: "margem", key: "margem", width: 155,
      align: "right" as const,
      render: (v: number) => <span style={{ color: v < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v)}</span>,
    },
    {
      title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", width: 100,
      align: "center" as const,
      render: (v: number | "") => <MargemTag value={v} />,
    },
  ];

  // Pivot: projetos × períodos (para view mensal)
  const pivotData = useMemo(() => {
    if (!projetosMensal.length) return [];
    const map = new Map<string, any>();
    for (const r of projetosMensal) {
      const key = r.pep;
      if (!map.has(key)) map.set(key, { key, pep: r.pep, nome_cliente: r.nome_cliente, empresa: r.empresa });
      const e = map.get(key)!;
      e[`${r.periodo}_receita`]     = (e[`${r.periodo}_receita`]     || 0) + (Number(r.receita)       || 0);
      e[`${r.periodo}_margem`]      = (e[`${r.periodo}_margem`]      || 0) + (Number(r.margem)        || 0);
    }
    return Array.from(map.values()).map(r => {
      const tot_rec = selPeriodos.reduce((s, p) => s + (r[`${p}_receita`] || 0), 0);
      const tot_mar = selPeriodos.reduce((s, p) => s + (r[`${p}_margem`]  || 0), 0);
      selPeriodos.forEach(p => {
        const rec = r[`${p}_receita`] || 0;
        const mar = r[`${p}_margem`]  || 0;
        r[`${p}_margem_pct`] = rec !== 0 ? mar / rec : null;
      });
      return { ...r, total_receita: tot_rec, total_margem: tot_mar, total_margem_pct: tot_rec !== 0 ? tot_mar / tot_rec : null };
    }).sort((a, b) => b.total_receita - a.total_receita);
  }, [projetosMensal, selPeriodos]);

  // Pivot: pessoas × períodos
  const pivotPessoas = useMemo(() => {
    if (!pessoasMensal.length) return [];
    const map = new Map<string, any>();
    for (const r of pessoasMensal) {
      const key = r.cpf || r.nome;
      if (!map.has(key)) map.set(key, { key, cpf: r.cpf, nome: r.nome, empresa: r.empresa, numero_pessoal: r.numero_pessoal || "" });
      const e = map.get(key)!;
      e[`${r.periodo}_receita`] = (e[`${r.periodo}_receita`] || 0) + (Number(r.receita) || 0);
      e[`${r.periodo}_margem`]  = (e[`${r.periodo}_margem`]  || 0) + (Number(r.margem)  || 0);
    }
    return Array.from(map.values()).map(r => {
      const tot_rec = selPeriodos.reduce((s, p) => s + (r[`${p}_receita`] || 0), 0);
      const tot_mar = selPeriodos.reduce((s, p) => s + (r[`${p}_margem`]  || 0), 0);
      selPeriodos.forEach(p => {
        const rec = r[`${p}_receita`] || 0;
        r[`${p}_margem_pct`] = rec !== 0 ? (r[`${p}_margem`] || 0) / rec : null;
      });
      return { ...r, total_receita: tot_rec, total_margem: tot_mar, total_margem_pct: tot_rec !== 0 ? tot_mar / tot_rec : null };
    }).sort((a, b) => b.total_receita - a.total_receita);
  }, [pessoasMensal, selPeriodos]);

  // Pivot: projetos da pessoa × períodos
  const pivotPessoaProjetos = useMemo(() => {
    if (!pessoaProjetosMensal.length) return [];
    const map = new Map<string, any>();
    for (const r of pessoaProjetosMensal) {
      const key = r.pep;
      if (!map.has(key)) map.set(key, { key, pep: r.pep, nome_cliente: r.nome_cliente || "", empresa: r.empresa });
      const e = map.get(key)!;
      e[`${r.periodo}_receita`] = (e[`${r.periodo}_receita`] || 0) + (Number(r.receita) || 0);
      e[`${r.periodo}_margem`]  = (e[`${r.periodo}_margem`]  || 0) + (Number(r.margem)  || 0);
    }
    return Array.from(map.values()).map(r => {
      const tot_rec = selPeriodos.reduce((s, p) => s + (r[`${p}_receita`] || 0), 0);
      const tot_mar = selPeriodos.reduce((s, p) => s + (r[`${p}_margem`]  || 0), 0);
      selPeriodos.forEach(p => {
        const rec = r[`${p}_receita`] || 0;
        r[`${p}_margem_pct`] = rec !== 0 ? (r[`${p}_margem`] || 0) / rec : null;
      });
      return { ...r, total_receita: tot_rec, total_margem: tot_mar, total_margem_pct: tot_rec !== 0 ? tot_mar / tot_rec : null };
    }).sort((a, b) => b.total_receita - a.total_receita);
  }, [pessoaProjetosMensal, selPeriodos]);

  const colMensal = useMemo(() => {
    const periodoLabel = (p: string) => {
      const [y, m] = p.split("-");
      return `${m}/${y.slice(2)}`;
    };
    const numCol = (dataIndex: string, render?: (v: any) => React.ReactNode) => ({
      dataIndex, key: dataIndex,
      align: "right" as const,
      width: 130,
      sorter: (a: any, b: any) => (Number(a[dataIndex]) || 0) - (Number(b[dataIndex]) || 0),
      render: render,
    });
    const periodoCols = selPeriodos.map(p => ({
      title: periodoLabel(p),
      children: [
        { ...numCol(`${p}_receita`), title: "Receita",  render: (v: number) => v != null ? <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span> : "—" },
        { ...numCol(`${p}_margem`),  title: "Margem",   render: (v: number) => v != null ? <span style={{ color: (v||0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span> : "—" },
        { ...numCol(`${p}_margem_pct`, (v: any) => <MargemTag value={v} />), title: "%", width: 80 },
      ],
    }));
    return [
      { title: "PEP",     dataIndex: "pep",          key: "pep",          width: 190, sorter: (a: any, b: any) => String(a.pep).localeCompare(String(b.pep)) },
      { title: "Cliente", dataIndex: "nome_cliente",  key: "nome_cliente", ellipsis: true },
      { title: "Empresa", dataIndex: "empresa",       key: "empresa",      width: 120 },
      ...periodoCols,
      {
        title: "Total",
        children: [
          { ...numCol("total_receita"), title: "Receita", render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 700 }}>{brl(v || 0)}</span> },
          { ...numCol("total_margem"),  title: "Margem",  render: (v: number) => <span style={{ color: (v||0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span> },
          { ...numCol("total_margem_pct", (v: any) => <MargemTag value={v} />), title: "%", width: 80 },
        ],
      },
    ];
  }, [selPeriodos]);

  const colPessoasMensal = useMemo(() => {
    const periodoLabel = (p: string) => { const [y, m] = p.split("-"); return `${m}/${y.slice(2)}`; };
    const numCol = (dataIndex: string, render?: (v: any) => React.ReactNode) => ({
      dataIndex, key: dataIndex, align: "right" as const, width: 130,
      sorter: (a: any, b: any) => (Number(a[dataIndex]) || 0) - (Number(b[dataIndex]) || 0),
      render,
    });
    const periodoCols = selPeriodos.map(p => ({
      title: periodoLabel(p),
      children: [
        { ...numCol(`${p}_receita`), title: "Receita", render: (v: number) => v != null ? <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v || 0)}</span> : "—" },
        { ...numCol(`${p}_margem`),  title: "Margem",  render: (v: number) => v != null ? <span style={{ color: (v||0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span> : "—" },
        { ...numCol(`${p}_margem_pct`, (v: any) => <MargemTag value={v} />), title: "%", width: 80 },
      ],
    }));
    return [
      { title: "ID",      dataIndex: "numero_pessoal", key: "numero_pessoal", width: 110, sorter: (a: any, b: any) => String(a.numero_pessoal).localeCompare(String(b.numero_pessoal)) },
      { title: "Nome",    dataIndex: "nome",           key: "nome",           ellipsis: true },
      { title: "CPF",     dataIndex: "cpf",            key: "cpf",            width: 140 },
      { title: "Empresa", dataIndex: "empresa",        key: "empresa",        width: 110 },
      ...periodoCols,
      { title: "Total", children: [
        { ...numCol("total_receita"), title: "Receita", render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 700 }}>{brl(v || 0)}</span> },
        { ...numCol("total_margem"),  title: "Margem",  render: (v: number) => <span style={{ color: (v||0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v || 0)}</span> },
        { ...numCol("total_margem_pct", (v: any) => <MargemTag value={v} />), title: "%", width: 80 },
      ]},
    ];
  }, [selPeriodos]);

  // Colunas para busca direta por PEP (inclui Cliente)
  const colProjetosSearch = [
    { title: "PEP",     dataIndex: "pep",          key: "pep",          width: 190,
      sorter: (a: any, b: any) => String(a.pep).localeCompare(String(b.pep)) },
    { title: "Cliente", dataIndex: "nome_cliente",  key: "nome_cliente", ellipsis: true,
      sorter: (a: any, b: any) => String(a.nome_cliente).localeCompare(String(b.nome_cliente)) },
    { title: "Empresa", dataIndex: "empresa",       key: "empresa",      width: 120,
      sorter: (a: any, b: any) => String(a.empresa).localeCompare(String(b.empresa)) },
    { title: "Receita", dataIndex: "receita", key: "receita", width: 155, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.receita)||0) - (Number(b.receita)||0),
      render: (v: number) => <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Custo Rateado", dataIndex: "custo_rateado", key: "custo_rateado", width: 155, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.custo_rateado)||0) - (Number(b.custo_rateado)||0),
      render: (v: number) => <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Margem (R$)", dataIndex: "margem", key: "margem", width: 155, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.margem)||0) - (Number(b.margem)||0),
      render: (v: number) => <span style={{ color: v < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 700 }}>{brl(v)}</span> },
    { title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", width: 100, align: "center" as const,
      sorter: (a: any, b: any) => (Number(a.margem_pct)||0) - (Number(b.margem_pct)||0),
      render: (v: number | "") => <MargemTag value={v} /> },
    { title: "Horas", dataIndex: "horas_total", key: "horas_total", width: 80, align: "right" as const,
      sorter: (a: any, b: any) => (Number(a.horas_total)||0) - (Number(b.horas_total)||0),
      render: (v: number) => v > 0 ? v.toLocaleString("pt-BR") : "—" },
  ];

  const draggableClientes       = useDraggableColumns(colClientes);
  const draggableProjetos       = useDraggableColumns(colProjetos);
  const draggableProjetosSearch = useDraggableColumns(colProjetosSearch);
  const draggablePessoas        = useDraggableColumns(colPessoas);
  const draggablePessoaProj     = useDraggableColumns(colPessoaProjetos);

  const breadcrumb = [
    {
      title: (
        <span style={{ cursor: "pointer", color: "#2d50a0" }}
          onClick={() => { setSelectedCliente(null); setSelectedPep(null); setSelectedPessoa(null); }}>
          <HomeOutlined /> Clientes
        </span>
      ),
    },
    ...(selectedCliente ? [{
      title: selectedPep ? (
        <span style={{ cursor: "pointer", color: "#2d50a0" }}
          onClick={() => { setSelectedPep(null); setSelectedPessoa(null); }}>
          {selectedCliente}
        </span>
      ) : (
        <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{selectedCliente}</span>
      ),
    }] : []),
    ...(selectedPep ? [{
      title: selectedPessoa ? (
        <span style={{ cursor: "pointer", color: "#2d50a0" }}
          onClick={() => setSelectedPessoa(null)}>
          {selectedPep.pep}
        </span>
      ) : (
        <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{selectedPep.pep}</span>
      ),
    }] : []),
    ...(selectedPessoa ? [{
      title: <span style={{ color: "#1a2e5a", fontWeight: 600 }}>{selectedPessoa.nome}</span>,
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
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Pessoa (nome, CPF ou ID)</div>
          <Input
            allowClear
            placeholder="Buscar pessoa..."
            prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
            value={searchPessoa}
            onChange={e => { setSearchPessoa(e.target.value); setSelectedPessoa(null); }}
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, justifyContent: "flex-end" }}>
          <div style={labelStyle}>Visualização</div>
          <Segmented
            value={viewMode}
            onChange={v => setViewMode(v as "total" | "mensal")}
            options={[{ label: "Consolidado", value: "total" }, { label: "Por Mês", value: "mensal" }]}
          />
        </div>
        <Text type="secondary" style={{ fontSize: "0.78rem", paddingBottom: 2 }}>
          * Custo rateado disponível para out–dez/2025. Períodos sem custo exibem receita apenas.
        </Text>
      </div>

      {kpiBlock}

      <Breadcrumb items={breadcrumb} style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 16 }} />

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : selectedPessoa ? (
        <>
          <Button icon={<ArrowLeftOutlined />} type="link" style={{ color: "#2d50a0", paddingLeft: 0, marginBottom: 12 }}
            onClick={() => setSelectedPessoa(null)}>
            Voltar para pessoas
          </Button>
          {loadingPessoaProj ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : viewMode === "mensal" ? (() => {
            const tot_rec = pivotPessoaProjetos.reduce((s,r)=>s+(r.total_receita||0),0);
            const tot_mar = pivotPessoaProjetos.reduce((s,r)=>s+(r.total_margem||0),0);
            const totRow: any = { key:"__t__", pep:"TOTAL", nome_cliente:"", empresa:"", total_receita:tot_rec, total_margem:tot_mar, total_margem_pct:tot_rec!==0?tot_mar/tot_rec:null, _isTotal:true };
            selPeriodos.forEach(p => {
              totRow[`${p}_receita`] = pivotPessoaProjetos.reduce((s,r)=>s+(r[`${p}_receita`]||0),0);
              totRow[`${p}_margem`]  = pivotPessoaProjetos.reduce((s,r)=>s+(r[`${p}_margem`] ||0),0);
              totRow[`${p}_margem_pct`] = totRow[`${p}_receita`]!==0 ? totRow[`${p}_margem`]/totRow[`${p}_receita`] : null;
            });
            return <Table dataSource={[totRow, ...pivotPessoaProjetos]} columns={colMensal} pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }} size="small" scroll={{ x: "max-content" }} style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }} onRow={row => ({ style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : {} })} />;
          })() : (
            <Table
              dataSource={(() => {
                const rec = pessoaProjetos.reduce((s,r)=>s+(Number(r.receita)||0),0);
                const cus = pessoaProjetos.reduce((s,r)=>s+(Number(r.custo_rateado)||0),0);
                const mar = pessoaProjetos.reduce((s,r)=>s+(Number(r.margem)||0),0);
                return [{ key:"__t__", pep:"TOTAL", nome_cliente:"", empresa:"", receita:rec, custo_rateado:cus, margem:mar, margem_pct: rec!==0?mar/rec:null, _isTotal:true }, ...pessoaProjetos.map((d,i)=>({...d,key:i}))];
              })()}
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
            <Button icon={<ArrowLeftOutlined />} type="link" style={{ color: "#2d50a0", paddingLeft: 0, marginBottom: 12 }}
              onClick={() => setSelectedPep(null)}>
              Voltar para projetos
            </Button>
          )}
          {viewMode === "mensal" ? (() => {
            const q = searchPessoa.trim().toLowerCase();
            const qDigits = q.replace(/\D/g, "");
            const filtered = pivotPessoas.filter(r => !q || String(r.nome||"").toLowerCase().includes(q) || (qDigits && String(r.cpf||"").replace(/\D/g,"").includes(qDigits)) || String(r.numero_pessoal||"").toLowerCase().includes(q));
            const tot_rec = filtered.reduce((s,r)=>s+(r.total_receita||0),0);
            const tot_mar = filtered.reduce((s,r)=>s+(r.total_margem||0),0);
            const totRow: any = { key:"__t__", nome:"TOTAL", cpf:"", empresa:"", numero_pessoal:"", total_receita:tot_rec, total_margem:tot_mar, total_margem_pct:tot_rec!==0?tot_mar/tot_rec:null, _isTotal:true };
            selPeriodos.forEach(p => {
              totRow[`${p}_receita`] = filtered.reduce((s,r)=>s+(r[`${p}_receita`]||0),0);
              totRow[`${p}_margem`]  = filtered.reduce((s,r)=>s+(r[`${p}_margem`] ||0),0);
              totRow[`${p}_margem_pct`] = totRow[`${p}_receita`]!==0 ? totRow[`${p}_margem`]/totRow[`${p}_receita`] : null;
            });
            return <Table dataSource={[totRow, ...filtered]} columns={colPessoasMensal} pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }} size="small" scroll={{ x: "max-content" }} style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }} onRow={row => ({ onClick: () => !row._isTotal && setSelectedPessoa({ cpf: row.cpf, nome: row.nome, numero_pessoal: row.numero_pessoal }), style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: "pointer" } })} />;
          })() : (
          <Table
            dataSource={(() => {
              const rec = filteredPessoas.reduce((s,r)=>s+(Number(r.receita)||0),0);
              const cus = filteredPessoas.reduce((s,r)=>s+(Number(r.custo_rateado)||0),0);
              const mar = filteredPessoas.reduce((s,r)=>s+(Number(r.margem)||0),0);
              return [{ key:"__t__", nome:"TOTAL", cpf:"", empresa:"", horas:0, receita:rec, custo_rateado:cus, margem:mar, margem_pct: rec!==0?mar/rec:null, _isTotal:true }, ...filteredPessoas.map((d,i)=>({...d,key:i}))];
            })()}
            columns={draggablePessoas}
            pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
            size="small"
            scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
            onRow={row => ({
              onClick: () => !row._isTotal && setSelectedPessoa({ cpf: row.cpf, nome: row.nome, numero_pessoal: row.numero_pessoal }),
              style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: "pointer" },
            })}
          />)}
        </>
      ) : selectedCliente ? (
        <>
          <Button icon={<ArrowLeftOutlined />} type="link" style={{ color: "#2d50a0", paddingLeft: 0, marginBottom: 12 }}
            onClick={() => setSelectedCliente(null)}>
            Voltar para clientes
          </Button>
          {viewMode === "mensal" ? (() => {
            const filtered = pivotData.filter(r => r.nome_cliente === selectedCliente);
            const tot_rec = filtered.reduce((s,r)=>s+(r.total_receita||0),0);
            const tot_mar = filtered.reduce((s,r)=>s+(r.total_margem||0),0);
            const totRow: any = { key:"__t__", pep:"TOTAL", nome_cliente:"", empresa:"", total_receita:tot_rec, total_margem:tot_mar, total_margem_pct:tot_rec!==0?tot_mar/tot_rec:null, _isTotal:true };
            selPeriodos.forEach(p => {
              totRow[`${p}_receita`] = filtered.reduce((s,r)=>s+(r[`${p}_receita`]||0),0);
              totRow[`${p}_margem`]  = filtered.reduce((s,r)=>s+(r[`${p}_margem`] ||0),0);
              totRow[`${p}_margem_pct`] = totRow[`${p}_receita`]!==0 ? totRow[`${p}_margem`]/totRow[`${p}_receita`] : null;
            });
            return <Table dataSource={[totRow, ...filtered]} columns={colMensal} pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }} size="small" scroll={{ x: "max-content" }} style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }} onRow={row => ({ style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : {} })} />;
          })() : (
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
          />)}
        </>
      ) : searchPep.trim() ? (
        // Busca direta por PEP: mostra projetos filtrados, clicar abre as pessoas do projeto
        viewMode === "mensal" ? (() => {
          const filtered = pivotData.filter(r =>
            String(r.pep || "").toLowerCase().includes(searchPep.trim().toLowerCase())
          );
          const tot_rec = filtered.reduce((s,r)=>s+(r.total_receita||0),0);
          const tot_mar = filtered.reduce((s,r)=>s+(r.total_margem||0),0);
          const totRow: any = { key:"__t__", pep:"TOTAL", nome_cliente:"", empresa:"", total_receita:tot_rec, total_margem:tot_mar, total_margem_pct:tot_rec!==0?tot_mar/tot_rec:null, _isTotal:true };
          selPeriodos.forEach(p => {
            totRow[`${p}_receita`]    = filtered.reduce((s,r)=>s+(r[`${p}_receita`]||0),0);
            totRow[`${p}_margem`]     = filtered.reduce((s,r)=>s+(r[`${p}_margem`] ||0),0);
            totRow[`${p}_margem_pct`] = totRow[`${p}_receita`]!==0 ? totRow[`${p}_margem`]/totRow[`${p}_receita`] : null;
          });
          return (
            <Table
              dataSource={[totRow, ...filtered]}
              columns={colMensal}
              pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
              size="small"
              scroll={{ x: "max-content" }}
              style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
              onRow={row => ({
                onClick: () => !row._isTotal && setSelectedPep({ pep: row.pep, nome_cliente: row.nome_cliente }),
                style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: "pointer" },
              })}
            />
          );
        })() : (() => {
          const rows = filteredProjetos;
          const rec = rows.reduce((s,r)=>s+(Number(r.receita)||0),0);
          const cus = rows.reduce((s,r)=>s+(Number(r.custo_rateado)||0),0);
          const mar = rows.reduce((s,r)=>s+(Number(r.margem)||0),0);
          const pct = rec!==0 ? mar/rec : null;
          const data = [
            { key:"__t__", pep:"TOTAL", nome_cliente:"", empresa:"", receita:rec, custo_rateado:cus, margem:mar, margem_pct:pct, horas_total:0, _isTotal:true },
            ...rows.map((d,i) => ({ ...d, key: i })),
          ];
          return (
            <Table
              dataSource={data}
              columns={draggableProjetosSearch}
              pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
              size="small"
              scroll={{ x: "max-content" }}
              style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
              onRow={row => ({
                onClick: () => !row._isTotal && setSelectedPep({ pep: row.pep, nome_cliente: row.nome_cliente }),
                style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : { cursor: "pointer" },
              })}
            />
          );
        })()
      ) : viewMode === "mensal" ? (
        (() => {
          const filtered = pivotData.filter(r => {
            if (searchCliente.trim() && !String(r.nome_cliente || "").toLowerCase().includes(searchCliente.trim().toLowerCase())) return false;
            if (searchPep.trim() && !String(r.pep || "").toLowerCase().includes(searchPep.trim().toLowerCase())) return false;
            return true;
          });
          const tot_rec = filtered.reduce((s, r) => s + (r.total_receita || 0), 0);
          const tot_mar = filtered.reduce((s, r) => s + (r.total_margem  || 0), 0);
          const totRow: any = { key: "__t__", pep: "TOTAL", nome_cliente: "", empresa: "", total_receita: tot_rec, total_margem: tot_mar, total_margem_pct: tot_rec !== 0 ? tot_mar / tot_rec : null, _isTotal: true };
          selPeriodos.forEach(p => {
            totRow[`${p}_receita`]    = filtered.reduce((s, r) => s + (r[`${p}_receita`] || 0), 0);
            totRow[`${p}_margem`]     = filtered.reduce((s, r) => s + (r[`${p}_margem`]  || 0), 0);
            const rec = totRow[`${p}_receita`];
            const mar = totRow[`${p}_margem`];
            totRow[`${p}_margem_pct`] = rec !== 0 ? mar / rec : null;
          });
          return (
            <Table
              dataSource={[totRow, ...filtered]}
              columns={colMensal}
              pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
              size="small"
              scroll={{ x: "max-content" }}
              style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
              onRow={row => ({ style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : {} })}
            />
          );
        })()
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

import React, { useEffect, useMemo, useState } from "react";
import { Card, Table, Modal, Tag, Select, Input, Row, Col, Statistic, Spin } from "antd";
import { SearchOutlined, UserOutlined } from "@ant-design/icons";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
  PieChart, Pie, Cell,
} from "recharts";
import { getWorkers, getWorkerDetalhe } from "../api";
import { theme } from "../theme";

type Row = {
  nome_pessoa: string;
  cpf?: string;
  contrato?: string;
  razao_social?: string;
  cnpj?: string;
  email?: string;
  receita: number; custo: number; margem: number; horas: number;
  margem_pct: number; vertical: string; tipo_contrato: string; n_clientes: number;
};

type Detalhe = {
  nome: string;
  totais: { horas: number; receita: number; custo: number; margem: number };
  por_periodo: { periodo: string; horas: number; receita: number; custo: number; margem: number }[];
  por_cliente: { nome_cliente: string; horas: number; receita: number; custo: number; margem: number; pct_horas: number }[];
};

const brl = (v: number) =>
  (v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const num = (v: number) =>
  (v || 0).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
const pct = (v: number) => `${((v || 0) * 100).toFixed(1)}%`;

const MESES = ["2026-01","2026-02","2026-03","2026-04","2026-05","2026-06",
               "2026-07","2026-08","2026-09","2026-10","2026-11","2026-12"];
const VERTICAIS = ["BU Finance","BU Health","BU Logistics","BU Multisector","BU Retail","BU Others","Hyper"];

const PIE_COLORS = ["#FF5C35","#1E7C99","#7B61FF","#52c41a","#fa8c16","#13c2c2","#eb2f96","#a0d911","#fadb14","#722ed1"];

export default function WorkersTab() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [selPer, setSelPer] = useState<string[]>(["2026-01","2026-02","2026-03"]);
  const [selVerts, setSelVerts] = useState<string[]>([]);
  const [search, setSearch] = useState("");

  const [selected, setSelected] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<Detalhe | null>(null);
  const [loadingDet, setLoadingDet] = useState(false);

  const load = () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPer.length) params.periodos = selPer.join(",");
    if (selVerts.length) params.verticais = selVerts.join(",");
    getWorkers(params)
      .then(d => setRows(d.rows || []))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [selPer.join(","), selVerts.join(",")]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r => r.nome_pessoa.toLowerCase().includes(q));
  }, [rows, search]);

  const tot = useMemo(() => filtered.reduce((a, r) => ({
    receita: a.receita + r.receita, custo: a.custo + r.custo,
    margem: a.margem + r.margem, horas: a.horas + r.horas,
  }), { receita: 0, custo: 0, margem: 0, horas: 0 }), [filtered]);

  const openDet = (nome: string) => {
    setSelected(nome);
    setDetalhe(null);
    setLoadingDet(true);
    const params: Record<string, string> = { nome };
    if (selPer.length) params.periodos = selPer.join(",");
    getWorkerDetalhe(params)
      .then(d => setDetalhe(d))
      .finally(() => setLoadingDet(false));
  };

  const formatCpf = (s?: string) => {
    if (!s) return "—";
    const d = String(s).replace(/\D/g, "");
    if (d.length !== 11) return s;
    return `${d.slice(0,3)}.${d.slice(3,6)}.${d.slice(6,9)}-${d.slice(9)}`;
  };
  const contratoColor: Record<string, string> = { CLT: "blue", PJ: "purple", INTERN: "cyan", "Estagiário": "geekblue", OTHER: "default" };

  const columns = [
    { title: "Pessoa", dataIndex: "nome_pessoa", key: "nome_pessoa", fixed: "left" as const, width: 240,
      render: (v: string) => (
        <a onClick={() => openDet(v)} style={{ cursor: "pointer" }}>
          <UserOutlined style={{ marginRight: 6 }} />{v}
        </a>
      ),
      sorter: (a: Row, b: Row) => a.nome_pessoa.localeCompare(b.nome_pessoa, "pt-BR") },
    { title: "CPF", dataIndex: "cpf", key: "cpf", width: 140,
      render: (v: string) => <span style={{ fontFamily: "monospace", fontSize: 12 }}>{formatCpf(v)}</span> },
    { title: "Contrato", dataIndex: "contrato", key: "contrato", width: 95,
      render: (v: string) => v ? <Tag color={contratoColor[v] || "default"}>{v}</Tag> : "—",
      sorter: (a: Row, b: Row) => (a.contrato || "").localeCompare(b.contrato || "") },
    { title: "Razão Social", dataIndex: "razao_social", key: "razao_social", width: 220, ellipsis: true,
      render: (v: string) => v || "—" },
    { title: "BU", dataIndex: "vertical", key: "vertical", width: 130,
      render: (v: string) => v ? <Tag>{v}</Tag> : "—",
      sorter: (a: Row, b: Row) => (a.vertical || "").localeCompare(b.vertical || "") },
    { title: "Horas", dataIndex: "horas", key: "horas", align: "right" as const, width: 90,
      render: num, sorter: (a: Row, b: Row) => a.horas - b.horas },
    { title: "Receita", dataIndex: "receita", key: "receita", align: "right" as const, width: 130,
      render: brl, sorter: (a: Row, b: Row) => a.receita - b.receita, defaultSortOrder: "descend" as const },
    { title: "Custo", dataIndex: "custo", key: "custo", align: "right" as const, width: 130,
      render: brl, sorter: (a: Row, b: Row) => a.custo - b.custo },
    { title: "Margem", dataIndex: "margem", key: "margem", align: "right" as const, width: 130,
      render: (v: number) => <span style={{ color: v >= 0 ? "#52c41a" : "#ff4d4f" }}>{brl(v)}</span>,
      sorter: (a: Row, b: Row) => a.margem - b.margem },
    { title: "Margem %", dataIndex: "margem_pct", key: "margem_pct", align: "right" as const, width: 95,
      render: (v: number) => v ? pct(v) : "—",
      sorter: (a: Row, b: Row) => a.margem_pct - b.margem_pct },
    { title: "# Clientes", dataIndex: "n_clientes", key: "n_clientes", align: "right" as const, width: 100,
      sorter: (a: Row, b: Row) => a.n_clientes - b.n_clientes },
  ];

  const detCliCols = [
    { title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true },
    { title: "Horas", dataIndex: "horas", align: "right" as const, render: num, width: 100,
      sorter: (a: any, b: any) => a.horas - b.horas, defaultSortOrder: "descend" as const },
    { title: "% Horas", dataIndex: "pct_horas", align: "right" as const, render: pct, width: 90 },
    { title: "Receita", dataIndex: "receita", align: "right" as const, render: brl, width: 130 },
    { title: "Custo", dataIndex: "custo", align: "right" as const, render: brl, width: 130 },
    { title: "Margem", dataIndex: "margem", align: "right" as const, width: 130,
      render: (v: number) => <span style={{ color: v >= 0 ? "#52c41a" : "#ff4d4f" }}>{brl(v)}</span> },
  ];

  // pie data (top 8 clientes + "outros")
  const pieData = useMemo(() => {
    if (!detalhe) return [];
    const arr = [...detalhe.por_cliente].sort((a, b) => b.horas - a.horas);
    const top = arr.slice(0, 8);
    const rest = arr.slice(8);
    if (rest.length === 0) return top.map(x => ({ name: x.nome_cliente, value: x.horas }));
    const outros = rest.reduce((s, x) => s + x.horas, 0);
    return [...top.map(x => ({ name: x.nome_cliente, value: x.horas })),
            { name: `Outros (${rest.length})`, value: outros }];
  }, [detalhe]);

  return (
    <div>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Row gutter={[12, 12]} align="middle">
          <Col flex="auto">
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>Períodos</div>
            <Select mode="multiple" allowClear style={{ width: "100%" }}
              value={selPer} onChange={setSelPer} placeholder="Todos até hoje"
              options={MESES.map(m => ({ label: m, value: m }))} />
          </Col>
          <Col flex="auto">
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>BUs</div>
            <Select mode="multiple" allowClear style={{ width: "100%" }}
              value={selVerts} onChange={setSelVerts} placeholder="Todas"
              options={VERTICAIS.map(v => ({ label: v, value: v }))} />
          </Col>
          <Col flex="auto">
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>Buscar pessoa</div>
            <Input prefix={<SearchOutlined />} value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Nome..." allowClear />
          </Col>
        </Row>
      </Card>

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={6}><Card size="small"><Statistic title="Pessoas" value={filtered.length} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="Total Receita" value={tot.receita}
          formatter={v => brl(Number(v))} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="Total Custo" value={tot.custo}
          formatter={v => brl(Number(v))} valueStyle={{ color: "#ff4d4f" }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="Total Margem" value={tot.margem}
          formatter={v => brl(Number(v))} valueStyle={{ color: tot.margem >= 0 ? "#52c41a" : "#ff4d4f" }} /></Card></Col>
      </Row>

      <Card size="small">
        <Table
          loading={loading}
          dataSource={filtered}
          columns={columns}
          rowKey="nome_pessoa"
          size="small"
          pagination={{ pageSize: 50, showSizeChanger: true, showTotal: t => `${t} pessoas` }}
          scroll={{ x: 1600 }}
        />
      </Card>

      <Modal
        open={!!selected}
        title={selected}
        onCancel={() => { setSelected(null); setDetalhe(null); }}
        footer={null}
        width={1000}
      >
        {loadingDet || !detalhe ? (
          <div style={{ padding: 40, textAlign: "center" }}><Spin /></div>
        ) : (
          <>
            <Row gutter={12} style={{ marginBottom: 16 }}>
              <Col span={6}><Card size="small"><Statistic title="Horas" value={num(detalhe.totais.horas)} /></Card></Col>
              <Col span={6}><Card size="small"><Statistic title="Receita" value={brl(detalhe.totais.receita)} /></Card></Col>
              <Col span={6}><Card size="small"><Statistic title="Custo" value={brl(detalhe.totais.custo)}
                valueStyle={{ color: "#ff4d4f" }} /></Card></Col>
              <Col span={6}><Card size="small"><Statistic title="Margem" value={brl(detalhe.totais.margem)}
                valueStyle={{ color: detalhe.totais.margem >= 0 ? "#52c41a" : "#ff4d4f" }} /></Card></Col>
            </Row>

            <Card size="small" title="Por período" style={{ marginBottom: 12 }}>
              <div style={{ width: "100%", height: 220 }}>
                <ResponsiveContainer>
                  <BarChart data={detalhe.por_periodo}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                    <XAxis dataKey="periodo" />
                    <YAxis yAxisId="left" tickFormatter={v => `${v}h`} />
                    <YAxis yAxisId="right" orientation="right" tickFormatter={v => `${(v/1000).toFixed(0)}K`} />
                    <Tooltip formatter={(v: any, name: any) => String(name) === "Horas" ? `${num(Number(v))}h` : brl(Number(v))} />
                    <Legend />
                    <Bar yAxisId="left" dataKey="horas" name="Horas" fill="#a0b3d6" />
                    <Bar yAxisId="right" dataKey="receita" name="Receita" fill={theme.accent} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card size="small" title={`Horas por cliente (${detalhe.por_cliente.length})`}>
              <Row gutter={12}>
                <Col span={10}>
                  <div style={{ width: "100%", height: 280 }}>
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={100} label={(e: any) => `${(e.percent * 100).toFixed(0)}%`}>
                          {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                        </Pie>
                        <Tooltip formatter={(v: any) => `${num(Number(v))}h`} />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </Col>
                <Col span={14}>
                  <Table
                    size="small"
                    dataSource={detalhe.por_cliente}
                    columns={detCliCols}
                    rowKey="nome_cliente"
                    pagination={{ pageSize: 10, size: "small" }}
                    scroll={{ x: 720 }}
                  />
                </Col>
              </Row>
            </Card>
          </>
        )}
      </Modal>
    </div>
  );
}

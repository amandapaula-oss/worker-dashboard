import React, { useEffect, useMemo, useState } from "react";
import { Card, Select, Table, Segmented, Statistic, Row, Col, Spin } from "antd";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer,
} from "recharts";
import { getBudgetVsRealizado } from "../api";
import { theme } from "../theme";

type Row = {
  periodo: string;
  vertical: string;
  nome_cliente: string;
  bud_receita: number; bud_custo: number; bud_lb: number;
  real_receita: number; real_custo: number; real_lb: number;
};

const brl = (v: number) =>
  (v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const MESES = Array.from({ length: 12 }, (_, i) => `2026-${String(i + 1).padStart(2, "0")}`);
const MES_LABEL: Record<string, string> = {
  "2026-01": "Jan", "2026-02": "Fev", "2026-03": "Mar", "2026-04": "Abr",
  "2026-05": "Mai", "2026-06": "Jun", "2026-07": "Jul", "2026-08": "Ago",
  "2026-09": "Set", "2026-10": "Out", "2026-11": "Nov", "2026-12": "Dez",
};

type Metric = "receita" | "custo" | "lb";
const METRIC_LABEL: Record<Metric, string> = { receita: "Receita", custo: "Custo", lb: "Lucro Bruto" };

type GroupBy = "vertical" | "nome_cliente";

export default function BudgetVsRealizadoTab({
  fixedGroupBy,
}: { fixedGroupBy?: GroupBy } = {}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [groupBy, setGroupBy] = useState<GroupBy>(fixedGroupBy ?? "vertical");
  const [metric, setMetric] = useState<Metric>("receita");
  const [selVerts, setSelVerts] = useState<string[]>([]);
  const [selCli, setSelCli] = useState<string[]>([]);

  useEffect(() => {
    setLoading(true);
    getBudgetVsRealizado()
      .then((d) => setRows(d.rows || []))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return rows.filter(r =>
      (selVerts.length === 0 || selVerts.includes(r.vertical)) &&
      (selCli.length === 0 || selCli.includes(r.nome_cliente))
    );
  }, [rows, selVerts, selCli]);

  const verticais = useMemo(() => Array.from(new Set(rows.map(r => r.vertical))).filter(Boolean).sort(), [rows]);
  const clientes = useMemo(() => Array.from(new Set(rows.map(r => r.nome_cliente))).filter(Boolean).sort(), [rows]);

  // KPIs totais
  const kpi = useMemo(() => {
    const acc = { br: 0, bc: 0, bl: 0, rr: 0, rc: 0, rl: 0 };
    filtered.forEach(r => {
      acc.br += r.bud_receita; acc.bc += r.bud_custo; acc.bl += r.bud_lb;
      acc.rr += r.real_receita; acc.rc += r.real_custo; acc.rl += r.real_lb;
    });
    return acc;
  }, [filtered]);

  // Série temporal: por mês, soma budget e realizado da métrica
  const chartData = useMemo(() => {
    const idx: Record<string, { mes: string; Budget: number; Realizado: number }> = {};
    MESES.forEach(m => { idx[m] = { mes: MES_LABEL[m], Budget: 0, Realizado: 0 }; });
    filtered.forEach(r => {
      if (!idx[r.periodo]) return;
      const bud = metric === "receita" ? r.bud_receita : metric === "custo" ? r.bud_custo : r.bud_lb;
      const real = metric === "receita" ? r.real_receita : metric === "custo" ? r.real_custo : r.real_lb;
      idx[r.periodo].Budget += bud;
      idx[r.periodo].Realizado += real;
    });
    return MESES.map(m => idx[m]);
  }, [filtered, metric]);

  // Tabela: agregada por groupBy
  const tableData = useMemo(() => {
    const idx: Record<string, any> = {};
    filtered.forEach(r => {
      const k = (r as any)[groupBy] || "—";
      if (!idx[k]) idx[k] = { key: k, label: k, bud_receita: 0, bud_custo: 0, bud_lb: 0, real_receita: 0, real_custo: 0, real_lb: 0 };
      idx[k].bud_receita += r.bud_receita; idx[k].bud_custo += r.bud_custo; idx[k].bud_lb += r.bud_lb;
      idx[k].real_receita += r.real_receita; idx[k].real_custo += r.real_custo; idx[k].real_lb += r.real_lb;
    });
    const arr = Object.values(idx) as any[];
    arr.forEach(r => {
      r.delta_receita = r.real_receita - r.bud_receita;
      r.delta_custo = r.real_custo - r.bud_custo;
      r.delta_lb = r.real_lb - r.bud_lb;
      r.atingimento_receita = r.bud_receita ? r.real_receita / r.bud_receita : 0;
      r.atingimento_lb = r.bud_lb ? r.real_lb / r.bud_lb : 0;
    });
    arr.sort((a, b) => b.bud_receita - a.bud_receita);
    return arr;
  }, [filtered, groupBy]);

  const tot = useMemo(() => tableData.reduce((a, r) => ({
    bud_receita: a.bud_receita + r.bud_receita, bud_custo: a.bud_custo + r.bud_custo, bud_lb: a.bud_lb + r.bud_lb,
    real_receita: a.real_receita + r.real_receita, real_custo: a.real_custo + r.real_custo, real_lb: a.real_lb + r.real_lb,
  }), { bud_receita: 0, bud_custo: 0, bud_lb: 0, real_receita: 0, real_custo: 0, real_lb: 0 }), [tableData]);

  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

  const columns = [
    { title: groupBy === "vertical" ? "BU" : "Cliente", dataIndex: "label", key: "label", fixed: "left" as const, width: 240 },
    { title: "Receita Budget", dataIndex: "bud_receita", render: brl, align: "right" as const, sorter: (a: any, b: any) => a.bud_receita - b.bud_receita },
    { title: "Receita Real",   dataIndex: "real_receita", render: brl, align: "right" as const, sorter: (a: any, b: any) => a.real_receita - b.real_receita },
    { title: "Δ Receita", dataIndex: "delta_receita", align: "right" as const,
      render: (v: number) => <span style={{ color: v >= 0 ? "#52c41a" : "#ff4d4f" }}>{brl(v)}</span>,
      sorter: (a: any, b: any) => a.delta_receita - b.delta_receita },
    { title: "% Atingim.", dataIndex: "atingimento_receita", align: "right" as const,
      render: (v: number) => v ? pct(v) : "—",
      sorter: (a: any, b: any) => a.atingimento_receita - b.atingimento_receita },
    { title: "LB Budget", dataIndex: "bud_lb", render: brl, align: "right" as const, sorter: (a: any, b: any) => a.bud_lb - b.bud_lb },
    { title: "LB Real",   dataIndex: "real_lb", render: brl, align: "right" as const, sorter: (a: any, b: any) => a.real_lb - b.real_lb },
    { title: "Δ LB", dataIndex: "delta_lb", align: "right" as const,
      render: (v: number) => <span style={{ color: v >= 0 ? "#52c41a" : "#ff4d4f" }}>{brl(v)}</span>,
      sorter: (a: any, b: any) => a.delta_lb - b.delta_lb },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Row gutter={[12, 12]} align="middle">
          {!fixedGroupBy && (
            <Col>
              <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>Visão</div>
              <Segmented
                value={groupBy}
                onChange={(v) => setGroupBy(v as any)}
                options={[
                  { label: "Por BU", value: "vertical" },
                  { label: "Por Cliente", value: "nome_cliente" },
                ]}
              />
            </Col>
          )}
          <Col>
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>Métrica do gráfico</div>
            <Segmented
              value={metric}
              onChange={(v) => setMetric(v as Metric)}
              options={[
                { label: "Receita", value: "receita" },
                { label: "Custo", value: "custo" },
                { label: "LB", value: "lb" },
              ]}
            />
          </Col>
          <Col flex="auto">
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>Filtrar BUs</div>
            <Select mode="multiple" allowClear style={{ width: "100%", maxWidth: 380 }}
              value={selVerts} onChange={setSelVerts} placeholder="Todas as BUs"
              options={verticais.map(v => ({ label: v, value: v }))} />
          </Col>
          <Col flex="auto">
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>Filtrar Clientes</div>
            <Select mode="multiple" allowClear style={{ width: "100%", maxWidth: 380 }}
              value={selCli} onChange={setSelCli} placeholder="Todos os clientes" showSearch optionFilterProp="label"
              options={clientes.map(c => ({ label: c, value: c }))} />
          </Col>
        </Row>
      </Card>

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={8}><Card size="small">
          <div style={{ fontSize: 12, opacity: 0.7 }}>Receita</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div><div style={{ fontSize: 11, opacity: 0.6 }}>Budget</div><div style={{ fontWeight: 600 }}>{brl(kpi.br)}</div></div>
            <div><div style={{ fontSize: 11, opacity: 0.6 }}>Realizado</div><div style={{ fontWeight: 600 }}>{brl(kpi.rr)}</div></div>
            <div style={{ color: kpi.rr - kpi.br >= 0 ? "#52c41a" : "#ff4d4f" }}>
              <div style={{ fontSize: 11, opacity: 0.6 }}>Δ</div>
              <div style={{ fontWeight: 600 }}>{brl(kpi.rr - kpi.br)}</div>
            </div>
          </div>
        </Card></Col>
        <Col span={8}><Card size="small">
          <div style={{ fontSize: 12, opacity: 0.7 }}>Custo</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div><div style={{ fontSize: 11, opacity: 0.6 }}>Budget</div><div style={{ fontWeight: 600 }}>{brl(kpi.bc)}</div></div>
            <div><div style={{ fontSize: 11, opacity: 0.6 }}>Realizado</div><div style={{ fontWeight: 600 }}>{brl(kpi.rc)}</div></div>
            <div style={{ color: kpi.rc - kpi.bc >= 0 ? "#52c41a" : "#ff4d4f" }}>
              <div style={{ fontSize: 11, opacity: 0.6 }}>Δ</div>
              <div style={{ fontWeight: 600 }}>{brl(kpi.rc - kpi.bc)}</div>
            </div>
          </div>
        </Card></Col>
        <Col span={8}><Card size="small">
          <div style={{ fontSize: 12, opacity: 0.7 }}>Lucro Bruto</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div><div style={{ fontSize: 11, opacity: 0.6 }}>Budget</div><div style={{ fontWeight: 600 }}>{brl(kpi.bl)}</div></div>
            <div><div style={{ fontSize: 11, opacity: 0.6 }}>Realizado</div><div style={{ fontWeight: 600 }}>{brl(kpi.rl)}</div></div>
            <div style={{ color: kpi.rl - kpi.bl >= 0 ? "#52c41a" : "#ff4d4f" }}>
              <div style={{ fontSize: 11, opacity: 0.6 }}>Δ</div>
              <div style={{ fontWeight: 600 }}>{brl(kpi.rl - kpi.bl)}</div>
            </div>
          </div>
        </Card></Col>
      </Row>

      <Card size="small" title={`${METRIC_LABEL[metric]} mensal — Budget vs Realizado`} style={{ marginBottom: 12 }}>
        {loading ? <div style={{ padding: 40, textAlign: "center" }}><Spin /></div> : (
          <div style={{ width: "100%", height: 340 }}>
            <ResponsiveContainer>
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="mes" />
                <YAxis tickFormatter={(v) => `${(v / 1_000_000).toFixed(1)}M`} />
                <Tooltip formatter={(v: any) => brl(Number(v) || 0)} />
                <Legend />
                <Bar dataKey="Budget" fill="#a0b3d6" />
                <Line type="monotone" dataKey="Realizado" stroke={theme.accent} strokeWidth={2} dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <Card size="small" title={groupBy === "vertical" ? "Detalhe por BU" : "Detalhe por Cliente"}>
        <Table
          size="small"
          loading={loading}
          dataSource={tableData}
          columns={columns}
          rowKey="key"
          pagination={{ pageSize: 25, showSizeChanger: true }}
          scroll={{ x: 1200 }}
          summary={() => (
            <Table.Summary fixed>
              <Table.Summary.Row style={{ background: "#fafafa", fontWeight: 600 }}>
                <Table.Summary.Cell index={0}>TOTAL</Table.Summary.Cell>
                <Table.Summary.Cell index={1} align="right">{brl(tot.bud_receita)}</Table.Summary.Cell>
                <Table.Summary.Cell index={2} align="right">{brl(tot.real_receita)}</Table.Summary.Cell>
                <Table.Summary.Cell index={3} align="right">
                  <span style={{ color: tot.real_receita - tot.bud_receita >= 0 ? "#52c41a" : "#ff4d4f" }}>
                    {brl(tot.real_receita - tot.bud_receita)}
                  </span>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={4} align="right">
                  {tot.bud_receita ? pct(tot.real_receita / tot.bud_receita) : "—"}
                </Table.Summary.Cell>
                <Table.Summary.Cell index={5} align="right">{brl(tot.bud_lb)}</Table.Summary.Cell>
                <Table.Summary.Cell index={6} align="right">{brl(tot.real_lb)}</Table.Summary.Cell>
                <Table.Summary.Cell index={7} align="right">
                  <span style={{ color: tot.real_lb - tot.bud_lb >= 0 ? "#52c41a" : "#ff4d4f" }}>
                    {brl(tot.real_lb - tot.bud_lb)}
                  </span>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            </Table.Summary>
          )}
        />
      </Card>
    </div>
  );
}

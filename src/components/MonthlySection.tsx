import React, { useState } from "react";
import { Select, Table } from "antd";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Mensal } from "../types";
import { theme } from "../theme";

interface Props {
  data: Mensal[];
}

const METRICS = [
  { label: "Receita Bruta",   value: "receita_bruta" },
  { label: "Receita Líquida", value: "receita_liquida" },
  { label: "Custo",           value: "custo" },
  { label: "Lucro Bruto",     value: "lucro_bruto" },
  { label: "Margem Bruta %",  value: "margem_bruta" },
];

function fmtBRL(v: number) {
  return `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}
function fmtPct(v: number) { return `${(v * 100).toFixed(1)}%`; }
function fmtVal(v: number, key: string) { return key === "margem_bruta" ? fmtPct(v) : fmtBRL(v); }

export default function MonthlySection({ data }: Props) {
  const [metric, setMetric] = useState("receita_bruta");
  const chartData = data.filter(d => d.competencia !== "Total");

  const columns = [
    { title: "Competência", dataIndex: "competencia", key: "competencia",
      render: (v: string) => v === "Total" ? <strong>{v}</strong> : v },
    { title: "Receita Bruta", dataIndex: "receita_bruta", key: "receita_bruta",
      render: (v: number) => fmtBRL(v), align: "right" as const },
    { title: "Receita Líquida", dataIndex: "receita_liquida", key: "receita_liquida",
      render: (v: number) => fmtBRL(v), align: "right" as const },
    { title: "Custo", dataIndex: "custo", key: "custo",
      render: (v: number) => fmtBRL(v), align: "right" as const },
    { title: "Lucro Bruto", dataIndex: "lucro_bruto", key: "lucro_bruto",
      render: (v: number) => <span style={{ color: v < 0 ? "#c0392b" : theme.text }}>{fmtBRL(v)}</span>,
      align: "right" as const },
    { title: "Margem Bruta %", dataIndex: "margem_bruta", key: "margem_bruta",
      render: (v: number) => <span style={{ color: v < 0 ? "#c0392b" : "#1a7a4a", fontWeight: 600 }}>{fmtPct(v)}</span>,
      align: "right" as const },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Select
          value={metric}
          onChange={setMetric}
          options={METRICS}
          style={{ width: 200 }}
          size="middle"
        />
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 4, right: 16, left: 16, bottom: 4 }}>
          <XAxis dataKey="competencia" tick={{ fontSize: 12, fill: "#6b7fa3" }} />
          <YAxis
            tick={{ fontSize: 12, fill: "#6b7fa3" }}
            tickFormatter={(v: number) => metric === "margem_bruta" ? `${(v * 100).toFixed(0)}%` : `${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            formatter={(v: number | string | undefined) => fmtVal(Number(v ?? 0), metric)}
            labelStyle={{ color: theme.text }}
            contentStyle={{ borderRadius: 8, border: "1px solid #dde3f0" }}
          />
          <Bar dataKey={metric} radius={[4, 4, 0, 0]}>
            {chartData.map((_, i) => <Cell key={i} fill={theme.accent} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <Table
        dataSource={data.map((d, i) => ({ ...d, key: i }))}
        columns={columns}
        pagination={false}
        size="middle"
        rowClassName={(record) => record.competencia === "Total" ? "total-row" : ""}
        style={{ marginTop: 16, borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
      />
    </div>
  );
}

import React from "react";
import { Table, Tag } from "antd";
import { Metrica } from "../types";
import { theme } from "../theme";

interface Props {
  data: Metrica[];
  onSelect?: (row: Metrica) => void;
  levelKey: string;
}

function fmtBRL(v: number) {
  return `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}
function fmtPct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

export default function MetricTable({ data, onSelect, levelKey }: Props) {
  const columns = [
    {
      title: "Nome",
      dataIndex: "nome",
      key: "nome",
      render: (text: string, row: Metrica) => {
        const isTotal = text === "Total";
        if (isTotal) return <strong>{text}</strong>;
        if (onSelect) return (
          <span
            style={{ color: theme.link, cursor: "pointer", textDecoration: "underline" }}
            onClick={() => onSelect(row)}
          >
            {text} <span style={{ fontSize: "0.75rem" }}>›</span>
          </span>
        );
        return text;
      },
    },
    {
      title: "Receita Bruta",
      dataIndex: "receita_bruta",
      key: "receita_bruta",
      render: (v: number) => fmtBRL(v),
      align: "right" as const,
    },
    {
      title: "Receita Líquida",
      dataIndex: "receita_liquida",
      key: "receita_liquida",
      render: (v: number) => fmtBRL(v),
      align: "right" as const,
    },
    {
      title: "Custo",
      dataIndex: "custo",
      key: "custo",
      render: (v: number) => fmtBRL(v),
      align: "right" as const,
    },
    {
      title: "Lucro Bruto",
      dataIndex: "lucro_bruto",
      key: "lucro_bruto",
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : theme.text }}>{fmtBRL(v)}</span>
      ),
      align: "right" as const,
    },
    {
      title: "Margem Bruta %",
      dataIndex: "margem_bruta",
      key: "margem_bruta",
      render: (v: number) => (
        <Tag color={v < 0 ? "red" : v >= 0.2 ? "green" : "blue"} style={{ fontWeight: 600 }}>
          {fmtPct(v)}
        </Tag>
      ),
      align: "right" as const,
    },
  ];

  return (
    <Table
      dataSource={data.map((d, i) => ({ ...d, key: i }))}
      columns={columns}
      pagination={false}
      size="middle"
      rowClassName={(record) => record.nome === "Total" ? "total-row" : ""}
      style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
    />
  );
}

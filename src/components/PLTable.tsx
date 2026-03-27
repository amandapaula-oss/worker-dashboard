import React from "react";
import { Table } from "antd";
import { theme } from "../theme";

interface PLRow {
  name: string;
  is_subtotal: boolean;
  is_pct: boolean;
  values: Record<string, number>;
}

interface Props {
  rows: PLRow[];
  columns: string[];
}

function fmtBRL(v: number) {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtPct(v: number) { return `${(v * 100).toFixed(1)}%`; }

export default function PLTable({ rows, columns }: Props) {
  if (!rows.length) return <p style={{ color: "#6b7fa3" }}>Nenhum dado encontrado.</p>;

  const tableColumns = [
    {
      title: "Linha",
      dataIndex: "name",
      key: "name",
      fixed: "left" as const,
      width: 220,
      render: (text: string, record: PLRow) => (
        <span style={{ fontWeight: record.is_subtotal ? 700 : 400, color: theme.text }}>{text}</span>
      ),
    },
    ...columns.map(col => ({
      title: col,
      dataIndex: col,
      key: col,
      align: "right" as const,
      width: 120,
      render: (_: any, record: PLRow) => {
        const v = record.values[col] ?? 0;
        const formatted = record.is_pct ? fmtPct(v) : fmtBRL(v);
        const color = v < 0 && !record.is_pct ? "#c0392b" : theme.text;
        return <span style={{ fontWeight: record.is_subtotal ? 700 : 400, color }}>{formatted}</span>;
      },
    })),
  ];

  const dataSource = rows.map((r, i) => ({ ...r, key: i }));

  return (
    <Table
      dataSource={dataSource}
      columns={tableColumns}
      pagination={false}
      size="small"
      scroll={{ x: "max-content" }}
      rowClassName={(record) => record.is_subtotal ? "subtotal-row" : ""}
      style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
    />
  );
}

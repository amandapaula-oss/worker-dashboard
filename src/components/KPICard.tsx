import React from "react";
import { Card, Statistic } from "antd";
import { theme } from "../theme";

interface Props {
  label: string;
  value: number;
  format?: "brl" | "pct";
}

function fmt(value: number, format: "brl" | "pct") {
  if (format === "pct") return `${(value * 100).toFixed(1)}%`;
  return `R$ ${value.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function KPICard({ label, value, format = "brl" }: Props) {
  const isNegative = value < 0;
  const color = isNegative ? "#c0392b" : format === "pct" ? "#1a7a4a" : theme.text;

  return (
    <Card style={{ flex: 1, borderRadius: 10, border: "1px solid #dde3f0", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}
      styles={{ body: { padding: "1rem 1.2rem", textAlign: "center" } }}>
      <Statistic
        title={<span style={{ color: "#6b7fa3", fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</span>}
        value={fmt(value, format)}
        valueStyle={{ color, fontSize: "1.25rem", fontWeight: 700 }}
      />
    </Card>
  );
}

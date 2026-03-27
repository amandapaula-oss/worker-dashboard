import React from "react";
import { theme } from "../theme";

interface Props {
  label: string;
  value: number;
  format?: "brl" | "pct";
  accent?: string;
}

function fmt(value: number, format: "brl" | "pct") {
  if (format === "pct") return `${(value * 100).toFixed(1)}%`;
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}

export default function KPICard({ label, value, format = "brl", accent }: Props) {
  const isNegative = value < 0;
  const valueColor = isNegative ? "#c0392b" : format === "pct" ? "#1a7a4a" : theme.text;
  const barColor = accent ?? (isNegative ? "#c0392b" : format === "pct" ? "#1a7a4a" : theme.accent);

  return (
    <div style={{
      flex: 1, minWidth: 140,
      background: "#fff",
      borderRadius: 10,
      border: "1px solid #dde3f0",
      boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
      overflow: "hidden",
    }}>
      <div style={{ height: 3, background: barColor }} />
      <div style={{ padding: "0.85rem 1.1rem", textAlign: "center" }}>
        <div style={{ color: "#6b7fa3", fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 6 }}>
          {label}
        </div>
        <div style={{ color: valueColor, fontSize: "1.2rem", fontWeight: 700, lineHeight: 1.2 }}>
          {fmt(value, format)}
        </div>
      </div>
    </div>
  );
}

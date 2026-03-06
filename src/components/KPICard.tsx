import React from "react";

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
  return (
    <div style={styles.card}>
      <div style={styles.label}>{label}</div>
      <div style={{ ...styles.value, color: isNegative ? "#c0392b" : format === "pct" ? "#1a7a4a" : "#1a2e5a" }}>
        {fmt(value, format)}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "#fff", border: "1px solid #dde3f0", borderRadius: 10,
    padding: "1rem 1.2rem", textAlign: "center",
    boxShadow: "0 1px 4px rgba(0,0,0,0.04)", flex: 1,
  },
  label: { color: "#6b7fa3", fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 },
  value: { fontSize: "1.3rem", fontWeight: 700 },
};

import React from "react";
import { Metrica } from "../types";

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
  return (
    <div style={styles.wrapper}>
      <table style={styles.table}>
        <thead>
          <tr>
            {["Nome", "Receita Bruta", "Receita Líquida", "Custo", "Lucro Bruto", "Margem Bruta %"].map(h => (
              <th key={h} style={styles.th}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const isTotal = row.nome === "Total";
            const isNegLB = row.lucro_bruto < 0;
            const isNegMG = row.margem_bruta < 0;
            return (
              <tr
                key={i}
                style={{
                  ...styles.tr,
                  background: isTotal ? "#dce6f7" : i % 2 === 0 ? "#fff" : "#f9fafc",
                  cursor: onSelect && !isTotal ? "pointer" : "default",
                  fontWeight: isTotal ? 700 : 400,
                }}
                onClick={() => !isTotal && onSelect && onSelect(row)}
              >
                <td style={{ ...styles.td, color: isTotal ? "#1a2e5a" : onSelect ? "#2d50a0" : "#1a2e5a",
                             textDecoration: onSelect && !isTotal ? "underline" : "none" }}>
                  {row.nome}
                  {onSelect && !isTotal && <span style={{ marginLeft: 6, fontSize: "0.75rem" }}>›</span>}
                </td>
                <td style={styles.td}>{fmtBRL(row.receita_bruta)}</td>
                <td style={styles.td}>{fmtBRL(row.receita_liquida)}</td>
                <td style={styles.td}>{fmtBRL(row.custo)}</td>
                <td style={{ ...styles.td, color: isNegLB ? "#c0392b" : "#1a2e5a" }}>{fmtBRL(row.lucro_bruto)}</td>
                <td style={{ ...styles.td, color: isNegMG ? "#c0392b" : "#1a7a4a" }}>{fmtPct(row.margem_bruta)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    overflowX: "auto", borderRadius: 10, border: "1px solid #dde3f0",
    boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
  },
  table: { width: "100%", borderCollapse: "collapse", fontFamily: "'Segoe UI', sans-serif" },
  th: {
    background: "#2d50a0", color: "#fff", padding: "0.7rem 1rem",
    textAlign: "left", fontSize: "0.8rem", fontWeight: 600,
    textTransform: "uppercase", letterSpacing: 0.5,
  },
  tr: { transition: "background 0.15s" },
  td: { padding: "0.6rem 1rem", fontSize: "0.88rem", color: "#1a2e5a", borderBottom: "1px solid #eef0f6" },
};

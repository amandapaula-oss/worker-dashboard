import React, { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Mensal } from "../types";

interface Props {
  data: Mensal[];
}

const METRICS = [
  { label: "Receita Bruta",   key: "receita_bruta" },
  { label: "Receita Líquida", key: "receita_liquida" },
  { label: "Custo",           key: "custo" },
  { label: "Lucro Bruto",     key: "lucro_bruto" },
  { label: "Margem Bruta %",  key: "margem_bruta" },
];

function fmtBRL(v: number) {
  return `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}
function fmtPct(v: number) { return `${(v * 100).toFixed(1)}%`; }
function fmtVal(v: number, key: string) { return key === "margem_bruta" ? fmtPct(v) : fmtBRL(v); }

export default function MonthlySection({ data }: Props) {
  const [metric, setMetric] = useState("receita_bruta");
  const chartData = data.filter(d => d.competencia !== "Total");

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <select
          value={metric}
          onChange={e => setMetric(e.target.value)}
          style={styles.select}
        >
          {METRICS.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
        </select>
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
            labelStyle={{ color: "#1a2e5a" }}
          />
          <Bar dataKey={metric} radius={[4, 4, 0, 0]}>
            {chartData.map((_, i) => <Cell key={i} fill="#2d50a0" />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div style={{ overflowX: "auto", marginTop: 16, borderRadius: 10, border: "1px solid #dde3f0", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "'Segoe UI', sans-serif" }}>
          <thead>
            <tr>
              {["Competência", "Receita Bruta", "Receita Líquida", "Custo", "Lucro Bruto", "Margem Bruta %"].map(h => (
                <th key={h} style={{ background: "#2d50a0", color: "#fff", padding: "0.7rem 1rem", textAlign: "left", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: 0.5 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => {
              const isTotal = row.competencia === "Total";
              const isNegLB = row.lucro_bruto < 0;
              const isNegMG = row.margem_bruta < 0;
              return (
                <tr key={i} style={{ background: isTotal ? "#dce6f7" : i % 2 === 0 ? "#fff" : "#f9fafc", fontWeight: isTotal ? 700 : 400 }}>
                  <td style={{ padding: "0.6rem 1rem", fontSize: "0.88rem", color: "#1a2e5a", borderBottom: "1px solid #eef0f6" }}>{row.competencia}</td>
                  <td style={{ padding: "0.6rem 1rem", fontSize: "0.88rem", color: "#1a2e5a", borderBottom: "1px solid #eef0f6" }}>{fmtBRL(row.receita_bruta)}</td>
                  <td style={{ padding: "0.6rem 1rem", fontSize: "0.88rem", color: "#1a2e5a", borderBottom: "1px solid #eef0f6" }}>{fmtBRL(row.receita_liquida)}</td>
                  <td style={{ padding: "0.6rem 1rem", fontSize: "0.88rem", color: "#1a2e5a", borderBottom: "1px solid #eef0f6" }}>{fmtBRL(row.custo)}</td>
                  <td style={{ padding: "0.6rem 1rem", fontSize: "0.88rem", color: isNegLB ? "#c0392b" : "#1a2e5a", borderBottom: "1px solid #eef0f6" }}>{fmtBRL(row.lucro_bruto)}</td>
                  <td style={{ padding: "0.6rem 1rem", fontSize: "0.88rem", color: isNegMG ? "#c0392b" : "#1a7a4a", borderBottom: "1px solid #eef0f6" }}>{fmtPct(row.margem_bruta)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  select: {
    padding: "0.5rem 0.8rem", border: "1px solid #dde3f0", borderRadius: 8,
    fontSize: "0.9rem", color: "#1a2e5a", background: "#fff", cursor: "pointer",
  },
};

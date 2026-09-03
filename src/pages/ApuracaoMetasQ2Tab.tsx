import React, { useEffect, useMemo, useState } from "react";
import { Table, Tag, Segmented, message, Button } from "antd";
import { DownloadOutlined, LockOutlined, TrophyOutlined } from "@ant-design/icons";
import TableSkeleton from "../components/TableSkeleton";
import { getApuracaoMetas } from "../api";
import { useDraggableColumns } from "../hooks/useDraggableColumns";
import { exportTableToExcel } from "../utils/exportExcel";
import { theme } from "../theme";

type Trio = { realizado: number | null; meta: number | null; ating?: number | null; delta_pp?: number | null };
type Avaliado = {
  periodo: string; contrato: string | null; bu: string | null; avaliado: string;
  posicao: string | null; peso_meta: number | null; atingimento_final: number | null;
  salario: number | null; quantidade: number | null; apuracao_rs: number | null;
  receita: Trio; mb: Trio; lb: Trio;
};
type Payload = { gerado_em: string; fonte: string; q2: Avaliado[]; q1: Avaliado[] };

const fmtBRL = (v: number | null | undefined, dec = 0) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: dec, minimumFractionDigits: dec });
const fmtPct = (v: number | null | undefined, dec = 1) =>
  v == null ? "—" : `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: dec, minimumFractionDigits: dec })}%`;

const atingColor = (v: number | null | undefined) =>
  v == null ? "#9aa4bc" : v >= 1 ? "#0a7a3e" : v >= 0.85 ? "#b7791f" : "#c0392b";

function Delta({ v, pct = true }: { v: number | null | undefined; pct?: boolean }) {
  if (v == null) return <span style={{ color: "#9aa4bc" }}>—</span>;
  const good = v >= 0;
  return (
    <span style={{ color: good ? "#0a7a3e" : "#c0392b", fontWeight: 600 }}>
      {good ? "▲" : "▼"} {pct ? fmtPct(Math.abs(v)) : fmtBRL(Math.abs(v))}
    </span>
  );
}

export default function ApuracaoMetasQ2Tab() {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [periodo, setPeriodo] = useState<"Q2Y26" | "Q1Y26">("Q2Y26");

  useEffect(() => {
    getApuracaoMetas()
      .then(setData)
      .catch(() => message.error("Erro ao carregar apuração de metas"))
      .finally(() => setLoading(false));
  }, []);

  const rows = useMemo(() => {
    const src = periodo === "Q2Y26" ? data?.q2 : data?.q1;
    return (src ?? []).map((r, i) => ({ ...r, key: i }));
  }, [data, periodo]);

  const diretores = useMemo(() => rows.filter(r => (r.posicao || "").toLowerCase() === "diretor"), [rows]);

  const columnsDef = [
    { title: "BU", dataIndex: "bu", key: "bu", width: 150, render: (v: string) => v || "—" },
    {
      title: "Avaliado", dataIndex: "avaliado", key: "avaliado", ellipsis: true,
      render: (v: string, r: any) => (
        <span style={{ fontWeight: (r.posicao || "").toLowerCase() === "diretor" ? 700 : 400 }}>{v}</span>
      ),
    },
    { title: "Posição", dataIndex: "posicao", key: "posicao", width: 82 },
    { title: "Contrato", dataIndex: "contrato", key: "contrato", width: 78 },
    { title: "Receita Meta", key: "rec_meta", align: "right" as const, width: 120, render: (_: any, r: any) => fmtBRL(r.receita?.meta) },
    { title: "Receita Realizado", key: "rec_real", align: "right" as const, width: 130, render: (_: any, r: any) => <b>{fmtBRL(r.receita?.realizado)}</b> },
    {
      title: "Ating. Receita", key: "rec_ating", align: "center" as const, width: 105,
      render: (_: any, r: any) => <span style={{ color: atingColor(r.receita?.ating), fontWeight: 700 }}>{fmtPct(r.receita?.ating)}</span>,
    },
    { title: "MB% Meta", key: "mb_meta", align: "center" as const, width: 90, render: (_: any, r: any) => fmtPct(r.mb?.meta) },
    {
      title: "MB% Realizado", key: "mb_real", align: "center" as const, width: 110,
      render: (_: any, r: any) => <b style={{ color: (r.mb?.realizado ?? 0) < 0 ? "#c0392b" : undefined }}>{fmtPct(r.mb?.realizado)}</b>,
    },
    { title: "Δ MB (p.p.)", key: "mb_delta", align: "center" as const, width: 100, render: (_: any, r: any) => <Delta v={r.mb?.delta_pp} /> },
    { title: "LB/MC Meta", key: "lb_meta", align: "right" as const, width: 115, render: (_: any, r: any) => fmtBRL(r.lb?.meta) },
    {
      title: "LB/MC Realizado", key: "lb_real", align: "right" as const, width: 125,
      render: (_: any, r: any) => <b style={{ color: (r.lb?.realizado ?? 0) < 0 ? "#c0392b" : undefined }}>{fmtBRL(r.lb?.realizado)}</b>,
    },
    {
      title: "Ating. LB", key: "lb_ating", align: "center" as const, width: 90,
      render: (_: any, r: any) => <span style={{ color: atingColor(r.lb?.ating), fontWeight: 600 }}>{fmtPct(r.lb?.ating)}</span>,
    },
    {
      title: "Atingimento Final", dataIndex: "atingimento_final", key: "ating_final", align: "center" as const, width: 120,
      render: (v: number | null) => v == null ? "—" : (
        <Tag color={v >= 1 ? "green" : v > 0 ? "gold" : "red"} style={{ fontWeight: 700 }}>{fmtPct(v, 0)}</Tag>
      ),
    },
    { title: "Salário", dataIndex: "salario", key: "salario", align: "right" as const, width: 105, render: (v: number | null) => fmtBRL(v) },
    {
      title: "Bônus Apurado", dataIndex: "apuracao_rs", key: "apuracao_rs", align: "right" as const, width: 120,
      render: (v: number | null) => <b style={{ color: (v ?? 0) > 0 ? "#0a7a3e" : undefined }}>{fmtBRL(v, 2)}</b>,
    },
  ];
  const [columns, colSettings] = useDraggableColumns(columnsDef, "apuracao_metas_q2");

  return (
    <div>
      <div style={{ background: "#fff3cd", border: "1px solid #e8d48b", borderRadius: 10, padding: "0.55rem 1.1rem", marginBottom: 14, display: "flex", alignItems: "center", gap: 10 }}>
        <LockOutlined style={{ color: "#856404" }} />
        <span style={{ fontSize: "0.82rem", color: "#856404" }}>
          <b>Visão restrita (somente administradores).</b> Fonte: {data?.fonte || "Metas Oficiais (Yuri)"} · gerada em {data?.gerado_em || "—"}. Os diretores ainda não têm acesso.
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <TrophyOutlined style={{ color: theme.accent, fontSize: 20 }} />
        <span style={{ fontWeight: 700, fontSize: "1rem" }}>Apuração de Metas — {periodo === "Q2Y26" ? "2º trimestre 2026" : "1º trimestre 2026"}</span>
        <Segmented options={["Q2Y26", "Q1Y26"]} value={periodo} onChange={v => setPeriodo(v as any)} />
      </div>

      {loading ? <TableSkeleton rows={8} /> : (
        <>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 18 }}>
            {diretores.map(d => (
              <div key={d.avaliado + d.bu} style={{ flex: 1, minWidth: 215, background: "#fff", border: "1px solid #dde3f0", borderTop: `3px solid ${atingColor(d.receita?.ating)}`, borderRadius: 10, padding: "0.8rem 1rem", boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}>
                <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#6b7fa3", textTransform: "uppercase", letterSpacing: 0.4 }}>{d.bu}</div>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>{d.avaliado} <span style={{ fontWeight: 400, color: "#9aa4bc", fontSize: "0.78rem" }}>· Diretor</span></div>
                <div style={{ fontSize: "0.8rem", lineHeight: 1.7 }}>
                  <div>Receita: <b>{fmtBRL(d.receita?.realizado)}</b> <span style={{ color: "#9aa4bc" }}>/ {fmtBRL(d.receita?.meta)}</span> <span style={{ color: atingColor(d.receita?.ating), fontWeight: 700 }}>({fmtPct(d.receita?.ating, 0)})</span></div>
                  <div>MB%: <b style={{ color: (d.mb?.realizado ?? 0) < 0 ? "#c0392b" : undefined }}>{fmtPct(d.mb?.realizado)}</b> <span style={{ color: "#9aa4bc" }}>/ meta {fmtPct(d.mb?.meta)}</span></div>
                  <div>LB/MC: <b style={{ color: (d.lb?.realizado ?? 0) < 0 ? "#c0392b" : undefined }}>{fmtBRL(d.lb?.realizado)}</b> <span style={{ color: "#9aa4bc" }}>/ {fmtBRL(d.lb?.meta)}</span></div>
                </div>
              </div>
            ))}
          </div>

          <Table
            dataSource={rows}
            columns={columns}
            title={() => (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 0 4px" }}>
                <span style={{ fontSize: "0.8rem", color: "#6b7fa3" }}>{rows.length} avaliados (AEs e Diretores) — números idênticos à planilha oficial de metas</span>
                <div style={{ display: "flex", gap: 4 }}>
                  {colSettings}
                  <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                    onClick={() => exportTableToExcel(columns, rows, `apuracao_metas_${periodo}`)}>Excel</Button>
                </div>
              </div>
            )}
            pagination={false}
            size="small"
            scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
            onRow={r => (r.posicao || "").toLowerCase() === "diretor" ? { style: { background: "#f2f6ff" } } : {}}
          />
        </>
      )}
    </div>
  );
}

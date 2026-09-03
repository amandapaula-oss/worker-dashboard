import React, { useEffect, useMemo, useState } from "react";
import { Table, Tag, Segmented, message, Button, Divider } from "antd";
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
type DetRow = {
  bu: string; arquivo: string; aba: string; origem: "bloco" | "referencia";
  avaliado: string; posicao: string | null; trimestre: string; metrica: string;
  meta: number | null; realizado: number | null; atingimento: number | null;
  peso: number | null; trigger: number | null;
  salario: number | null; quantidade: number | null; bonus: number | null; obs: string | null;
};
type Payload = { gerado_em: string; fonte: string; q2: Avaliado[]; q1: Avaliado[]; detalhe?: { fontes: string[]; rows: DetRow[] } };

const fmtBRL = (v: number | null | undefined, dec = 0) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: dec, minimumFractionDigits: dec });
const fmtPct = (v: number | null | undefined, dec = 1) =>
  v == null ? "—" : `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: dec, minimumFractionDigits: dec })}%`;
const atingColor = (v: number | null | undefined) =>
  v == null ? "#9aa4bc" : v >= 1 ? "#0a7a3e" : v >= 0.85 ? "#b7791f" : "#c0392b";

const METRICA_ORDEM: { key: string; label: string; pct?: boolean; gate?: boolean }[] = [
  { key: "outra:receita_next_gen", label: "Receita Next Gen" },
  { key: "outra:receita_ecossistema", label: "Receita Ecossistema" },
  { key: "receita", label: "Receita Total" },
  { key: "mb", label: "MB %", pct: true },
  { key: "mc", label: "MC %", pct: true },
  { key: "lb", label: "LB (Lucro Bruto)" },
  { key: "outra:trigger_lb", label: "Trigger LB (gatilho)", gate: true },
  { key: "outra:trigger_mc", label: "Trigger MC (gatilho)", gate: true },
];
const BUS = ["Finance", "Grupo Mult", "Health", "Multisector", "Retail"];
const TRIS = ["Q1Y26", "Q2Y26", "Q3Y26", "Q4Y26", "ANUAL"];
const ABA_PRIO: Record<string, number> = { AE: 0, "AE G MULT": 1, DIRETOR: 2 };

function Delta({ v, pct = true }: { v: number | null | undefined; pct?: boolean }) {
  if (v == null) return <span style={{ color: "#9aa4bc" }}>—</span>;
  const good = v >= 0;
  return (
    <span style={{ color: good ? "#0a7a3e" : "#c0392b", fontWeight: 600 }}>
      {good ? "▲" : "▼"} {pct ? fmtPct(Math.abs(v)) : fmtBRL(Math.abs(v))}
    </span>
  );
}

function BlocoAvaliado({ nome, rows, dark }: { nome: string; rows: DetRow[]; dark?: boolean }) {
  const total = rows.find(r => r.metrica === "outra:total");
  const posicao = rows[0]?.posicao || "";
  const metricas = METRICA_ORDEM
    .map(m => ({ ...m, r: rows.find(x => x.metrica === m.key) }))
    .filter(m => m.r && (m.r.meta != null || m.r.realizado != null || m.r.trigger != null));
  return (
    <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, marginBottom: 14, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.55rem 1rem", background: "#f6f8fd", borderBottom: "1px solid #e4e9f4", flexWrap: "wrap", gap: 8 }}>
        <span style={{ fontWeight: 700 }}>{nome} <span style={{ fontWeight: 400, color: "#9aa4bc", fontSize: "0.8rem" }}>· {posicao}</span></span>
        <span style={{ fontSize: "0.8rem", color: "#6b7fa3", display: "flex", gap: 14, alignItems: "center" }}>
          {total?.salario != null && <span>Salário: <b>{fmtBRL(total.salario, 2)}</b>{total?.quantidade ? ` × ${total.quantidade}` : ""}</span>}
          {total?.atingimento != null && (
            <span>Atingimento: <Tag color={total.atingimento >= 1 ? "green" : total.atingimento > 0 ? "gold" : "red"} style={{ fontWeight: 700, marginRight: 0 }}>{fmtPct(total.atingimento, 0)}</Tag></span>
          )}
          {total?.bonus != null && <span>Bônus: <b style={{ color: total.bonus > 0 ? "#0a7a3e" : "#9aa4bc" }}>{fmtBRL(total.bonus, 2)}</b></span>}
        </span>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
        <thead>
          <tr style={{ color: "#6b7fa3", textAlign: "right" }}>
            <th style={{ textAlign: "left", padding: "6px 12px", fontWeight: 600 }}>Métrica</th>
            <th style={{ padding: "6px 12px", fontWeight: 600 }}>Peso</th>
            <th style={{ padding: "6px 12px", fontWeight: 600 }}>Meta</th>
            <th style={{ padding: "6px 12px", fontWeight: 600 }}>Realizado</th>
            <th style={{ padding: "6px 12px", fontWeight: 600 }}>Trigger mín.</th>
            <th style={{ padding: "6px 12px", fontWeight: 600 }}>Atingimento</th>
          </tr>
        </thead>
        <tbody>
          {metricas.map(m => {
            const r = m.r!;
            const fv = (v: number | null) => (m.pct ? fmtPct(v) : fmtBRL(v));
            return (
              <tr key={m.key} style={{ borderTop: "1px solid #eef2fa", background: m.gate ? "#fbfcff" : undefined, color: m.gate ? "#8a94ad" : undefined }}>
                <td style={{ padding: "5px 12px", fontWeight: m.key === "receita" ? 700 : 400 }}>{m.label}</td>
                <td style={{ padding: "5px 12px", textAlign: "right" }}>{r.peso != null ? fmtPct(r.peso, 0) : "—"}</td>
                <td style={{ padding: "5px 12px", textAlign: "right" }}>{fv(r.meta)}</td>
                <td style={{ padding: "5px 12px", textAlign: "right", fontWeight: 700, color: r.realizado != null && r.meta != null && r.realizado < (r.trigger ?? r.meta) ? "#c0392b" : undefined }}>{fv(r.realizado)}</td>
                <td style={{ padding: "5px 12px", textAlign: "right" }}>{fv(r.trigger)}</td>
                <td style={{ padding: "5px 12px", textAlign: "right", color: atingColor(r.atingimento), fontWeight: 700 }}>{r.atingimento != null ? fmtPct(r.atingimento, 0) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function ApuracaoMetasQ2Tab() {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [periodo, setPeriodo] = useState<"Q2Y26" | "Q1Y26">("Q2Y26");
  const [buSel, setBuSel] = useState<string>("Finance");
  const [triSel, setTriSel] = useState<string>("Q2Y26");

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

  // detalhe: blocos oficiais da BU/trimestre selecionados, 1 bloco por avaliado (dedup por prioridade de aba)
  const blocos = useMemo(() => {
    const det = (data?.detalhe?.rows ?? []).filter(r => r.bu === buSel || (buSel === "Grupo Mult" && r.bu === "Grupo Mult"));
    const doTri = det.filter(r => r.trimestre === triSel && r.origem === "bloco");
    const porAvaliado = new Map<string, DetRow[]>();
    for (const r of doTri) {
      const k = r.avaliado.toUpperCase().replace(/\s+/g, " ");
      const cur = porAvaliado.get(k);
      if (!cur) porAvaliado.set(k, [r]);
      else {
        const curPrio = ABA_PRIO[cur[0].aba] ?? 9, novaPrio = ABA_PRIO[r.aba] ?? 9;
        if (r.aba === cur[0].aba) cur.push(r);
        else if (novaPrio < curPrio) porAvaliado.set(k, [r]);
      }
    }
    return Array.from(porAvaliado.values())
      .map(rs => ({ nome: rs[0].avaliado, rs }))
      .sort((a, b) => ((a.rs[0].posicao || "") > (b.rs[0].posicao || "") ? 1 : -1) || a.nome.localeCompare(b.nome));
  }, [data, buSel, triSel]);

  const referencias = useMemo(() => {
    const det = (data?.detalhe?.rows ?? []).filter(r => r.bu === buSel && r.trimestre === triSel && r.origem === "referencia");
    const comBloco = new Set(blocos.map(b => b.nome.toUpperCase()));
    return det.filter(r => !comBloco.has(r.avaliado.toUpperCase()) && !/^total/i.test(r.avaliado) && ["receita", "mb", "lb"].includes(r.metrica));
  }, [data, buSel, triSel, blocos]);

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
          <b>Visão restrita (somente administradores).</b> Fonte: planilhas oficiais de metas (RESUMO + apurações por BU do Yuri) · gerada em {data?.gerado_em || "—"}. Os diretores ainda não têm acesso.
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <TrophyOutlined style={{ color: theme.accent, fontSize: 20 }} />
        <span style={{ fontWeight: 700, fontSize: "1rem" }}>Resumo geral — {periodo === "Q2Y26" ? "2º trimestre 2026" : "1º trimestre 2026"}</span>
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

          {data?.detalhe && (
            <>
              <Divider style={{ margin: "26px 0 14px" }} />
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6, flexWrap: "wrap" }}>
                <TrophyOutlined style={{ color: theme.accent, fontSize: 20 }} />
                <span style={{ fontWeight: 700, fontSize: "1rem" }}>Detalhe oficial por BU — todos os trimestres</span>
                <Segmented options={BUS} value={buSel} onChange={v => setBuSel(v as string)} />
                <Segmented options={TRIS.map(t => ({ label: t === "ANUAL" ? "Anual 2026" : t, value: t }))} value={triSel} onChange={v => setTriSel(v as string)} />
              </div>
              <div style={{ fontSize: "0.78rem", color: "#9aa4bc", marginBottom: 14 }}>
                Reprodução dos quadros das planilhas "Apuração Meta {buSel} OFICIAL" — mesma métrica, peso, trigger, atingimento e bônus. Realizado disponível até Q2Y26; Q3/Q4 mostram as metas contratadas.
              </div>
              {blocos.length === 0 && <div style={{ color: "#9aa4bc", padding: "1rem" }}>Sem bloco de apuração para {buSel} em {triSel}.</div>}
              {blocos.map(b => <BlocoAvaliado key={b.nome} nome={b.nome} rows={b.rs} />)}
              {referencias.length > 0 && (
                <div style={{ fontSize: "0.78rem", color: "#8a94ad", marginTop: 6 }}>
                  Metas de referência (avaliados sem bloco oficial neste trimestre):{" "}
                  {Array.from(new Set(referencias.map(r => r.avaliado))).join(", ")} — valores no export Excel do resumo.
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

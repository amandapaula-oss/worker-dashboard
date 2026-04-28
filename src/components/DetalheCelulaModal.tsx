import React, { useEffect, useState } from "react";
import { Modal, Table, Tag, Spin, Statistic, Card } from "antd";
import { getNovaBaseData } from "../api";
import { theme } from "../theme";
import { periodoLabel } from "../utils/format";

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const FONTE_COLORS: Record<string, string> = {
  custo_project: "blue", racionais: "green", CLTs: "purple",
  PJs: "orange", "Custo Socios": "red", "de para": "default",
  TDMs: "cyan", "Equipe Labs": "magenta", "Equipe Play": "volcano",
  custo_gerencial: "geekblue",
};

interface Props {
  open: boolean;
  onClose: () => void;
  filters: Record<string, string>;
  titulo: string;
  metricLabel?: string;
}

export default function DetalheCelulaModal({ open, onClose, filters, titulo, metricLabel }: Props) {
  const [loading, setLoading] = useState(false);
  const [rows, setRows]       = useState<any[]>([]);
  const [total, setTotal]     = useState(0);
  const [truncated, setTruncated] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getNovaBaseData(filters)
      .then(r => {
        setRows(r.rows || []);
        setTotal(r.total || 0);
        setTruncated(!!r.truncated);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, JSON.stringify(filters)]);

  // KPIs do que está sendo mostrado
  const totRec = rows.reduce((s, r) => s + (Number(r.receita) || 0), 0);
  const totCus = rows.reduce((s, r) => s + (Number(r.custo_rateado) || 0), 0);
  const totHrs = rows.reduce((s, r) => s + (Number(r.horas) || 0), 0);
  const totVL  = rows.reduce((s, r) => s + (Number(r.valor_liquido) || 0), 0);

  const fmt = (v: any) =>
    v == null || v === "" ? "—" : typeof v === "number"
      ? v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : String(v);

  const cols: any[] = [
    { title: "Fonte", dataIndex: "fonte", width: 120,
      render: (v: string) => <Tag color={FONTE_COLORS[v] ?? "default"}>{v}</Tag> },
    { title: "Período", dataIndex: "periodo", width: 80,
      render: (v: string) => v ? periodoLabel(v) : "—" },
    { title: "Empresa", dataIndex: "empresa", width: 100, ellipsis: true },
    { title: "PEP", dataIndex: "pep_base", width: 130 },
    { title: "Pessoa", dataIndex: "nome_pessoa", width: 180, ellipsis: true },
    { title: "Cliente", dataIndex: "nome_cliente", width: 180, ellipsis: true },
    { title: "Vertical", dataIndex: "vertical", width: 130, ellipsis: true },
    { title: "Macro Área", dataIndex: "macro_area", width: 110, ellipsis: true },
    { title: "Receita", dataIndex: "receita", align: "right" as const, width: 110,
      render: (v: number) => <span style={{ fontWeight: (v||0) !== 0 ? 600 : 400 }}>{fmt(v)}</span> },
    { title: "Custo Rateado", dataIndex: "custo_rateado", align: "right" as const, width: 110,
      render: (v: number) => <span style={{ color: (v||0) < 0 ? "#c0392b" : theme.text }}>{fmt(v)}</span> },
    { title: "Horas", dataIndex: "horas", align: "right" as const, width: 80, render: fmt },
    { title: "Margem", dataIndex: "margem", align: "right" as const, width: 110,
      render: (v: number) => <span style={{ color: (v||0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 600 }}>{fmt(v)}</span> },
    { title: "Vlr Líq", dataIndex: "valor_liquido", align: "right" as const, width: 100, render: fmt },
    { title: "Tag Rateio", dataIndex: "tag_rateio", width: 220, ellipsis: true },
  ];

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width="92%"
      title={<div><strong>Detalhe</strong> — {titulo}{metricLabel ? <span style={{ color: "#6b7fa3", fontWeight: 400 }}> · {metricLabel}</span> : null}</div>}
      style={{ top: 20 }}
      destroyOnClose
    >
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        {[
          { label: "Linhas", value: rows.length.toLocaleString("pt-BR"), color: theme.text },
          { label: "Receita", value: brl(totRec), color: theme.text },
          { label: "Custo Rateado", value: brl(totCus), color: totCus < 0 ? "#c0392b" : theme.text },
          { label: "Margem", value: brl(totRec + totCus), color: (totRec+totCus) < 0 ? "#c0392b" : "#0a7a3e" },
          { label: "Horas", value: totHrs.toLocaleString("pt-BR", { maximumFractionDigits: 0 }), color: theme.text },
          { label: "Vlr Líq", value: brl(totVL), color: totVL < 0 ? "#c0392b" : theme.text },
        ].map(k => (
          <Card key={k.label} style={{ flex: 1, minWidth: 130, borderRadius: 8, border: "1px solid #dde3f0" }}
            styles={{ body: { padding: "0.5rem 0.8rem", textAlign: "center" } }}>
            <Statistic title={<span style={{ color: "#6b7fa3", fontSize: "0.7rem", fontWeight: 600, textTransform: "uppercase" }}>{k.label}</span>}
              value={k.value} valueStyle={{ color: k.color, fontSize: "0.95rem", fontWeight: 700 }} />
          </Card>
        ))}
      </div>
      {truncated && (
        <div style={{ marginBottom: 8, padding: "0.5rem 0.8rem", background: "#fffbe6", border: "1px solid #ffe58f", borderRadius: 6, fontSize: "0.8rem", color: "#856404" }}>
          Total na base: {total.toLocaleString("pt-BR")} linhas. Exibindo as primeiras 5.000 — refine os filtros se precisar ver as outras.
        </div>
      )}
      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <Table
          dataSource={rows}
          columns={cols}
          rowKey={(_, i) => String(i)}
          size="small"
          scroll={{ x: 1700, y: 400 }}
          pagination={{
            defaultPageSize: 50,
            showSizeChanger: true,
            pageSizeOptions: ["50","100","200"],
          }}
        />
      )}
    </Modal>
  );
}

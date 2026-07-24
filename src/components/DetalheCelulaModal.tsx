import React, { useEffect, useMemo, useState } from "react";
import { Modal, Table, Tag, Spin, Statistic, Card, Select, Checkbox, Popover, Button } from "antd";
import { SettingOutlined, FilterOutlined } from "@ant-design/icons";
import { getNovaBaseData, getNovaBaseFilters } from "../api";
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

type ColKey = "fonte" | "periodo" | "empresa" | "pep_base" | "nome_pessoa" |
              "nome_cliente" | "vertical" | "macro_area" | "no_hierarquia" | "apuracao" |
              "tipo_contrato" | "classificacao" | "fonte_dados" |
              "receita" | "custo_rateado" | "horas" | "margem" | "valor_liquido" | "tag_rateio";

const ALL_COLS: { key: ColKey; label: string }[] = [
  { key: "fonte",          label: "Fonte" },
  { key: "fonte_dados",    label: "Fonte (origem)" },
  { key: "periodo",        label: "Período" },
  { key: "empresa",        label: "Empresa" },
  { key: "pep_base",       label: "PEP" },
  { key: "nome_pessoa",    label: "Pessoa" },
  { key: "nome_cliente",   label: "Cliente" },
  { key: "vertical",       label: "Vertical" },
  { key: "macro_area",     label: "Macro Área" },
  { key: "no_hierarquia",  label: "Centro de Lucro" },
  { key: "apuracao",       label: "Apuração" },
  { key: "tipo_contrato",  label: "Tipo Contrato" },
  { key: "classificacao",  label: "Classificação" },
  { key: "receita",        label: "Receita" },
  { key: "custo_rateado",  label: "Custo Rateado" },
  { key: "horas",          label: "Horas" },
  { key: "margem",         label: "Margem" },
  { key: "valor_liquido",  label: "Vlr Líq" },
  { key: "tag_rateio",     label: "Tag Rateio" },
];

const DEFAULT_VISIBLE: ColKey[] = [
  "fonte", "periodo", "empresa", "pep_base", "nome_pessoa", "nome_cliente",
  "vertical", "macro_area", "receita", "custo_rateado", "horas", "margem",
  "valor_liquido", "tag_rateio",
];

export default function DetalheCelulaModal({ open, onClose, filters, titulo, metricLabel }: Props) {
  const [loading, setLoading] = useState(false);
  const [rows, setRows]       = useState<any[]>([]);
  const [total, setTotal]     = useState(0);
  const [truncated, setTruncated] = useState(false);

  // Filtros extras aplicaveis no popup (alem dos filtros base passados via props)
  const [extraFilters, setExtraFilters] = useState<Record<string, string[]>>({});
  // Opcoes pros selects (carregadas 1x)
  const [filterOpts, setFilterOpts] = useState<any>({});

  // Visibilidade de colunas (persistida em localStorage)
  const [visibleCols, setVisibleCols] = useState<Set<ColKey>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("modal:detalhe-cols:v1") || "null");
      if (Array.isArray(saved)) return new Set(saved as ColKey[]);
    } catch {}
    return new Set<ColKey>(DEFAULT_VISIBLE);
  });

  // Carga das opcoes de filtro
  useEffect(() => {
    if (!open || Object.keys(filterOpts).length > 0) return;
    getNovaBaseFilters().then(setFilterOpts).catch(() => {});
  }, [open, filterOpts]);

  // Mescla filtros base + extras pra fetch
  const mergedFilters = useMemo(() => {
    const out: Record<string, string> = { ...filters };
    for (const [k, v] of Object.entries(extraFilters)) {
      if (v && v.length) out[k] = v.join(",");
    }
    return out;
  }, [filters, extraFilters]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getNovaBaseData(mergedFilters)
      .then(r => {
        setRows(r.rows || []);
        setTotal(r.total || 0);
        setTruncated(!!r.truncated);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, JSON.stringify(mergedFilters)]);

  // Reseta extras quando muda o card clicado (filters base mudou)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setExtraFilters({}); }, [JSON.stringify(filters)]);

  // KPIs
  const totRec = rows.reduce((s, r) => s + (Number(r.receita) || 0), 0);
  const totCus = rows.reduce((s, r) => s + (Number(r.custo_rateado) || 0), 0);
  const totHrs = rows.reduce((s, r) => s + (Number(r.horas) || 0), 0);

  const fmt = (v: any) =>
    v == null || v === "" ? "—" : typeof v === "number"
      ? v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : String(v);

  const allColsDef: Record<ColKey, any> = {
    fonte:          { title: "Fonte", dataIndex: "fonte", width: 120,
                      render: (v: string) => <Tag color={FONTE_COLORS[v] ?? "default"}>{v}</Tag> },
    fonte_dados:    { title: "Fonte (origem)", dataIndex: "fonte_dados", width: 200, ellipsis: true },
    periodo:        { title: "Período", dataIndex: "periodo", width: 80,
                      render: (v: string) => v ? periodoLabel(v) : "—" },
    empresa:        { title: "Empresa", dataIndex: "empresa", width: 110, ellipsis: true },
    pep_base:       { title: "PEP", dataIndex: "pep_base", width: 130 },
    nome_pessoa:    { title: "Pessoa", dataIndex: "nome_pessoa", width: 180, ellipsis: true },
    nome_cliente:   { title: "Cliente", dataIndex: "nome_cliente", width: 180, ellipsis: true },
    vertical:       { title: "Vertical", dataIndex: "vertical", width: 130, ellipsis: true },
    macro_area:     { title: "Macro Área", dataIndex: "macro_area", width: 110, ellipsis: true },
    no_hierarquia:  { title: "Centro de Lucro", dataIndex: "no_hierarquia", width: 160, ellipsis: true },
    apuracao:       { title: "Apuração", dataIndex: "apuracao", width: 110, ellipsis: true },
    tipo_contrato:  { title: "Tipo Contrato", dataIndex: "tipo_contrato", width: 110, ellipsis: true },
    classificacao:  { title: "Classificação", dataIndex: "classificacao", width: 110, ellipsis: true },
    receita:        { title: "Receita", dataIndex: "receita", align: "right" as const, width: 110,
                      render: (v: number) => <span style={{ fontWeight: (v||0) !== 0 ? 600 : 400 }}>{fmt(v)}</span> },
    custo_rateado:  { title: "Custo Rateado", dataIndex: "custo_rateado", align: "right" as const, width: 110,
                      render: (v: number) => <span style={{ color: (v||0) < 0 ? "#c0392b" : theme.text }}>{fmt(v)}</span> },
    horas:          { title: "Horas", dataIndex: "horas", align: "right" as const, width: 80, render: fmt },
    margem:         { title: "Margem", dataIndex: "margem", align: "right" as const, width: 110,
                      render: (v: number) => <span style={{ color: (v||0) < 0 ? "#c0392b" : "#0a7a3e", fontWeight: 600 }}>{fmt(v)}</span> },
    valor_liquido:  { title: "Vlr Líq", dataIndex: "valor_liquido", align: "right" as const, width: 100, render: fmt },
    tag_rateio:     { title: "Tag Rateio", dataIndex: "tag_rateio", width: 220, ellipsis: true },
  };

  const cols = ALL_COLS.filter(c => visibleCols.has(c.key)).map(c => allColsDef[c.key]);

  const toggleCol = (k: ColKey) => {
    setVisibleCols(prev => {
      const next = new Set(prev);
      if (next.has(k)) { if (next.size > 1) next.delete(k); }
      else next.add(k);
      localStorage.setItem("modal:detalhe-cols:v1", JSON.stringify(Array.from(next)));
      return next;
    });
  };

  const opt = (arr: string[]) => (arr || []).map(v => ({ label: v, value: v }));

  // Define quais filtros estao "fixos" pelo card clicado (mostra como tag, nao editavel)
  const fixedFilterKeys = new Set(Object.keys(filters).filter(k => k !== "metric"));
  const filtroAtivo = Object.keys(extraFilters).some(k => (extraFilters[k] || []).length > 0);

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
      {/* Filtros extras + seletor de colunas */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        <FilterOutlined style={{ color: "#6b7fa3" }} />
        <Select mode="multiple" placeholder="Período" style={{ minWidth: 140 }} size="small"
          value={extraFilters.periodos || []}
          options={opt(filterOpts.periodos)}
          onChange={(v) => setExtraFilters(s => ({ ...s, periodos: v }))}
          maxTagCount="responsive" allowClear />
        <Select mode="multiple" placeholder="Fonte" style={{ minWidth: 140 }} size="small"
          value={extraFilters.fontes || []}
          options={opt(filterOpts.fontes)}
          onChange={(v) => setExtraFilters(s => ({ ...s, fontes: v }))}
          maxTagCount="responsive" allowClear
          disabled={fixedFilterKeys.has("fontes")} />
        <Select mode="multiple" placeholder="Empresa" style={{ minWidth: 150 }} size="small"
          value={extraFilters.empresas || []}
          options={opt(filterOpts.empresas)}
          onChange={(v) => setExtraFilters(s => ({ ...s, empresas: v }))}
          maxTagCount="responsive" allowClear
          disabled={fixedFilterKeys.has("empresas")} />
        <Select mode="multiple" placeholder="BU" style={{ minWidth: 130 }} size="small"
          value={extraFilters.verticais || []}
          options={opt(filterOpts.verticais)}
          onChange={(v) => setExtraFilters(s => ({ ...s, verticais: v }))}
          maxTagCount="responsive" allowClear
          disabled={fixedFilterKeys.has("verticais")} />
        <Select mode="multiple" placeholder="Macro Área" style={{ minWidth: 140 }} size="small"
          value={extraFilters.macro_areas || []}
          options={opt(filterOpts.macro_areas)}
          onChange={(v) => setExtraFilters(s => ({ ...s, macro_areas: v }))}
          maxTagCount="responsive" allowClear />
        <Select mode="multiple" placeholder="Centro de Lucro" style={{ minWidth: 150 }} size="small"
          value={extraFilters.no_hierarquias || []}
          options={opt(filterOpts.no_hierarquias)}
          onChange={(v) => setExtraFilters(s => ({ ...s, no_hierarquias: v }))}
          maxTagCount="responsive" allowClear />
        {filtroAtivo && (
          <Button size="small" danger onClick={() => setExtraFilters({})}>Limpar</Button>
        )}
        <span style={{ marginLeft: "auto" }}>
          <Popover trigger="click" placement="bottomRight" title="Colunas visíveis"
            content={
              <div style={{ minWidth: 160, maxHeight: 360, overflowY: "auto" }}>
                {ALL_COLS.map(c => (
                  <div key={c.key} style={{ padding: "3px 0" }}>
                    <Checkbox checked={visibleCols.has(c.key)} onChange={() => toggleCol(c.key)}>
                      {c.label}
                    </Checkbox>
                  </div>
                ))}
              </div>
            }
          >
            <Button size="small" icon={<SettingOutlined />}>Colunas</Button>
          </Popover>
        </span>
      </div>

      {/* KPIs */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        {[
          { label: "Linhas", value: rows.length.toLocaleString("pt-BR"), color: theme.text },
          { label: "Receita", value: brl(totRec), color: theme.text },
          { label: "Custo Rateado", value: brl(totCus), color: totCus < 0 ? "#c0392b" : theme.text },
          // Receita + custo = Lucro Bruto do recorte (nao e a Margem Bruta oficial,
          // que fixa Eco em 33,3%). "Vlr Liq" removido: campo valor_liquido cru e
          // poluido pela fonte P&L Holding e nao representa lucro.
          { label: "Lucro Bruto", value: brl(totRec + totCus), color: (totRec+totCus) < 0 ? "#c0392b" : "#0a7a3e" },
          { label: "Horas", value: totHrs.toLocaleString("pt-BR", { maximumFractionDigits: 0 }), color: theme.text },
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

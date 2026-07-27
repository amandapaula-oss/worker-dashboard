import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Select, Table, Button, Card, Statistic, Popover, Checkbox } from "antd";
import { FilterOutlined, DownloadOutlined, SettingOutlined } from "@ant-design/icons";
import { getNovaBaseFilters, getNovaBaseResumo, getNovaBaseDre } from "../api";
import TableSkeleton from "../components/TableSkeleton";
import { useNovaBaseFilters } from "../contexts/NovaBaseFilters";
import PLTable from "../components/PLTable";
import ErrorState from "../components/ErrorState";
import DetalheCelulaModal from "../components/DetalheCelulaModal";
import { theme } from "../theme";
import { exportTableToExcel, exportPLTableToExcel } from "../utils/exportExcel";
import { periodoLabel } from "../utils/format";

const AGRUPAR_PARAM_KEY: Record<string, string> = {
  empresa: "empresas", vertical: "verticais", fonte: "fontes", macro_area: "macro_areas",
  tipo_pessoa: "tipo_pessoa", apuracao: "apuracoes",
};

/* Timer que aparece após 5s de loading para informar sobre cold start */
function WarmUpNotice() {
  const [elapsed, setElapsed] = useState(0);
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t0 = Date.now();
    const id = setInterval(() => {
      const s = Math.floor((Date.now() - t0) / 1000);
      setElapsed(s);
      if (s >= 5) setShow(true);
    }, 1000);
    return () => clearInterval(id);
  }, []);
  if (!show) return null;
  return (
    <div style={{ marginTop: 16, color: "#6b7fa3", fontSize: "0.85rem", textAlign: "center" }}>
      <span style={{ fontSize: 18, marginRight: 6 }}>⏳</span>
      Aguardando servidor... <strong>{elapsed}s</strong>
      <div style={{ marginTop: 4, fontSize: "0.78rem", opacity: 0.7 }}>
        O servidor pode demorar até 2 min para acordar na primeira vez.
      </div>
    </div>
  );
}


const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const ALL_METRICS = ["receita", "custo", "despesa", "custo_despesa", "custo_fonte", "margem", "margem_pct", "valor_liquido", "horas"] as const;
type Metric = typeof ALL_METRICS[number];
const METRIC_LABELS: Record<Metric, string> = {
  receita: "Receita", custo: "Custo", despesa: "Despesa", custo_despesa: "Custo + Despesa", custo_fonte: "Custo na Fonte", margem: "Margem", margem_pct: "Margem %", valor_liquido: "Lucro Bruto", horas: "Horas",
};

function MargemTag({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span style={{ color: "#aaa" }}>—</span>;
  const v = Number(value) * 100;
  const color = v >= 30 ? "#0a7a3e" : v >= 10 ? "#856404" : "#c0392b";
  const bg    = v >= 30 ? "#d4edda" : v >= 10 ? "#fff3cd" : "#fde8e8";
  return <span style={{ background: bg, color, fontWeight: 700, padding: "2px 8px", borderRadius: 4, fontSize: "0.85rem" }}>{v.toFixed(1)}%</span>;
}

const AGRUPAR_LABELS: Record<string, string> = {
  empresa: "Empresa", fonte: "Fonte", macro_area: "Macro Área", vertical: "BU",
  tipo_pessoa: "Tipo (CLT/PJ)", apuracao: "Apuração",
};

export default function NovaBaseResumoTab({ agruparPor = "empresa" }: { agruparPor?: string }) {
  const [filters, setFilters]           = useState<any>({});
  const {
    selPeriodos, setSelPeriodos,
    selEmpresas, setSelEmpresas,
    selFontes, setSelFontes,
    selApuracoes, setSelApuracoes,
    selNoHier, setSelNoHier,
    selVerticais,
    resetFilters, hasAnyFilter: ctxHasFilter,
    lockedVertical, periodoLocked,
  } = useNovaBaseFilters();
  const [rawData, setRawData]           = useState<any[]>([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [filtersReady, setFiltersReady] = useState(false);
  const [showFilters, setShowFilters]   = useState(false);
  const initialLoad = useRef(true);

  const [drillOpen, setDrillOpen]       = useState(false);
  const [drillFilters, setDrillFilters] = useState<Record<string, string>>({});
  const [drillTitulo, setDrillTitulo]   = useState("");
  const [drillMetric, setDrillMetric]   = useState("");

  const openDrill = (grupo: string, prefix: string, metric: string, metricLabel: string) => {
    const filters: Record<string, string> = {};
    if (selPeriodos.length) filters.periodos = selPeriodos.join(",");
    if (selEmpresas.length) filters.empresas = selEmpresas.join(",");
    if (selFontes.length)   filters.fontes   = selFontes.join(",");
    if (selVerticais.length) filters.verticais = selVerticais.join(",");
    if (selApuracoes.length) filters.apuracoes = selApuracoes.join(",");
    if (selNoHier.length)    filters.no_hierarquias = selNoHier.join(",");
    // Filtro do grupo clicado. Labels sinteticos (criados no backend pra agrupamento)
    // mapeiam pro sentinel "__blank__" porque a coluna real esta vazia.
    const paramKey = AGRUPAR_PARAM_KEY[agruparPor] || "empresas";
    // "Sem Apuração" saiu daqui: agora e valor ESCRITO na coluna (materializado
    // no fim do pipeline), entao o drill filtra pelo literal, nao por __blank__.
    const SYNTH_TO_BLANK: Record<string, string[]> = {
      macro_area: ["Projetos"],
    };
    const synthLabels = SYNTH_TO_BLANK[agruparPor] || [];
    filters[paramKey] = (synthLabels.includes(grupo) || grupo === "(vazio)") ? "__blank__" : grupo;
    // Período (se for célula de período específico)
    if (prefix !== "total") filters.periodos = prefix;
    // Coluna Total sem filtro de período selecionado: envia os períodos exibidos
    // na tabela — senão o /data traria meses fora do corte do resumo.
    else if (!selPeriodos.length && periodos.length) filters.periodos = periodos.join(",");
    // Métrica
    filters.metric = metric;
    setDrillFilters(filters);
    const periodoTxt = prefix === "total" ? "Total" : periodoLabel(prefix);
    setDrillTitulo(`${grupo} · ${periodoTxt}`);
    setDrillMetric(metricLabel);
    setDrillOpen(true);
  };

  const [visibleMetrics, setVisibleMetrics] = useState<Set<Metric>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("tbl:nb-resumo-metrics:v2") || "null");
      if (Array.isArray(saved)) return new Set(saved as Metric[]);
    } catch {}
    return new Set<Metric>(["receita", "custo", "despesa", "valor_liquido"]);
  });

  const toggleMetric = (m: Metric) => {
    setVisibleMetrics(prev => {
      const next = new Set(prev);
      if (next.has(m)) { if (next.size > 1) next.delete(m); }
      else next.add(m);
      localStorage.setItem("tbl:nb-resumo-metrics:v2", JSON.stringify(Array.from(next)));
      return next;
    });
  };

  useEffect(() => {
    getNovaBaseFilters()
      .then(f => { setFilters(f); setFiltersReady(true); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = { agrupar_por: agruparPor };
    if (selPeriodos.length)   params.periodos       = selPeriodos.join(",");
    if (selEmpresas.length)   params.empresas       = selEmpresas.join(",");
    if (selFontes.length)     params.fontes         = selFontes.join(",");
    if (selApuracoes.length)  params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)     params.no_hierarquias = selNoHier.join(",");
    if (selVerticais.length)  params.verticais      = selVerticais.join(",");
    getNovaBaseResumo(params)
      .then(r => { setRawData(r); initialLoad.current = false; setError(null); })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selPeriodos, selEmpresas, selFontes, selApuracoes, selNoHier, selVerticais, agruparPor]);

  useEffect(() => { if (filtersReady) load(); }, [filtersReady, load]);

  const periodos = useMemo(() =>
    Array.from(new Set(rawData.map((r: any) => r.periodo))).filter(Boolean).sort() as string[],
  [rawData]);

  const pivotData = useMemo(() => {
    const map = new Map<string, any>();
    for (const r of rawData) {
      const key = r.grupo || "(sem grupo)";
      if (!map.has(key)) map.set(key, { grupo: key });
      const e = map.get(key)!;
      e[`${r.periodo}_receita`]       = (e[`${r.periodo}_receita`]       || 0) + (Number(r.receita)       || 0);
      e[`${r.periodo}_custo`]         = (e[`${r.periodo}_custo`]         || 0) + (Number(r.custo_rateado) || 0);
      e[`${r.periodo}_despesa`]       = (e[`${r.periodo}_despesa`]       || 0) + (Number(r.despesa)       || 0);
      e[`${r.periodo}_horas`]         = (e[`${r.periodo}_horas`]         || 0) + (Number(r.horas)         || 0);
      e[`${r.periodo}_custo_fonte`]   = (e[`${r.periodo}_custo_fonte`]   || 0) + (Number(r.custo_fonte)  || 0);
      e[`${r.periodo}_receita_ng`]    = (e[`${r.periodo}_receita_ng`]    || 0) + (Number(r.receita_ng)   || 0);
      e[`${r.periodo}_receita_eco`]   = (e[`${r.periodo}_receita_eco`]   || 0) + (Number(r.receita_eco)  || 0);
      e[`${r.periodo}_custo_ng`]      = (e[`${r.periodo}_custo_ng`]      || 0) + (Number(r.custo_ng)     || 0);
      e[`${r.periodo}_custo_outro`]   = (e[`${r.periodo}_custo_outro`]   || 0) + (Number(r.custo_outro)  || 0);
    }
    return Array.from(map.values()).map(r => {
      periodos.forEach(p => {
        // Margem Bruta = Receita NG + Custo NG + Custo Outro + 33,3% da Receita Eco.
        // "Outro" = custo direto sem flag NG/Eco (rateados, REALOCFIN etc.).
        // Eco entra com margem fixa de 33,3% — custo real de Eco nao conta.
        r[`${p}_margem`] = (r[`${p}_receita_ng`] || 0) + (r[`${p}_custo_ng`] || 0) + (r[`${p}_custo_outro`] || 0) + 0.333 * (r[`${p}_receita_eco`] || 0);
        const rec = r[`${p}_receita`] || 0;
        r[`${p}_margem_pct`] = rec !== 0 ? r[`${p}_margem`] / rec : null;
        r[`${p}_custo_despesa`] = (r[`${p}_custo`] || 0) + (r[`${p}_despesa`] || 0);
        // Lucro Bruto = Receita - Custo (custo eh negativo). NAO usar o campo
        // valor_liquido cru: ele vem poluido por P&L Holding (linhas de receita=0
        // com valor_liquido de milhoes = consolidado da Holding, nao lucro por BU).
        r[`${p}_valor_liquido`] = (r[`${p}_receita`] || 0) + (r[`${p}_custo`] || 0);
      });
      const tot_rec = periodos.reduce((s, p) => s + (r[`${p}_receita`] || 0), 0);
      const tot_cus = periodos.reduce((s, p) => s + (r[`${p}_custo`]   || 0), 0);
      const tot_des = periodos.reduce((s, p) => s + (r[`${p}_despesa`] || 0), 0);
      const tot_mar = periodos.reduce((s, p) => s + (r[`${p}_margem`]  || 0), 0);
      return {
        ...r,
        total_receita:       tot_rec,
        total_custo:         tot_cus,
        total_despesa:       tot_des,
        total_custo_despesa: tot_cus + tot_des,
        total_margem:        tot_mar,
        total_margem_pct:    tot_rec !== 0 ? tot_mar / tot_rec : null,
        total_valor_liquido: periodos.reduce((s, p) => s + (r[`${p}_valor_liquido`] || 0), 0),
        total_horas:         periodos.reduce((s, p) => s + (r[`${p}_horas`]         || 0), 0),
        total_custo_fonte:   periodos.reduce((s, p) => s + (r[`${p}_custo_fonte`]   || 0), 0),
        total_receita_ng:    periodos.reduce((s, p) => s + (r[`${p}_receita_ng`]    || 0), 0),
        total_receita_eco:   periodos.reduce((s, p) => s + (r[`${p}_receita_eco`]   || 0), 0),
        total_custo_ng:      periodos.reduce((s, p) => s + (r[`${p}_custo_ng`]      || 0), 0),
        total_custo_outro:   periodos.reduce((s, p) => s + (r[`${p}_custo_outro`]   || 0), 0),
      };
    }).sort((a, b) => b.total_receita - a.total_receita);
  }, [rawData, periodos]);

  const totReceita = pivotData.reduce((s, r) => s + (r.total_receita || 0), 0);
  const totCusto   = pivotData.reduce((s, r) => s + (r.total_custo   || 0), 0);
  const totMargem  = pivotData.reduce((s, r) => s + (r.total_margem  || 0), 0);
  const totPct     = totReceita !== 0 ? totMargem / totReceita : 0;
  const totVL      = pivotData.reduce((s, r) => s + (r.total_valor_liquido || 0), 0);
  const totHoras   = pivotData.reduce((s, r) => s + (r.total_horas   || 0), 0);
  // MC = Margem de Contribuição = Margem Bruta + despesas (despesa é negativa)
  const totDespesaKpi = pivotData.reduce((s, r) => s + (r.total_despesa || 0), 0);
  const totMC      = totMargem + totDespesaKpi;
  const totMCPct   = totReceita !== 0 ? totMC / totReceita : 0;

  const tableData = useMemo(() => {
    const totDespesa = pivotData.reduce((s, r) => s + (r.total_despesa || 0), 0);
    const totRow: any = {
      key: "__t__", grupo: "TOTAL",
      total_receita: totReceita, total_custo: totCusto,
      total_despesa: totDespesa,
      total_custo_despesa: totCusto + totDespesa,
      total_custo_fonte: pivotData.reduce((s, r) => s + (r.total_custo_fonte || 0), 0),
      total_margem: totMargem, total_margem_pct: totPct,
      total_valor_liquido: totVL, total_horas: totHoras,
      total_receita_ng:  pivotData.reduce((s, r) => s + (r.total_receita_ng  || 0), 0),
      total_receita_eco: pivotData.reduce((s, r) => s + (r.total_receita_eco || 0), 0),
      total_custo_ng:    pivotData.reduce((s, r) => s + (r.total_custo_ng    || 0), 0),
      total_custo_outro: pivotData.reduce((s, r) => s + (r.total_custo_outro || 0), 0),
      _isTotal: true,
    };
    periodos.forEach(p => {
      totRow[`${p}_receita`]       = pivotData.reduce((s, r) => s + (r[`${p}_receita`]       || 0), 0);
      totRow[`${p}_custo`]         = pivotData.reduce((s, r) => s + (r[`${p}_custo`]         || 0), 0);
      totRow[`${p}_despesa`]       = pivotData.reduce((s, r) => s + (r[`${p}_despesa`]       || 0), 0);
      totRow[`${p}_custo_despesa`] = (totRow[`${p}_custo`] || 0) + (totRow[`${p}_despesa`] || 0);
      totRow[`${p}_custo_fonte`]   = pivotData.reduce((s, r) => s + (r[`${p}_custo_fonte`] || 0), 0);
      totRow[`${p}_margem`]        = pivotData.reduce((s, r) => s + (r[`${p}_margem`]        || 0), 0);
      const rec = totRow[`${p}_receita`] || 0;
      totRow[`${p}_margem_pct`]    = rec !== 0 ? totRow[`${p}_margem`] / rec : null;
      totRow[`${p}_valor_liquido`] = pivotData.reduce((s, r) => s + (r[`${p}_valor_liquido`] || 0), 0);
      totRow[`${p}_horas`]         = pivotData.reduce((s, r) => s + (r[`${p}_horas`]         || 0), 0);
      totRow[`${p}_receita_ng`]    = pivotData.reduce((s, r) => s + (r[`${p}_receita_ng`]    || 0), 0);
      totRow[`${p}_receita_eco`]   = pivotData.reduce((s, r) => s + (r[`${p}_receita_eco`]   || 0), 0);
      totRow[`${p}_custo_ng`]      = pivotData.reduce((s, r) => s + (r[`${p}_custo_ng`]      || 0), 0);
      totRow[`${p}_custo_outro`]   = pivotData.reduce((s, r) => s + (r[`${p}_custo_outro`]   || 0), 0);
    });
    return [totRow, ...pivotData.map((d, i) => ({ ...d, key: i }))];
  }, [pivotData, periodos, totReceita, totCusto, totVL, totHoras]);

  const columnsDef = useMemo(() => {
    type MetricKey = "receita" | "custo" | "despesa" | "custo_despesa" | "custo_fonte" | "margem" | "margem_pct" | "valor_liquido" | "horas";
    // Mapeia métrica do frontend → métrica que o backend entende como filtro
    const metricApiKey: Record<string, string> = {
      // valor_liquido (coluna Lucro Bruto) NAO filtra pela coluna crua valor_liquido:
      // o Lucro Bruto exibido e receita+custo — o drill mostra todas as linhas do grupo.
      receita: "receita", custo: "custo_rateado", despesa: "despesa", custo_despesa: "", custo_fonte: "", margem: "",
      valor_liquido: "", horas: "horas", margem_pct: "",
    };
    const metricLabelMap: Record<string, string> = {
      receita: "Receita", custo: "Custo Rateado", despesa: "Despesa", custo_despesa: "Custo + Despesa", custo_fonte: "Custo na Fonte", margem: "Margem",
      valor_liquido: "Lucro Bruto", horas: "Horas", margem_pct: "Margem %",
    };
    const clickable = (prefix: string, metric: MetricKey, content: React.ReactNode, row: any, v: any) => (
      <span
        style={{ cursor: row?._isTotal ? "default" : "pointer", borderBottom: row?._isTotal ? "none" : "1px dashed transparent" }}
        onClick={(e) => {
          if (row?._isTotal) return;
          if (!v && v !== 0) return;
          e.stopPropagation();
          openDrill(row.grupo, prefix, metricApiKey[metric] || "", metricLabelMap[metric]);
        }}
        onMouseEnter={(e) => { if (!row?._isTotal) (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed #6b7fa3"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderBottom = "1px dashed transparent"; }}
      >
        {content}
      </span>
    );
    const colDef = (prefix: string, metric: MetricKey, bold: boolean) => {
      const isHoras = metric === "horas";
      return {
        dataIndex: `${prefix}_${metric}`,
        key: `${prefix}_${metric}`,
        align: "right" as const,
        sorter: (a: any, b: any) =>
          (Number(a[`${prefix}_${metric}`]) || 0) - (Number(b[`${prefix}_${metric}`]) || 0),
        render: (v: number, row: any) => clickable(prefix, metric, (
          <span style={{ fontWeight: bold ? 700 : 500, color: isHoras ? theme.text : (v || 0) < 0 ? "#c0392b" : theme.text }}>
            {isHoras
              ? (v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })
              : brl(v || 0)}
          </span>
        ), row, v),
      };
    };

    const metricChildDefs: { metric: MetricKey; title: string; width: number; renderFn?: string }[] = [
      { metric: "receita",       title: "Receita",    width: 140 },
      { metric: "custo",         title: "Custo",      width: 130 },
      { metric: "despesa",       title: "Despesa",    width: 130 },
      { metric: "custo_despesa", title: "Custo + Despesa", width: 150 },
      { metric: "custo_fonte",   title: "Custo na Fonte", width: 150 },
      { metric: "margem",        title: "Margem",     width: 130 },
      { metric: "margem_pct",    title: "%",          width: 75, renderFn: "pct" },
      { metric: "valor_liquido", title: "Lucro Bruto", width: 130 },
      { metric: "horas",         title: "Horas",      width: 90  },
    ];

    const children = (prefix: string, bold: boolean) =>
      metricChildDefs
        .filter(m => visibleMetrics.has(m.metric))
        .map(m => {
          if (m.renderFn === "pct") {
            return {
              dataIndex: `${prefix}_${m.metric}`,
              key: `${prefix}_${m.metric}`,
              title: m.title, width: m.width,
              align: "right" as const,
              sorter: (a: any, b: any) => (Number(a[`${prefix}_${m.metric}`]) || 0) - (Number(b[`${prefix}_${m.metric}`]) || 0),
              render: (v: any) => <MargemTag value={v} />,
            };
          }
          const col = colDef(prefix, m.metric as any, bold);
          if (m.metric === "margem") {
            return { ...col, title: m.title, width: m.width,
              render: (v: number, row: any) => {
                const rng = row[`${prefix}_receita_ng`]  || 0;
                const cng = row[`${prefix}_custo_ng`]    || 0;
                const cou = row[`${prefix}_custo_outro`] || 0;
                const eco = row[`${prefix}_receita_eco`] || 0;
                return (
                  <Popover trigger="click" placement="left" title="Margem Bruta — composição"
                    content={
                      <div style={{ minWidth: 250, fontSize: "0.85rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}><span>Receita NG</span><strong>{brl(rng)}</strong></div>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}><span>Custo NG</span><strong style={{ color: "#c0392b" }}>{brl(cng)}</strong></div>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}><span>Custo Outro</span><strong style={{ color: "#c0392b" }}>{brl(cou)}</strong></div>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}><span>Receita Eco × 33,3%</span><strong>{brl(eco * 0.333)}</strong></div>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, borderTop: "1px solid #dde3f0", marginTop: 6, paddingTop: 6 }}>
                          <span style={{ fontWeight: 700 }}>Margem Bruta</span>
                          <strong style={{ color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e" }}>{brl(v || 0)}</strong>
                        </div>
                        <div style={{ marginTop: 8, background: "#fff3cd", color: "#856404", borderRadius: 6, padding: "6px 8px", fontSize: "0.78rem" }}>
                          Margem de Ecossistema é fixada em <strong>33,3%</strong> da receita — o custo real de Eco não entra nesta conta.
                        </div>
                      </div>
                    }
                  >
                    <span style={{ cursor: "pointer", fontWeight: bold ? 700 : 600, color: (v || 0) < 0 ? "#c0392b" : "#0a7a3e", borderBottom: "1px dashed #6b7fa3" }}>
                      {brl(v || 0)}
                    </span>
                  </Popover>
                );
              },
            };
          }
          return { ...col, title: m.title, width: m.width };
        });

    const periodoCols = periodos.map(p => ({
      title: periodoLabel ? periodoLabel(p) : p,
      key: p,
      children: children(p, false),
    }));

    return [
      {
        title: AGRUPAR_LABELS[agruparPor] ?? "Grupo",
        dataIndex: "grupo", key: "grupo", width: 170, fixed: "left" as const,
        sorter: (a: any, b: any) => String(a.grupo).localeCompare(String(b.grupo), "pt-BR"),
      },
      ...periodoCols,
      {
        title: "Total",
        key: "__total__",
        children: children("total", true),
      },
    ];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodos, visibleMetrics, agruparPor, selPeriodos, selEmpresas, selFontes]);

  const opt = (arr: string[]) => [
    ...arr.map(v => ({ label: v, value: v })),
    { label: "(Vazio)", value: "__blank__" },
  ];
  const hasActiveFilter = selPeriodos.length > 0 || selEmpresas.length > 0 || selFontes.length > 0 || selApuracoes.length > 0 || selNoHier.length > 0;

  return (
    <div>
      {/* Filter bar */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Button
          icon={<FilterOutlined />}
          onClick={() => setShowFilters(v => !v)}
          type={ctxHasFilter ? "primary" : "default"}
          style={{ marginLeft: "auto" }}
        >
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
        {ctxHasFilter && (
          <Button onClick={resetFilters} danger>
            Limpar Filtros
          </Button>
        )}
      </div>

      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Período</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
              onChange={setSelPeriodos} options={opt(filters.periodos ?? [])}
              maxTagCount="responsive" placeholder="Todos" allowClear disabled={periodoLocked} />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
              onChange={setSelEmpresas} options={opt(filters.empresas ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Fonte</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selFontes}
              onChange={setSelFontes} options={opt(filters.fontes ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 130 }}>
            <div style={labelStyle}>Apuração</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selApuracoes}
              onChange={setSelApuracoes} options={opt(filters.apuracoes ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Centro de Lucro</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selNoHier}
              onChange={setSelNoHier} options={opt(filters.no_hierarquias ?? [])}
              maxTagCount="responsive" placeholder="Todos" allowClear />
          </div>
        </div>
      )}

      {/* KPI cards */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        {[
          { label: "Receita Total",   value: brl(totReceita), color: theme.text },
          { label: "Custo Total",     value: brl(totCusto),   color: totCusto   < 0 ? "#c0392b" : theme.text },
          { label: "Margem Bruta", value: brl(totMargem), color: totMargem < 0 ? "#c0392b" : "#0a7a3e" },
          { label: "Margem %",        value: `${(totPct * 100).toFixed(1)}%`, color: totPct < 0.1 ? "#c0392b" : totPct < 0.3 ? "#856404" : "#0a7a3e" },
          { label: "MC", value: brl(totMC), color: totMC < 0 ? "#c0392b" : "#0a7a3e" },
          { label: "MC %", value: `${(totMCPct * 100).toFixed(1)}%`, color: totMCPct < 0.1 ? "#c0392b" : totMCPct < 0.3 ? "#856404" : "#0a7a3e" },
        ].map(k => (
          <Card key={k.label}
            style={{ flex: 1, minWidth: 160, borderRadius: 10, border: "1px solid #dde3f0", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}
            styles={{ body: { padding: "1rem 1.2rem", textAlign: "center" } }}
          >
            <Statistic
              title={<span style={{ color: "#6b7fa3", fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{k.label}</span>}
              value={k.value}
              valueStyle={{ color: k.color, fontSize: "1.1rem", fontWeight: 700 }}
            />
          </Card>
        ))}
      </div>

      {loading ? <TableSkeleton rows={8} /> : error ? (
        <div style={{ background: "#fff1f0", border: "1px solid #ffa39e", borderRadius: 8, padding: "1rem 1.2rem", color: "#cf1322" }}>
          <strong>Erro ao carregar dados:</strong> {error}
        </div>
      ) : (
        <Table
          dataSource={tableData}
          columns={columnsDef}
          rowKey="key"
          size="small"
          pagination={false}
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={row => ({ style: row._isTotal ? { background: "#dce6f7", fontWeight: 700 } : {} })}
          title={() => (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 6, padding: "0 0 4px" }}>
              <span style={{ color: "#6b7fa3", fontSize: "0.75rem", marginRight: 2, lineHeight: "24px" }}>Métricas:</span>
              <Popover trigger="click" placement="bottomRight" title="Métricas visíveis"
                content={
                  <div style={{ minWidth: 140 }}>
                    {ALL_METRICS.map(m => (
                      <div key={m} style={{ padding: "3px 0" }}>
                        <Checkbox checked={visibleMetrics.has(m)} onChange={() => toggleMetric(m)}>
                          {METRIC_LABELS[m]}
                        </Checkbox>
                      </div>
                    ))}
                  </div>
                }
              >
                <Button icon={<SettingOutlined />} size="small" type="text" style={{ color: "#6b7fa3" }} />
              </Popover>
              <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                onClick={() => exportTableToExcel(columnsDef, pivotData, "nb_resumo")}>Excel</Button>
            </div>
          )}
        />
      )}
      <DetalheCelulaModal
        open={drillOpen}
        onClose={() => setDrillOpen(false)}
        filters={drillFilters}
        titulo={drillTitulo}
        metricLabel={drillMetric}
      />
    </div>
  );
}

// ── DRE Nova Base 2026 ─────────────────────────────────────────────────────────

export function NovaDreTab() {
  const [filters, setFilters]         = useState<any>({});
  const {
    selPeriodos, setSelPeriodos,
    selEmpresas, setSelEmpresas,
    selFontes, setSelFontes,
    selApuracoes, setSelApuracoes,
    selNoHier, setSelNoHier,
    selVerticais,
    resetFilters, hasAnyFilter: ctxHasFilter2,
    lockedVertical, periodoLocked,
  } = useNovaBaseFilters();
  const [data, setData]               = useState<any>(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [filtersReady, setFiltersReady] = useState(false);
  const initialLoad = useRef(true);

  // Carga inicial: filtros primeiro, depois DRE (evita carga dupla do Excel no cold start)
  const loadInitial = useCallback(() => {
    setLoading(true); setError(null);
    const initialParams: Record<string, string> = {};
    if (lockedVertical) initialParams.verticais = lockedVertical;
    getNovaBaseFilters()
      .then(f => { setFilters(f); return getNovaBaseDre(initialParams); })
      .then(d => { setData(d); setFiltersReady(true); initialLoad.current = false; })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lockedVertical]);

  useEffect(() => { loadInitial(); }, [loadInitial]);

  // Recarrega quando o usuário muda filtros (não na carga inicial)
  useEffect(() => {
    if (!filtersReady || initialLoad.current) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length)  params.periodos       = selPeriodos.join(",");
    if (selEmpresas.length)  params.empresas       = selEmpresas.join(",");
    if (selFontes.length)    params.fontes         = selFontes.join(",");
    if (selApuracoes.length) params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)    params.no_hierarquias = selNoHier.join(",");
    if (selVerticais.length) params.verticais      = selVerticais.join(",");
    getNovaBaseDre(params)
      .then(d => { setData(d); setError(null); })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selPeriodos, selEmpresas, selFontes, selApuracoes, selNoHier, selVerticais]);

  const opt = (arr: string[]) => [
    ...arr.map((v: string) => ({ label: v, value: v })),
    { label: "(Vazio)", value: "__blank__" },
  ];
  const hasActiveFilter = selPeriodos.length > 0 || selEmpresas.length > 0 || selFontes.length > 0 || selApuracoes.length > 0 || selNoHier.length > 0;

  const columns: string[] = useMemo(() => {
    if (!data?.columns) return [];
    return data.columns.map((c: string) =>
      c === "Total" ? "Total" : (periodoLabel ? periodoLabel(c) : c)
    );
  }, [data]);

  const rows = useMemo(() => {
    if (!data?.rows) return [];
    return data.rows.map((r: any) => {
      const renamedValues: Record<string, number> = {};
      (data.columns as string[]).forEach((raw: string, i: number) => {
        renamedValues[columns[i]] = r.values[raw] ?? 0;
      });
      return { ...r, values: renamedValues };
    });
  }, [data, columns]);

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={ctxHasFilter2 ? "primary" : "default"}
          style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
        {ctxHasFilter2 && (
          <Button onClick={resetFilters} danger>
            Limpar Filtros
          </Button>
        )}
      </div>

      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Período</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
              onChange={setSelPeriodos} options={opt(filters.periodos ?? [])}
              maxTagCount="responsive" placeholder="Todos" allowClear disabled={periodoLocked} />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
              onChange={setSelEmpresas} options={opt(filters.empresas ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Fonte</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selFontes}
              onChange={setSelFontes} options={opt(filters.fontes ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 130 }}>
            <div style={labelStyle}>Apuração</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selApuracoes}
              onChange={setSelApuracoes} options={opt(filters.apuracoes ?? [])}
              maxTagCount="responsive" placeholder="Todas" allowClear />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div style={labelStyle}>Centro de Lucro</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selNoHier}
              onChange={setSelNoHier} options={opt(filters.no_hierarquias ?? [])}
              maxTagCount="responsive" placeholder="Todos" allowClear />
          </div>
        </div>
      )}

      {loading ? (
        <div>
          <TableSkeleton rows={12} />
          <WarmUpNotice />
        </div>
      ) : error ? (
        <ErrorState onRetry={loadInitial} message="Não foi possível carregar o DRE. O servidor pode estar acordando — tente novamente." />
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
            <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
              onClick={() => exportPLTableToExcel(data?.rows || [], data?.columns || [], "nova_base_dre")}>
              Excel
            </Button>
          </div>
          <PLTable rows={rows} columns={columns} />
        </>
      )}
    </div>
  );
}

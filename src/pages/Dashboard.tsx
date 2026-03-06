import React, { useEffect, useState, useCallback } from "react";
import { getCompetencias, getKPIs, getMetricas, getMensal, logout } from "../api";
import { KPIs, Metrica, Mensal, PathItem, LEVELS, LEVEL_LABELS } from "../types";
import KPICard from "../components/KPICard";
import MetricTable from "../components/MetricTable";
import MonthlySection from "../components/MonthlySection";

export default function Dashboard() {
  const [competencias, setCompetencias] = useState<string[]>([]);
  const [selComp, setSelComp] = useState<string[]>([]);
  const [path, setPath] = useState<PathItem[]>([]);
  const [kpis, setKPIs] = useState<KPIs | null>(null);
  const [metricas, setMetricas] = useState<Metrica[]>([]);
  const [mensal, setMensal] = useState<Mensal[]>([]);
  const [loading, setLoading] = useState(true);

  const currentIdx = path.length;
  const currentLevel = LEVELS[currentIdx] || null;

  function buildParams() {
    const params: Record<string, string> = {};
    if (selComp.length) params.competencias = selComp.join(",");
    path.forEach(p => { params[p.level] = p.value; });
    return params;
  }

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = buildParams();
      const [k, m] = await Promise.all([getKPIs(params), getMensal(params)]);
      setKPIs(k);
      setMensal(m);
      if (currentLevel) {
        const met = await getMetricas(currentLevel, params);
        setMetricas(met);
      }
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selComp, path]);

  useEffect(() => {
    getCompetencias().then(c => { setCompetencias(c); setSelComp(c); });
  }, []);

  useEffect(() => {
    if (selComp.length > 0 || competencias.length === 0) fetchData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selComp, path]);

  function handleDrillDown(row: Metrica) {
    if (!currentLevel) return;
    const rawValue = String(row[currentLevel]);
    setPath(prev => [...prev, { level: currentLevel, value: rawValue, label: row.nome }]);
  }

  function navigateTo(idx: number) {
    setPath(prev => prev.slice(0, idx + 1));
  }

  function toggleComp(c: string) {
    setSelComp(prev =>
      prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]
    );
  }

  function selectAll() { setSelComp(competencias); }
  function clearAll() { setSelComp([]); }

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.h1}>👷 Worker Dashboard</h1>
          <p style={styles.subtitle}>Receita, Custo e Margem por hierarquia de alocação</p>
        </div>
        <button onClick={logout} style={styles.logoutBtn}>Sair</button>
      </div>

      {/* Filtro Competência */}
      <div style={styles.filterBox}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span style={styles.filterLabel}>Competência:</span>
          <button onClick={selectAll} style={styles.linkBtn}>Todas</button>
          <button onClick={clearAll} style={styles.linkBtn}>Nenhuma</button>
          {competencias.map(c => (
            <label key={c} style={styles.checkLabel}>
              <input type="checkbox" checked={selComp.includes(c)} onChange={() => toggleComp(c)} />
              {" "}{c}
            </label>
          ))}
        </div>
      </div>

      {/* Breadcrumb */}
      <div style={styles.breadcrumb}>
        <span
          style={{ ...styles.crumb, color: path.length === 0 ? "#2d50a0" : "#6b7fa3", cursor: path.length > 0 ? "pointer" : "default", fontWeight: path.length === 0 ? 700 : 400 }}
          onClick={() => setPath([])}
        >Início</span>
        {path.map((p, i) => (
          <React.Fragment key={i}>
            <span style={styles.sep}>›</span>
            <span
              style={{ ...styles.crumb, color: i === path.length - 1 ? "#2d50a0" : "#6b7fa3",
                       cursor: i < path.length - 1 ? "pointer" : "default",
                       fontWeight: i === path.length - 1 ? 700 : 400 }}
              onClick={() => i < path.length - 1 && navigateTo(i)}
            >
              {LEVEL_LABELS[p.level]}: {p.label}
            </span>
          </React.Fragment>
        ))}
      </div>

      {/* KPI Cards */}
      {kpis && (
        <div style={styles.kpiRow}>
          <KPICard label="Receita Bruta"  value={kpis.receita_bruta} />
          <KPICard label="Receita Líquida" value={kpis.receita_liquida} />
          <KPICard label="Custo"          value={kpis.custo} />
          <KPICard label="Lucro Bruto"    value={kpis.lucro_bruto} />
          <KPICard label="Margem Bruta"   value={kpis.margem_bruta} format="pct" />
        </div>
      )}

      <div style={{ height: 24 }} />

      {/* Comparativo Mensal */}
      <p style={styles.sectionTitle}>Comparativo por Competência</p>
      {loading ? <p style={styles.loading}>Carregando...</p> : <MonthlySection data={mensal} />}

      <div style={{ height: 24 }} />

      {/* Tabela drill-down */}
      {currentLevel && (
        <>
          <p style={styles.sectionTitle}>Visão por {LEVEL_LABELS[currentLevel]}</p>
          {loading ? <p style={styles.loading}>Carregando...</p> : (
            <MetricTable
              data={metricas}
              levelKey={currentLevel}
              onSelect={currentIdx + 1 < LEVELS.length ? handleDrillDown : undefined}
            />
          )}
        </>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#f4f6fb", padding: "2rem 2.5rem", fontFamily: "'Segoe UI', sans-serif" },
  header: { background: "#fff", border: "1px solid #dde3f0", borderLeft: "5px solid #2d50a0", borderRadius: 10, padding: "1.2rem 1.8rem", marginBottom: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.05)", display: "flex", justifyContent: "space-between", alignItems: "center" },
  h1: { color: "#1a2e5a", fontSize: "1.5rem", fontWeight: 700, margin: 0 },
  subtitle: { color: "#6b7fa3", fontSize: "0.85rem", margin: "4px 0 0 0" },
  logoutBtn: { background: "none", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.4rem 1rem", color: "#6b7fa3", cursor: "pointer", fontSize: "0.85rem" },
  filterBox: { background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.04)" },
  filterLabel: { color: "#1a2e5a", fontWeight: 600, fontSize: "0.85rem" },
  linkBtn: { background: "none", border: "none", color: "#2d50a0", cursor: "pointer", fontSize: "0.85rem", padding: "0 4px", textDecoration: "underline" },
  checkLabel: { fontSize: "0.85rem", color: "#1a2e5a", cursor: "pointer", display: "flex", alignItems: "center", gap: 4 },
  breadcrumb: { background: "#fff", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 20, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" },
  crumb: { fontSize: "0.88rem" },
  sep: { color: "#aab4cc", fontSize: "0.9rem" },
  kpiRow: { display: "flex", gap: 16, flexWrap: "wrap" },
  sectionTitle: { fontSize: "1rem", fontWeight: 600, color: "#1a2e5a", borderBottom: "2px solid #2d50a0", display: "inline-block", paddingBottom: 4, marginBottom: 14 },
  loading: { color: "#6b7fa3", fontSize: "0.9rem" },
};

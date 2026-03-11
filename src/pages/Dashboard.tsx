import React, { useEffect, useState, useCallback } from "react";
import { Layout, Breadcrumb, Button, Checkbox, Space, Typography, Divider, Spin, ConfigProvider, Tabs, Card } from "antd";
import { HomeOutlined, LogoutOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { getCompetencias, getKPIs, getMetricas, getMensal, logout } from "../api";
import { KPIs, Metrica, Mensal, PathItem, LEVELS, LEVEL_LABELS } from "../types";
import KPICard from "../components/KPICard";
import MetricTable from "../components/MetricTable";
import MonthlySection from "../components/MonthlySection";
import SapTab from "./SapTab";
import { DreTab, StreamsTab, MatricialTab } from "./CockpitTabs";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

function WorkerTab() {
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

  function toggleComp(c: string) {
    setSelComp(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]);
  }

  const breadcrumbItems = [
    {
      title: (
        <span style={{ cursor: "pointer", color: "#2d50a0" }} onClick={() => setPath([])}>
          <HomeOutlined /> Início
        </span>
      ),
    },
    ...path.map((p, i) => ({
      title: (
        <span
          style={{ cursor: i < path.length - 1 ? "pointer" : "default",
                   color: i === path.length - 1 ? "#1a2e5a" : "#2d50a0",
                   fontWeight: i === path.length - 1 ? 600 : 400 }}
          onClick={() => i < path.length - 1 && setPath(prev => prev.slice(0, i + 1))}
        >
          {LEVEL_LABELS[p.level]}: {p.label}
        </span>
      ),
    })),
  ];

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
        <Space wrap>
          <Text strong style={{ color: "#1a2e5a" }}>Competência:</Text>
          <Button size="small" type="link" onClick={() => setSelComp(competencias)}>Todas</Button>
          <Button size="small" type="link" onClick={() => setSelComp([])}>Nenhuma</Button>
          <Divider type="vertical" />
          {competencias.map(c => (
            <Checkbox key={c} checked={selComp.includes(c)} onChange={() => toggleComp(c)}>{c}</Checkbox>
          ))}
        </Space>
      </div>

      <Breadcrumb items={breadcrumbItems} style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 20 }} />

      {kpis && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 24 }}>
          <KPICard label="Receita Bruta"   value={kpis.receita_bruta} />
          <KPICard label="Receita Líquida" value={kpis.receita_liquida} />
          <KPICard label="Custo"           value={kpis.custo} />
          <KPICard label="Lucro Bruto"     value={kpis.lucro_bruto} />
          <KPICard label="Margem Bruta"    value={kpis.margem_bruta} format="pct" />
        </div>
      )}

      <Title level={5} style={{ color: "#1a2e5a", borderBottom: "2px solid #2d50a0", paddingBottom: 4, display: "inline-block", marginBottom: 16 }}>
        Comparativo por Competência
      </Title>
      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : <MonthlySection data={mensal} />}

      <div style={{ height: 28 }} />

      {currentLevel && (
        <>
          <Title level={5} style={{ color: "#1a2e5a", borderBottom: "2px solid #2d50a0", paddingBottom: 4, display: "inline-block", marginBottom: 16 }}>
            Visão por {LEVEL_LABELS[currentLevel]}
          </Title>
          {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
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

type Section = "worker" | "cockpit" | "metas" | null;

export default function Dashboard() {
  const [section, setSection] = useState<Section>(null);

  return (
    <ConfigProvider theme={{ token: { colorPrimary: "#2d50a0", borderRadius: 8 } }}>
      <Layout style={{ minHeight: "100vh", background: "#f4f6fb" }}>
        <Header style={{ background: "#fff", borderBottom: "1px solid #dde3f0", padding: "0 2rem", height: "auto", lineHeight: "normal", display: "flex", alignItems: "center", justifyContent: "space-between", boxShadow: "0 2px 8px rgba(0,0,0,0.05)", paddingTop: "0.8rem", paddingBottom: "0.8rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {section && (
              <Button icon={<ArrowLeftOutlined />} type="text" style={{ color: "#2d50a0" }} onClick={() => setSection(null)} />
            )}
            <span style={{ fontSize: 28 }}>📊</span>
            <div>
              <Title level={4} style={{ margin: 0, color: "#1a2e5a" }}>Cockpit FP&A</Title>
              <Text type="secondary" style={{ fontSize: "0.8rem" }}>Visualização gerencial de resultados financeiros</Text>
            </div>
          </div>
          <Button icon={<LogoutOutlined />} onClick={logout} type="text" style={{ color: "#6b7fa3" }}>
            Sair
          </Button>
        </Header>

        <Content style={{ padding: "1.5rem 2rem" }}>
          {section === null && (
            <div style={{ display: "flex", gap: 32, justifyContent: "center", alignItems: "center", minHeight: "60vh" }}>
              <Card
                hoverable
                onClick={() => setSection("worker")}
                style={{ width: 280, textAlign: "center", border: "2px solid #dde3f0", cursor: "pointer" }}
                styles={{ body: { padding: "2.5rem 2rem" } }}
              >
                <div style={{ fontSize: 52, marginBottom: 16 }}>👷</div>
                <Title level={4} style={{ color: "#1a2e5a", marginBottom: 8 }}>Worker</Title>
                <Text type="secondary">Base Worker, receitas e custos por colaborador</Text>
              </Card>

              <Card
                hoverable
                onClick={() => setSection("cockpit")}
                style={{ width: 280, textAlign: "center", border: "2px solid #dde3f0", cursor: "pointer" }}
                styles={{ body: { padding: "2.5rem 2rem" } }}
              >
                <div style={{ fontSize: 52, marginBottom: 16 }}>🏢</div>
                <Title level={4} style={{ color: "#1a2e5a", marginBottom: 8 }}>Financeiro</Title>
                <Text type="secondary">DRE, P&L por Stream, Matricial e Base SAP S4</Text>
              </Card>

              <Card
                hoverable
                onClick={() => setSection("metas")}
                style={{ width: 280, textAlign: "center", border: "2px solid #dde3f0", cursor: "pointer" }}
                styles={{ body: { padding: "2.5rem 2rem" } }}
              >
                <div style={{ fontSize: 52, marginBottom: 16 }}>🎯</div>
                <Title level={4} style={{ color: "#1a2e5a", marginBottom: 8 }}>Apuração de Metas</Title>
                <Text type="secondary">Acompanhamento e apuração de metas</Text>
              </Card>
            </div>
          )}

          {section === "worker" && (
            <Tabs
              defaultActiveKey="worker"
              type="card"
              size="large"
              items={[
                { key: "worker", label: "👷 Worker", children: <WorkerTab /> },
              ]}
            />
          )}

          {section === "metas" && (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "40vh" }}>
              <Text type="secondary" style={{ fontSize: "1.1rem" }}>Em construção 🚧</Text>
            </div>
          )}

          {section === "cockpit" && (
            <Tabs
              defaultActiveKey="dre"
              type="card"
              size="large"
              items={[
                { key: "dre",       label: "🏢 DRE por Empresa", children: <DreTab /> },
                { key: "streams",   label: "🌊 P&L por Stream",  children: <StreamsTab /> },
                { key: "matricial", label: "📐 P&L Matricial",   children: <MatricialTab /> },
                { key: "sap",       label: "📋 Base SAP S4",     children: <SapTab /> },
              ]}
            />
          )}
        </Content>
      </Layout>

      <style>{`
        .total-row td { background-color: #dce6f7 !important; font-weight: 700; }
        .subtotal-row td { background-color: #dce6f7 !important; font-weight: 700; }
        .ant-table-thead > tr > th { background: #2d50a0 !important; color: #fff !important; font-weight: 600; }
        .ant-table-row:hover > td { background: #f0f4ff !important; }
        .ant-tabs-card > .ant-tabs-nav .ant-tabs-tab-active { background: #2d50a0 !important; border-color: #2d50a0 !important; }
        .ant-tabs-card > .ant-tabs-nav .ant-tabs-tab-active .ant-tabs-tab-btn { color: #fff !important; }
      `}</style>
    </ConfigProvider>
  );
}

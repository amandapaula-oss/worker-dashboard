import React, { useEffect, useState, useCallback } from "react";
import { Layout, Breadcrumb, Button, Checkbox, Space, Typography, Divider, ConfigProvider, Tabs, Switch, theme as antdTheme, Upload, Modal } from "antd";
import TableSkeleton from "../components/TableSkeleton";
import { HomeOutlined, LogoutOutlined, ArrowLeftOutlined, AimOutlined, FileTextOutlined, FundOutlined, AuditOutlined, TeamOutlined, DatabaseOutlined, HeatMapOutlined, BankOutlined, SlidersOutlined, UserOutlined, MoonOutlined, SunOutlined, ApartmentOutlined, UploadOutlined, TableOutlined, InboxOutlined, ClusterOutlined, MedicineBoxOutlined, ShoppingCartOutlined, TruckOutlined, GlobalOutlined, RocketOutlined, FolderOpenOutlined } from "@ant-design/icons";
import { getCompetencias, getKPIs, getMetricas, getMensal, logout } from "../api";
import { KPIs, Metrica, Mensal, PathItem, LEVELS, LEVEL_LABELS } from "../types";
import KPICard from "../components/KPICard";
import MetricTable from "../components/MetricTable";
import MonthlySection from "../components/MonthlySection";
import SapTab from "./SapTab";
import { theme, darkTheme, lightTheme } from "../theme";
import { NovaBaseFiltersProvider } from "../contexts/NovaBaseFilters";
import { MeProvider, useMe } from "../contexts/Me";
import { DreTab, StreamsTab, MatricialTab } from "./CockpitTabs";
import MargemTab from "./MargemTab";
import CheckLucasTab from "./CheckLucasTab";
import VistaMasterTab, { VistaMasterTabQ3 } from "./VistaMasterTab";
import ResumoTab from "./ResumoTab";
import ClientesTab from "./ClientesTab";
import NovaBaseTab from "./NovaBaseTab";
import NovaBaseResumoTab, { NovaDreTab } from "./NovaBaseResumoTab";
import NovaBaseMargemTab from "./NovaBaseMargemTab";
import NovaBasePivotTab from "./NovaBasePivotTab";
import BudgetVsRealizadoTab from "./BudgetVsRealizadoTab";
import WorkersTab from "./WorkersTab";
import AdminTab from "./AdminTab";
import { uploadNovaBase, clearNovaBaseCache } from "../api";
import { ReloadOutlined, SafetyCertificateOutlined } from "@ant-design/icons";

function NovaBaseUploadButton() {
  const [uploading, setUploading] = React.useState(false);
  const handleUpload = (file: File) => {
    Modal.confirm({
      title: "Substituir dados da Nova Base?",
      content: `Arquivo: ${file.name}. Todos os dados atuais serão substituídos.`,
      okText: "Sim, substituir",
      cancelText: "Cancelar",
      onOk: async () => {
        setUploading(true);
        try {
          const r = await uploadNovaBase(file);
          Modal.success({ title: "Upload concluído", content: `${r.rows_inserted} linhas inseridas.` });
          setTimeout(() => window.location.reload(), 1500);
        } catch (e: any) {
          Modal.error({ title: "Erro no upload", content: e.message });
        } finally {
          setUploading(false);
        }
      },
    });
    return false;
  };
  const [clearing, setClearing] = React.useState(false);
  const handleClearCache = async () => {
    setClearing(true);
    try {
      await clearNovaBaseCache();
      Modal.success({ title: "Cache limpo", content: "Dados serão recarregados do Supabase." });
      setTimeout(() => window.location.reload(), 1000);
    } catch (e: any) {
      Modal.error({ title: "Erro", content: e.message });
    } finally {
      setClearing(false);
    }
  };
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 8 }}>
      <Button icon={<ReloadOutlined />} loading={clearing} onClick={handleClearCache} size="small">
        Atualizar Dados
      </Button>
    </div>
  );
}

const { Header, Content } = Layout;
const { Title, Text } = Typography;

function WorkerTab({ dark }: { dark: boolean }) {
  const t = dark ? darkTheme : lightTheme;
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
        <span style={{ cursor: "pointer", color: t.link }} onClick={() => setPath([])}>
          <HomeOutlined /> Início
        </span>
      ),
    },
    ...path.map((p, i) => ({
      title: (
        <span
          style={{ cursor: i < path.length - 1 ? "pointer" : "default",
                   color: i === path.length - 1 ? t.text : t.link,
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
      <div style={{ background: t.cardBg, border: `1px solid ${t.border}`, borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
        <Space wrap>
          <Text strong style={{ color: t.text }}>Competência:</Text>
          <Button size="small" type="link" onClick={() => setSelComp(competencias)}>Todas</Button>
          <Button size="small" type="link" onClick={() => setSelComp([])}>Nenhuma</Button>
          <Divider type="vertical" />
          {competencias.map(c => (
            <Checkbox key={c} checked={selComp.includes(c)} onChange={() => toggleComp(c)}>{c}</Checkbox>
          ))}
        </Space>
      </div>

      <Breadcrumb items={breadcrumbItems} style={{ background: t.cardBg, border: `1px solid ${t.border}`, borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 20 }} />

      {kpis && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 24 }}>
          <KPICard label="Receita Bruta"   value={kpis.receita_bruta} />
          <KPICard label="Receita Líquida" value={kpis.receita_liquida} />
          <KPICard label="Custo"           value={kpis.custo} />
          <KPICard label="Lucro Bruto"     value={kpis.lucro_bruto} />
          <KPICard label="Margem Bruta"    value={kpis.margem_bruta} format="pct" />
        </div>
      )}

      <Title level={5} style={{ color: t.text, borderBottom: `2px solid ${theme.accent}`, paddingBottom: 4, display: "inline-block", marginBottom: 16 }}>
        Comparativo por Competência
      </Title>
      {loading ? <TableSkeleton rows={6} /> : <MonthlySection data={mensal} />}

      <div style={{ height: 28 }} />

      {currentLevel && (
        <>
          <Title level={5} style={{ color: t.text, borderBottom: `2px solid ${theme.accent}`, paddingBottom: 4, display: "inline-block", marginBottom: 16 }}>
            Visão por {LEVEL_LABELS[currentLevel]}
          </Title>
          {loading ? <TableSkeleton rows={8} /> : (
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

type Section = "worker" | "cockpit" | "metas" | "nova_base" | "nova_base_pivot" | "budget" | "bus" | "admin" | "obsoleto" | null;

const BU_LABEL: Record<string, string> = {
  "BU Finance":     "Finance",
  "BU Health":      "Health",
  "BU Multisector": "Multisector",
  "BU Retail":      "Retail",
  "BU Logistics":   "Logistics (Grupo Mult)",
};

const BU_ICON: Record<string, React.ReactNode> = {
  "BU Finance":     <BankOutlined />,
  "BU Health":      <MedicineBoxOutlined />,
  "BU Multisector": <GlobalOutlined />,
  "BU Retail":      <ShoppingCartOutlined />,
  "BU Logistics":   <TruckOutlined />,
  "BU Hyper":       <RocketOutlined />,
  "BU Others":      <FolderOpenOutlined />,
};

function BUTabs({ bu }: { bu: string }) {
  return (
    <NovaBaseFiltersProvider lockedVertical={bu}>
      <Tabs
        defaultActiveKey="resumoEmp"
        type="card"
        size="large"
        items={[
          { key: "resumoEmp", label: <span><FileTextOutlined /> Resumo por Empresa</span>, children: <NovaBaseResumoTab agruparPor="empresa" /> },
          { key: "margemCli", label: <span><FundOutlined /> Margem por Cliente</span>,   children: <NovaBaseMargemTab /> },
          { key: "empresa",   label: <span><BankOutlined /> DRE</span>,                   children: <NovaDreTab /> },
          { key: "fonte",     label: <span><HeatMapOutlined /> PJ/CLT</span>,             children: <NovaBaseResumoTab agruparPor="tipo_pessoa" /> },
          { key: "apuracao",  label: <span><AimOutlined /> Apuração</span>,               children: <NovaBaseResumoTab agruparPor="apuracao" /> },
          { key: "workers",   label: <span><TeamOutlined /> Workers</span>,                children: <WorkersTab /> },
          { key: "base",      label: <span><DatabaseOutlined /> Base Detalhada</span>,    children: <NovaBaseTab /> },
        ]}
      />
    </NovaBaseFiltersProvider>
  );
}

export default function Dashboard() {
  return (
    <MeProvider>
      <DashboardInner />
    </MeProvider>
  );
}

function DashboardInner() {
  const [section, setSection] = useState<Section>(null);
  const [selectedBu, setSelectedBu] = useState<string | null>(null);
  const me = useMe();
  const [apenasAtribuidos, setApenasAtribuidos] = useState(false);
  const [dark, setDark] = useState<boolean>(() => localStorage.getItem("darkMode") === "true");

  // Guarda: se a senha é temporária, força fluxo de troca via login.
  useEffect(() => {
    if (me?.must_change_password) {
      localStorage.removeItem("token");
      localStorage.removeItem("me");
      window.location.href = "/login";
    }
  }, [me?.must_change_password]);

  useEffect(() => {
    localStorage.setItem("darkMode", String(dark));
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    document.body.setAttribute("data-theme", dark ? "dark" : "light");
  }, [dark]);

  const t = dark ? darkTheme : lightTheme;

  return (
    <ConfigProvider
      theme={{
        algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: { colorPrimary: theme.accent, borderRadius: 8 },
      }}
    >
      <Layout style={{ minHeight: "100vh", background: t.pageBg }}>
        <Header style={{
          background: t.cardBg,
          borderBottom: `1px solid ${t.border}`,
          padding: "0 2rem",
          height: "auto",
          lineHeight: "normal",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxShadow: dark ? "0 2px 8px rgba(0,0,0,0.3)" : "0 2px 8px rgba(0,0,0,0.05)",
          paddingTop: "0.8rem",
          paddingBottom: "0.8rem",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {section && (
              <Button icon={<ArrowLeftOutlined />} type="text" style={{ color: t.link }}
                onClick={() => {
                  if (section === "worker" || section === "cockpit" || section === "metas") setSection("obsoleto");
                  else if (section === "bus" && selectedBu) setSelectedBu(null);
                  else setSection(null);
                }} />
            )}
            <img src="/logo-fcamara.png" alt="FCamara" style={{ height: 32, width: "auto", filter: dark ? "brightness(0.9)" : "none" }} />
            <div>
              <Title level={4} style={{ margin: 0, color: t.text }}>Cockpit FP&A</Title>
              <Text type="secondary" style={{ fontSize: "0.8rem" }}>Visualização gerencial de resultados financeiros</Text>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: "0.7rem", color: t.secondary, fontFamily: "monospace", background: t.tagBg, padding: "2px 8px", borderRadius: 4, border: `1px solid ${t.border}` }}>
              v{process.env.REACT_APP_VERSION ?? "dev"}
            </span>
            <Switch
              checked={dark}
              onChange={setDark}
              checkedChildren={<MoonOutlined />}
              unCheckedChildren={<SunOutlined />}
              style={{ background: dark ? "#3b4a6b" : "#d9d9d9" }}
            />
            <Button icon={<LogoutOutlined />} onClick={logout} type="text" style={{ color: t.secondary }}>
              Sair
            </Button>
          </div>
        </Header>

        <Content style={{ padding: "1.5rem 2rem" }}>
          {(section === null || section === "obsoleto") && (() => {
            // Catálogo único dos cards da home, indexado pela key do Section.
            const CARD_CATALOG: Record<string, { icon: React.ReactNode; title: string; desc: string; sub: string }> = {
              nova_base:        { icon: <DatabaseOutlined />,  title: "Financeiro - Nova Base", desc: "Base unificada 2026 com todas as fontes",                  sub: "Nova Base · 2026" },
              bus:              { icon: <ClusterOutlined />,   title: "Visão BUs",               desc: "Recorte do financeiro por BU (Finance, Health, etc.)",   sub: me && !me.is_admin ? `BU · ${me.bus.join(", ")}` : "BUs · 2026" },
              budget:           { icon: <AimOutlined />,       title: "Budget vs Realizado",     desc: "Comparativo orçado vs realizado 2026",                   sub: "Budget · 2026" },
              nova_base_pivot:  { icon: <TableOutlined />,     title: "Visão Personalizada",     desc: "Tabela dinâmica sobre a Nova Base 2026",                 sub: "Pivot · Drag-and-drop" },
              obsoleto:         { icon: <InboxOutlined />,     title: "Obsoleto",                desc: "Telas legadas (Worker, Financeiro SAP, Metas Q4/Q3)",    sub: "Arquivo" },
              admin:            { icon: <SafetyCertificateOutlined />, title: "Administração",   desc: "Usuários, histórico de login e online agora",             sub: "Painel · só você" },
            };
            // Cards da home: backend já calculou em me.visible_cards (default por role aplicado).
            // 'admin' não está em visible_cards (não pode ser desabilitado): adiciono se super_admin.
            const homeKeys: string[] = section === null
              ? [
                  ...(me?.visible_cards ?? []),
                  ...(me?.is_super_admin ? ["admin"] : []),
                ]
              : ["worker", "cockpit", "metas"]; // section === "obsoleto"
            // Adiciona ao catálogo o que é específico de "obsoleto"
            const obsoletoExtras: Record<string, typeof CARD_CATALOG[string]> = {
              worker:  { icon: <UserOutlined />, title: "Worker",            desc: "Receitas e custos por colaborador",          sub: "Base Worker" },
              cockpit: { icon: <BankOutlined />, title: "Financeiro",        desc: "DRE, P&L por Stream e Matricial",            sub: "SAP S4 · Nexus" },
              metas:   { icon: <AimOutlined />,  title: "Apuração de Metas", desc: "Acompanhamento e apuração de metas Q4 e Q3", sub: "Margem · Clientes · Check" },
            };
            const cards = homeKeys
              .map(key => ({ key, ...(CARD_CATALOG[key] ?? obsoletoExtras[key]) }))
              .filter(c => c.title); // ignora keys desconhecidas
            return (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 280px)", gap: 24, justifyContent: "center", alignContent: "center", minHeight: "60vh" }}>
                {cards.map(({ key, icon, title, desc, sub }) => (
                  <div
                    key={key}
                    onClick={() => setSection(key as Section)}
                    className="home-card"
                    style={{
                      width: 280,
                      height: 280,
                      cursor: "pointer",
                      background: t.cardBg,
                      borderRadius: 14,
                      border: `1.5px solid ${t.border}`,
                      padding: "2rem 1.5rem",
                      textAlign: "center",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      boxShadow: dark ? "0 2px 12px rgba(0,0,0,0.3)" : "0 2px 8px rgba(0,0,0,0.05)",
                      transition: "box-shadow 0.2s, transform 0.15s, border-color 0.2s",
                    }}
                  >
                    <div style={{ fontSize: 40, marginBottom: 14, lineHeight: 1, color: theme.accent }}>{icon}</div>
                    <div style={{ color: t.text, fontWeight: 700, fontSize: "1.05rem", marginBottom: 6 }}>{title}</div>
                    <div style={{ color: t.secondary, fontSize: "0.82rem", lineHeight: 1.5, marginBottom: 10 }}>{desc}</div>
                    <div style={{ display: "inline-block", background: t.tagBg, color: t.secondary, fontSize: "0.72rem", fontWeight: 600, padding: "2px 10px", borderRadius: 20, letterSpacing: 0.3, alignSelf: "center" }}>{sub}</div>
                  </div>
                ))}
              </div>
            );
          })()}

          {section === "worker" && (
            <Tabs
              defaultActiveKey="worker"
              type="card"
              size="large"
              items={[
                { key: "worker", label: <span><UserOutlined /> Worker</span>, children: <WorkerTab dark={dark} /> },
              ]}
            />
          )}

          {section === "bus" && !selectedBu && (
            <div>
              <Title level={4} style={{ color: t.text, marginBottom: 6 }}>Visão por BU</Title>
              <Text type="secondary" style={{ fontSize: "0.85rem", display: "block", marginBottom: 24 }}>
                Selecione uma BU para abrir o recorte financeiro completo dela.
              </Text>
              {!me && <Text type="secondary">Carregando BUs...</Text>}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, 240px)", gap: 20, justifyContent: "center" }}>
                {(me?.visible_bus ?? []).map((bu) => (
                  <div
                    key={bu}
                    className="home-card"
                    onClick={() => setSelectedBu(bu)}
                    style={{
                      width: 240, height: 200, cursor: "pointer",
                      background: t.cardBg, borderRadius: 14,
                      border: `1.5px solid ${t.border}`,
                      padding: "1.5rem 1rem", textAlign: "center",
                      display: "flex", flexDirection: "column", justifyContent: "center",
                      boxShadow: dark ? "0 2px 12px rgba(0,0,0,0.3)" : "0 2px 8px rgba(0,0,0,0.05)",
                      transition: "box-shadow 0.2s, transform 0.15s, border-color 0.2s",
                    }}
                  >
                    <div style={{ fontSize: 36, marginBottom: 10, color: theme.accent }}>{BU_ICON[bu] ?? <ApartmentOutlined />}</div>
                    <div style={{ color: t.text, fontWeight: 700, fontSize: "1.05rem", marginBottom: 4 }}>{BU_LABEL[bu] ?? bu}</div>
                    <div style={{ color: t.secondary, fontSize: "0.78rem" }}>{bu}</div>
                  </div>
                ))}
                {me && me.visible_bus.length === 0 && (
                  <div style={{ color: t.secondary, gridColumn: "1 / -1", textAlign: "center" }}>
                    Você não tem acesso a nenhuma BU. Fale com o administrador.
                  </div>
                )}
              </div>
            </div>
          )}

          {section === "bus" && selectedBu && (
            <>
              <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
                <Title level={4} style={{ margin: 0, color: t.text }}>
                  <span style={{ color: theme.accent, marginRight: 8 }}>{BU_ICON[selectedBu] ?? <ApartmentOutlined />}</span>
                  {BU_LABEL[selectedBu] ?? selectedBu}
                </Title>
                <span style={{ fontSize: "0.78rem", color: t.secondary, background: t.tagBg, padding: "2px 10px", borderRadius: 20, border: `1px solid ${t.border}` }}>
                  Filtro de BU travado em <b>{selectedBu}</b>
                </span>
              </div>
              <BUTabs bu={selectedBu} />
            </>
          )}

          {section === "metas" && (
            <>
              <div style={{ background: t.cardBg, border: `1px solid ${t.border}`, borderRadius: 10, padding: "0.6rem 1.2rem", marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
                <Switch
                  size="small"
                  checked={apenasAtribuidos}
                  onChange={v => setApenasAtribuidos(v)}
                />
                <span style={{ fontSize: "0.85rem", fontWeight: 600, color: apenasAtribuidos ? t.link : t.secondary }}>
                  Apenas projetos atribuídos
                </span>
                {apenasAtribuidos && (
                  <span style={{ fontSize: "0.78rem", color: dark ? "#fbbf24" : "#856404", background: dark ? "#3b2800" : "#fff3cd", padding: "1px 8px", borderRadius: 4 }}>
                    Filtrando pela base de clientes
                  </span>
                )}
              </div>
              <Tabs
                defaultActiveKey="resumo"
                type="card"
                size="large"
                items={[
                  { key: "resumo",          label: <span><FileTextOutlined /> Resumo por Empresa</span>,  children: <ResumoTab apenasAtribuidos={apenasAtribuidos} /> },
                  { key: "visao-master",    label: <span><AimOutlined /> Apuração Q4</span>,              children: <VistaMasterTab /> },
                  { key: "visao-master-q3", label: <span><AimOutlined /> Apuração Q3</span>,              children: <VistaMasterTabQ3 /> },
                  { key: "margem",          label: <span><FundOutlined /> Margem por Cliente</span>,      children: <MargemTab apenasAtribuidos={apenasAtribuidos} /> },
                  { key: "check",           label: <span><AuditOutlined /> Check Lucas</span>,            children: <CheckLucasTab /> },
                  { key: "clientes",        label: <span><TeamOutlined /> Clientes</span>,                children: <ClientesTab /> },
                ]}
              />
            </>
          )}

          {section === "nova_base" && (
            <NovaBaseFiltersProvider>
            <NovaBaseUploadButton />
            <Tabs
              defaultActiveKey="resumoEmp"
              type="card"
              size="large"
              items={[
                { key: "resumoEmp", label: <span><FileTextOutlined /> Resumo por Empresa</span>, children: <NovaBaseResumoTab agruparPor="empresa" /> },
                { key: "resumoBU",  label: <span><ApartmentOutlined /> Resumo por BU</span>,    children: <NovaBaseResumoTab agruparPor="vertical" /> },
                { key: "margemCli", label: <span><FundOutlined /> Margem por Cliente</span>,   children: <NovaBaseMargemTab /> },
                { key: "empresa",   label: <span><BankOutlined /> DRE</span>,                   children: <NovaDreTab /> },
                { key: "fonte",     label: <span><HeatMapOutlined /> PJ/CLT</span>,             children: <NovaBaseResumoTab agruparPor="tipo_pessoa" /> },
                { key: "macroArea", label: <span><SlidersOutlined /> P&L por Macro Área</span>, children: <NovaBaseResumoTab agruparPor="macro_area" /> },
                { key: "apuracao",  label: <span><AimOutlined /> Apuração</span>,               children: <NovaBaseResumoTab agruparPor="apuracao" /> },
                { key: "workers",   label: <span><TeamOutlined /> Workers</span>,                children: <WorkersTab /> },
                { key: "base",      label: <span><DatabaseOutlined /> Base Detalhada</span>,    children: <NovaBaseTab /> },
              ]}
            />
            </NovaBaseFiltersProvider>
          )}

          {section === "budget" && (
            <NovaBaseFiltersProvider>
              <Tabs
                defaultActiveKey="bu"
                type="card"
                size="large"
                items={[
                  { key: "empresa", label: <span><FileTextOutlined /> Resumo por Empresa</span>, children: <BudgetVsRealizadoTab fixedGroupBy="vertical" /> },
                  { key: "bu",      label: <span><ApartmentOutlined /> Resumo por BU</span>,     children: <BudgetVsRealizadoTab fixedGroupBy="vertical" /> },
                  { key: "cliente", label: <span><FundOutlined /> Margem por Cliente</span>,    children: <BudgetVsRealizadoTab fixedGroupBy="nome_cliente" /> },
                  { key: "dre",     label: <span><BankOutlined /> DRE</span>,                    children: <BudgetVsRealizadoTab fixedGroupBy="vertical" /> },
                ]}
              />
            </NovaBaseFiltersProvider>
          )}

          {section === "nova_base_pivot" && (
            <NovaBaseFiltersProvider>
              <NovaBasePivotTab />
            </NovaBaseFiltersProvider>
          )}

          {section === "admin" && me?.is_super_admin && (
            <>
              <div style={{ marginBottom: 12 }}>
                <Title level={4} style={{ margin: 0, color: t.text }}>
                  <SafetyCertificateOutlined style={{ color: theme.accent, marginRight: 8 }} />
                  Administração
                </Title>
                <Text type="secondary" style={{ fontSize: "0.85rem" }}>
                  Cadastro de usuários, histórico de logins e quem está online.
                </Text>
              </div>
              <AdminTab />
            </>
          )}

          {section === "cockpit" && (
            <Tabs
              defaultActiveKey="dre"
              type="card"
              size="large"
              items={[
                { key: "dre",       label: <span><BankOutlined /> DRE por Empresa</span>,    children: <DreTab /> },
                { key: "streams",   label: <span><HeatMapOutlined /> P&L por Stream</span>,  children: <StreamsTab /> },
                { key: "matricial", label: <span><SlidersOutlined /> P&L Matricial</span>,   children: <MatricialTab /> },
                { key: "sap",       label: <span><DatabaseOutlined /> Base SAP S4</span>,    children: <SapTab /> },
              ]}
            />
          )}
        </Content>
      </Layout>

      <style>{`
        body { background: ${t.pageBg}; transition: background 0.2s; }
        .total-row td   { background-color: ${t.totalRow} !important; font-weight: 700; }
        .subtotal-row td { background-color: ${t.totalRow} !important; font-weight: 700; }
        .group-row td   { background-color: ${t.groupRow} !important; font-weight: 600; border-top: 2px solid ${dark ? "#2d4a8a" : "#c7d2fe"} !important; }
        .ant-table-thead > tr > th { background: ${theme.accent} !important; color: #fff !important; font-weight: 600; }
        .ant-table-row:hover > td  { background: ${t.hoverRow} !important; }
        .ant-tabs-card > .ant-tabs-nav .ant-tabs-tab-active { background: ${theme.accent} !important; border-color: ${theme.accent} !important; }
        .ant-tabs-card > .ant-tabs-nav .ant-tabs-tab-active .ant-tabs-tab-btn { color: #fff !important; }
        .clickable-row { cursor: pointer; }
        .clickable-row:hover > td { background: ${t.hoverRow} !important; }
        .home-card:hover { box-shadow: ${dark ? "0 8px 28px rgba(0,0,0,0.5)" : "0 8px 24px rgba(0,0,0,0.12)"} !important; transform: translateY(-2px); border-color: ${theme.accent} !important; }

        /* ── Dark mode: sobrescreve backgrounds hardcoded nos componentes filhos ── */
        ${dark ? `
        [data-theme="dark"] div[style*="background: rgb(255, 255, 255)"],
        [data-theme="dark"] div[style*="background: #fff"],
        [data-theme="dark"] div[style*='background: "#fff"'],
        [data-theme="dark"] .ant-card { background: #161b2e !important; border-color: #2a3050 !important; }
        [data-theme="dark"] .ant-card-body { background: #161b2e !important; }
        [data-theme="dark"] .ant-statistic-title { color: #8892a4 !important; }
        [data-theme="dark"] .ant-statistic-content { color: #e2e8f0 !important; }
        [data-theme="dark"] .ant-select-selector { background: #1e2438 !important; border-color: #2a3050 !important; color: #e2e8f0 !important; }
        [data-theme="dark"] .ant-select-selection-placeholder { color: #8892a4 !important; }
        [data-theme="dark"] .ant-select-arrow { color: #8892a4 !important; }
        [data-theme="dark"] .ant-select-dropdown { background: #1e2438 !important; border-color: #2a3050 !important; }
        [data-theme="dark"] .ant-select-item { color: #e2e8f0 !important; }
        [data-theme="dark"] .ant-select-item:hover { background: #2a3050 !important; }
        [data-theme="dark"] .ant-select-item-option-selected { background: #2d4a8a !important; }
        [data-theme="dark"] .ant-table-wrapper { background: #161b2e !important; }
        [data-theme="dark"] .ant-table { background: #161b2e !important; color: #e2e8f0 !important; }
        [data-theme="dark"] .ant-table-cell { background: #161b2e !important; color: #e2e8f0 !important; border-color: #2a3050 !important; }
        [data-theme="dark"] .ant-table-tbody > tr > td { border-color: #2a3050 !important; }
        [data-theme="dark"] .ant-table-tbody > tr > td span { color: #e2e8f0 !important; }
        [data-theme="dark"] .ant-table-tbody > tr > td span[style*="color: rgb(192, 57, 43)"],
        [data-theme="dark"] .ant-table-tbody > tr > td span[style*="color: rgb(255, 92, 53)"] { color: inherit !important; }
        [data-theme="dark"] .ant-table-container { border-color: #2a3050 !important; }
        [data-theme="dark"] .ant-table-title { background: #161b2e !important; border-color: #2a3050 !important; }
        [data-theme="dark"] .ant-btn-default { background: #1e2438 !important; border-color: #2a3050 !important; color: #e2e8f0 !important; }
        [data-theme="dark"] .ant-tabs-card > .ant-tabs-nav .ant-tabs-tab { background: #1e2438 !important; border-color: #2a3050 !important; color: #8892a4 !important; }
        [data-theme="dark"] .ant-tabs-content-holder { background: #161b2e !important; border-color: #2a3050 !important; }
        [data-theme="dark"] .ant-tabs-card > .ant-tabs-nav { background: transparent !important; }
        [data-theme="dark"] .ant-popover-inner { background: #1e2438 !important; border-color: #2a3050 !important; }
        [data-theme="dark"] .ant-checkbox-wrapper { color: #e2e8f0 !important; }
        [data-theme="dark"] label { color: #e2e8f0 !important; }
        ` : ``}
      `}</style>
    </ConfigProvider>
  );
}

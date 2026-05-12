import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Table, Select, Space, Typography, Tag, Button, Input, Dropdown, Checkbox } from "antd";
import { FilterOutlined, DownloadOutlined, SearchOutlined, SettingOutlined } from "@ant-design/icons";
import { Resizable } from "react-resizable";
import "react-resizable/css/styles.css";
import { getNovaBaseFilters, getNovaBaseData, downloadNovaBase } from "../api";
import TableSkeleton from "../components/TableSkeleton";
import { theme } from "../theme";
import { exportTableToExcel } from "../utils/exportExcel";

function ResizableTitle({ onResize, width, ...rest }: any) {
  if (!width) return <th {...rest} />;
  return (
    <Resizable
      width={width}
      height={0}
      handle={
        <span
          className="react-resizable-handle"
          onClick={(e) => e.stopPropagation()}
          style={{ position: "absolute", right: -5, top: 0, bottom: 0, width: 10, cursor: "col-resize", zIndex: 1 }}
        />
      }
      onResize={onResize}
      draggableOpts={{ enableUserSelectHack: false }}
    >
      <th {...rest} style={{ ...rest.style, position: "relative" }} />
    </Resizable>
  );
}

const { Text } = Typography;

const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const filterBox: React.CSSProperties = {
  background: "#fff", border: "1px solid #dde3f0", borderRadius: 10,
  padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap",
};

const fmt = (v: any) =>
  v == null ? "—" : typeof v === "number"
    ? v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : String(v);

const FONTE_COLORS: Record<string, string> = {
  // Famílias (fonte_familia)
  "Mapa Pessoas": "purple",
  "Custo Gerencial": "blue",
  "Custo Project": "geekblue",
  "Racionais": "green",
  "Outros": "default",
  // Abas (fonte) — fallback
  custo_project: "geekblue", racionais: "green", CLTs: "purple",
  PJs: "orange", "Custo Socios": "red", "de para": "default",
  TDMs: "cyan", "Equipe Labs": "magenta", "Equipe Play": "volcano",
  financeiro: "gold", nexus_agg: "lime", custo_gerencial: "blue",
};

export default function NovaBaseTab() {
  const [filters, setFilters] = useState<any>({});
  const [selPeriodos, setSelPeriodos]       = useState<string[]>(["2026-01", "2026-02", "2026-03"]);
  const [selFontes, setSelFontes]           = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas]       = useState<string[]>([]);
  const [selMacroAreas, setSelMacroAreas]   = useState<string[]>([]);
  const [selTipos, setSelTipos]             = useState<string[]>([]);
  const [selClassif, setSelClassif]         = useState<string[]>([]);
  const [selVerticais, setSelVerticais]     = useState<string[]>([]);
  const [selApuracoes, setSelApuracoes]     = useState<string[]>([]);
  const [selNoHier, setSelNoHier]           = useState<string[]>([]);
  const [rows, setRows]                     = useState<any[]>([]);
  const [total, setTotal]                   = useState(0);
  const [truncated, setTruncated]           = useState(false);
  const [loading, setLoading]               = useState(true);
  const [error, setError]                   = useState<string | null>(null);
  const [filtersReady, setFiltersReady]     = useState(false);
  const [downloadingAll, setDownloadingAll] = useState(false);
  const [search, setSearch]                 = useState("");
  const [pageSize, setPageSize]             = useState(50);
  const [currentPage, setCurrentPage]       = useState(1);

  useEffect(() => {
    getNovaBaseFilters()
      .then(f => { setFilters(f); setFiltersReady(true); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, []);

  const load = useCallback((searchTerm: string = "") => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length)   params.periodos       = selPeriodos.join(",");
    if (selFontes.length)     params.fontes         = selFontes.join(",");
    if (selEmpresas.length)   params.empresas       = selEmpresas.join(",");
    if (selMacroAreas.length) params.macro_areas    = selMacroAreas.join(",");
    if (selTipos.length)      params.tipos_contrato = selTipos.join(",");
    if (selClassif.length)    params.classificacoes = selClassif.join(",");
    if (selVerticais.length)  params.verticais      = selVerticais.join(",");
    if (selApuracoes.length)  params.apuracoes      = selApuracoes.join(",");
    if (selNoHier.length)     params.no_hierarquias = selNoHier.join(",");
    if (searchTerm.trim())    params.search         = searchTerm.trim();
    getNovaBaseData(params)
      .then(r => { setRows(r.rows); setTotal(r.total); setTruncated(r.truncated); })
      .finally(() => setLoading(false));
  }, [selPeriodos, selFontes, selEmpresas, selMacroAreas, selTipos, selClassif, selVerticais, selApuracoes, selNoHier]);

  useEffect(() => { if (filtersReady) load(""); }, [filtersReady, load]);

  // Debounce server-side search
  useEffect(() => {
    if (!filtersReady) return;
    const t = setTimeout(() => { load(search); }, 350);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const [columns, setColumns] = useState<any[]>([
    { title: "Fonte", dataIndex: "fonte_familia", key: "fonte_familia", width: 140,
      render: (v: string) => <Tag color={FONTE_COLORS[v] ?? "default"}>{v}</Tag> },
    { title: "Aba", dataIndex: "fonte", key: "fonte", width: 130, ellipsis: true },
    { title: "Arquivo", dataIndex: "fonte_dados", key: "fonte_dados", width: 220, ellipsis: true },
    { title: "Período",    dataIndex: "periodo",         key: "periodo",         width: 90 },
    { title: "Empresa",    dataIndex: "empresa",         key: "empresa",         width: 90 },
    { title: "PEP",        dataIndex: "pep_base",        key: "pep_base",        width: 130 },
    { title: "Pessoa",     dataIndex: "nome_pessoa",     key: "nome_pessoa",     width: 200, ellipsis: true },
    { title: "Cliente",    dataIndex: "nome_cliente",    key: "nome_cliente",    width: 200, ellipsis: true },
    { title: "Tipo",       dataIndex: "tipo_contrato",   key: "tipo_contrato",   width: 80 },
    { title: "Classif.",   dataIndex: "classificacao",   key: "classificacao",   width: 90,
      render: (v: string) => v ? <Tag color={v === "custo" ? "blue" : "orange"}>{v}</Tag> : "—" },
    { title: "Área",       dataIndex: "area",            key: "area",            width: 140 },
    { title: "Macro Área", dataIndex: "macro_area",      key: "macro_area",      width: 130 },
    { title: "Vertical",   dataIndex: "vertical",        key: "vertical",        width: 140, ellipsis: true },
    { title: "Apuração",   dataIndex: "apuracao",        key: "apuracao",        width: 110,
      render: (v: string) => v ? <Tag color={v === "NG" ? "magenta" : "geekblue"}>{v}</Tag> : "—" },
    { title: "Receita",    dataIndex: "receita",         key: "receita",         width: 120, align: "right" as const,
      render: fmt },
    { title: "Custo",      dataIndex: "custo_rateado",   key: "custo_rateado",   width: 120, align: "right" as const,
      render: fmt },
    { title: "Horas",      dataIndex: "horas",           key: "horas",           width: 80,  align: "right" as const,
      render: fmt },
    { title: "Margem",     dataIndex: "margem",          key: "margem",          width: 120, align: "right" as const,
      render: fmt },
    { title: "Vlr Líquido", dataIndex: "valor_liquido",  key: "valor_liquido",   width: 120, align: "right" as const,
      render: fmt },
    { title: "Billable",   dataIndex: "billable_category", key: "billable_category", width: 100 },
    { title: "Taxa/h",     dataIndex: "taxa_hora",       key: "taxa_hora",       width: 90, align: "right" as const, render: fmt },
    { title: "Origem do Custo", dataIndex: "tag_rateio", key: "tag_rateio", width: 280, ellipsis: true,
      render: (v: string) => v ? <span style={{ color: "#6b7fa3", fontSize: "0.78rem" }}>{v}</span> : "—" },
    { title: "Comentários", dataIndex: "Comentarios",    key: "Comentarios",     width: 200, ellipsis: true },
  ]);

  const handleResize = (index: number) => (_: any, { size }: any) => {
    setColumns((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], width: size.width };
      return next;
    });
  };

  // Column visibility (persistido em localStorage)
  const STORAGE_KEY = "novaBase.visibleColumns";
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return new Set(JSON.parse(saved));
    } catch {}
    return new Set(columns.map((c) => c.key));
  });
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(visibleKeys))); } catch {}
  }, [visibleKeys]);

  const toggleColumn = (key: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const visibleColumns = columns.filter((c) => visibleKeys.has(c.key));
  const resizableColumns = visibleColumns.map((col, index) => ({
    ...col,
    onHeaderCell: (column: any) => ({
      width: column.width,
      onResize: handleResize(columns.indexOf(col)),
    }),
  }));

  const columnSettingsMenu = (
    <div style={{ background: "#fff", border: "1px solid #e0e0e0", borderRadius: 8,
                  padding: "0.6rem 0.9rem", maxHeight: 420, overflowY: "auto", minWidth: 220,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <Button size="small" type="link" style={{ padding: 0 }}
          onClick={() => setVisibleKeys(new Set(columns.map((c) => c.key)))}>
          Marcar todas
        </Button>
        <Button size="small" type="link" style={{ padding: 0 }}
          onClick={() => setVisibleKeys(new Set())}>
          Desmarcar
        </Button>
      </div>
      {columns.map((c) => (
        <div key={c.key} style={{ padding: "3px 0" }}>
          <Checkbox checked={visibleKeys.has(c.key)} onChange={() => toggleColumn(c.key)}>
            {c.title}
          </Checkbox>
        </div>
      ))}
    </div>
  );

  const opt = (arr: string[]) => [
    ...arr.map(v => ({ label: v, value: v })),
    { label: "(Vazio)", value: "__blank__" },
  ];

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    const fields = ["nome_pessoa", "nome_cliente", "pep_base", "empresa", "fonte", "fonte_dados",
                    "fonte_familia", "area", "macro_area", "vertical", "tipo_contrato", "Comentarios"];
    return rows.filter(r =>
      fields.some(f => String(r[f] ?? "").toLowerCase().includes(q))
    );
  }, [rows, search]);

  return (
    <div>
      <div style={filterBox}>
        <div style={{ flex: 1, minWidth: 150 }}>
          <div style={labelStyle}>Período</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos}
            onChange={setSelPeriodos} options={opt(filters.periodos ?? [])}
            maxTagCount="responsive" placeholder="Todos" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 150 }}>
          <div style={labelStyle}>Fonte</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selFontes}
            onChange={setSelFontes} options={opt(filters.fontes ?? [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 130 }}>
          <div style={labelStyle}>Empresa</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas}
            onChange={setSelEmpresas} options={opt(filters.empresas ?? [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 150 }}>
          <div style={labelStyle}>Macro Área</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selMacroAreas}
            onChange={setSelMacroAreas} options={opt(filters.macro_areas ?? [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 120 }}>
          <div style={labelStyle}>Tipo Contrato</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selTipos}
            onChange={setSelTipos} options={opt(filters.tipos_contrato ?? [])}
            maxTagCount="responsive" placeholder="Todos" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 120 }}>
          <div style={labelStyle}>Classificação</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selClassif}
            onChange={setSelClassif}
            options={opt(filters.classificacoes ?? [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 130 }}>
          <div style={labelStyle}>BU</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selVerticais}
            onChange={setSelVerticais} options={opt(filters.verticais ?? [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 130 }}>
          <div style={labelStyle}>Apuração</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selApuracoes}
            onChange={setSelApuracoes} options={opt(filters.apuracoes ?? [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <div style={labelStyle}>Centro de Lucro</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selNoHier}
            onChange={setSelNoHier} options={opt(filters.no_hierarquias ?? [])}
            maxTagCount="responsive" placeholder="Todos" allowClear />
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
          <Button icon={<DownloadOutlined />} onClick={() => exportTableToExcel(columns, rows, "nova_base")}>
            Exportar Filtrado
          </Button>
          <Button icon={<DownloadOutlined />} type="primary" ghost loading={downloadingAll}
            onClick={async () => {
              setDownloadingAll(true);
              try {
                await downloadNovaBase();
              } catch {} finally { setDownloadingAll(false); }
            }}>
            Baixar Base Completa
          </Button>
        </div>
      </div>

      <div style={{ marginBottom: 12, display: "flex", gap: 12, alignItems: "center" }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder="Buscar por pessoa, cliente, PEP, empresa, área..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
          style={{ maxWidth: 360 }}
        />
        <Space>
          <Text type="secondary" style={{ fontSize: "0.82rem" }}>
            <FilterOutlined /> {filteredRows.length.toLocaleString("pt-BR")}
            {search && filteredRows.length !== rows.length && ` de ${rows.length.toLocaleString("pt-BR")}`}
            {" "}registros
            {truncated && !search && <Tag color="warning" style={{ marginLeft: 8 }}>Exibindo primeiros 5.000</Tag>}
          </Text>
        </Space>
        <div style={{ marginLeft: "auto" }}>
          <Dropdown popupRender={() => columnSettingsMenu} trigger={["click"]} placement="bottomRight">
            <Button icon={<SettingOutlined />} title="Selecionar colunas">
              Colunas ({visibleKeys.size}/{columns.length})
            </Button>
          </Dropdown>
        </div>
      </div>

      {loading ? <TableSkeleton rows={10} /> : error ? (
        <div style={{ background: "#fff1f0", border: "1px solid #ffa39e", borderRadius: 8, padding: "1rem 1.2rem", color: "#cf1322" }}>
          <strong>Erro ao carregar dados:</strong> {error}
        </div>
      ) : (
        <Table
          dataSource={filteredRows}
          columns={resizableColumns}
          components={{ header: { cell: ResizableTitle } }}
          rowKey={(_, i) => String(i)}
          size="small"
          scroll={{ x: 2700, y: 520 }}
          pagination={{
            pageSize,
            current: currentPage,
            showSizeChanger: true,
            pageSizeOptions: ["50", "100", "200"],
            total: filteredRows.length,
            onChange: (page, size) => {
              setCurrentPage(page);
              setPageSize(size);
            },
            onShowSizeChange: (_p, size) => {
              setCurrentPage(1);
              setPageSize(size);
            },
            showTotal: (total, range) => `${range[0]}-${range[1]} de ${total}`,
          }}
        />
      )}
    </div>
  );
}

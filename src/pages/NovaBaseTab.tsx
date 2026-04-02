import React, { useEffect, useState, useCallback } from "react";
import { Table, Select, Space, Typography, Tag, Button } from "antd";
import { FilterOutlined, DownloadOutlined } from "@ant-design/icons";
import { getNovaBaseFilters, getNovaBaseData } from "../api";
import TableSkeleton from "../components/TableSkeleton";
import { theme } from "../theme";
import { exportTableToExcel } from "../utils/exportExcel";

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
  custo_project: "blue", racionais: "green", CLTs: "purple",
  PJs: "orange", "Custo Socios": "red", "de para": "default",
  TDMs: "cyan", "Equipe Labs": "magenta", "Equipe Play": "volcano",
  financeiro: "gold", nexus_agg: "lime",
};

export default function NovaBaseTab() {
  const [filters, setFilters] = useState<any>({});
  const [selPeriodos, setSelPeriodos]       = useState<string[]>([]);
  const [selFontes, setSelFontes]           = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas]       = useState<string[]>([]);
  const [selMacroAreas, setSelMacroAreas]   = useState<string[]>([]);
  const [selTipos, setSelTipos]             = useState<string[]>([]);
  const [selClassif, setSelClassif]         = useState<string[]>([]);
  const [rows, setRows]                     = useState<any[]>([]);
  const [total, setTotal]                   = useState(0);
  const [truncated, setTruncated]           = useState(false);
  const [loading, setLoading]               = useState(true);
  const [error, setError]                   = useState<string | null>(null);
  const [filtersReady, setFiltersReady]     = useState(false);

  useEffect(() => {
    getNovaBaseFilters()
      .then(f => { setFilters(f); setFiltersReady(true); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length)   params.periodos       = selPeriodos.join(",");
    if (selFontes.length)     params.fontes         = selFontes.join(",");
    if (selEmpresas.length)   params.empresas       = selEmpresas.join(",");
    if (selMacroAreas.length) params.macro_areas    = selMacroAreas.join(",");
    if (selTipos.length)      params.tipos_contrato = selTipos.join(",");
    if (selClassif.length)    params.classificacoes = selClassif.join(",");
    getNovaBaseData(params)
      .then(r => { setRows(r.rows); setTotal(r.total); setTruncated(r.truncated); })
      .finally(() => setLoading(false));
  }, [selPeriodos, selFontes, selEmpresas, selMacroAreas, selTipos, selClassif]);

  useEffect(() => { if (filtersReady) load(); }, [filtersReady, load]);

  const columns = [
    { title: "Fonte", dataIndex: "fonte", key: "fonte", width: 130,
      render: (v: string) => <Tag color={FONTE_COLORS[v] ?? "default"}>{v}</Tag> },
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
    { title: "Comentários", dataIndex: "Comentarios",    key: "Comentarios",     width: 200, ellipsis: true },
  ];

  const opt = (arr: string[]) => arr.map(v => ({ label: v, value: v }));

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
            onChange={setSelClassif} options={opt(filters.classificacoes ?? [])}
            maxTagCount="responsive" placeholder="Todas" allowClear />
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <Button icon={<DownloadOutlined />} onClick={() => exportTableToExcel(columns, rows, "nova_base")}>
            Exportar
          </Button>
        </div>
      </div>

      <div style={{ marginBottom: 12, display: "flex", gap: 12, alignItems: "center" }}>
        <Space>
          <Text type="secondary" style={{ fontSize: "0.82rem" }}>
            <FilterOutlined /> {total.toLocaleString("pt-BR")} registros
            {truncated && <Tag color="warning" style={{ marginLeft: 8 }}>Exibindo primeiros 5.000</Tag>}
          </Text>
        </Space>
      </div>

      {loading ? <TableSkeleton rows={10} /> : error ? (
        <div style={{ background: "#fff1f0", border: "1px solid #ffa39e", borderRadius: 8, padding: "1rem 1.2rem", color: "#cf1322" }}>
          <strong>Erro ao carregar dados:</strong> {error}
        </div>
      ) : (
        <Table
          dataSource={rows}
          columns={columns}
          rowKey={(_, i) => String(i)}
          size="small"
          scroll={{ x: 2200, y: 520 }}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
        />
      )}
    </div>
  );
}

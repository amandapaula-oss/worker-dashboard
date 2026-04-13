import React, { useCallback, useEffect, useRef, useState } from "react";
import { Select, Table, message, Button } from "antd";
import { DownloadOutlined, FilterOutlined } from "@ant-design/icons";
import { getSapFilters, getSapData } from "../api";
import { useDraggableColumns } from "../hooks/useDraggableColumns";
import { exportTableToExcel } from "../utils/exportExcel";
import { theme } from "../theme";
import TableSkeleton from "../components/TableSkeleton";
import ErrorState from "../components/ErrorState";

export default function SapTab() {
  const [filters, setFilters] = useState<{ companies: string[]; verticals: string[]; profit_centers: string[] }>({ companies: [], verticals: [], profit_centers: [] });
  const [selCompanies, setSelCompanies] = useState<string[]>([]);
  const [selVerticals, setSelVerticals] = useState<string[]>([]);
  const [selPC, setSelPC] = useState<string[]>([]);
  const [data, setData] = useState<{ columns: string[]; data: any[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filtersReady, setFiltersReady] = useState(false);
  const [showFilters, setShowFilters]   = useState(false);
  const initialLoad = useRef(true);

  const loadInitial = useCallback(() => {
    setLoading(true);
    setError(false);
    Promise.all([getSapFilters(), getSapData({})])
      .then(([f, d]) => {
        setFilters(f);
        setSelCompanies(f.companies);
        setData(d);
        setFiltersReady(true);
        initialLoad.current = false;
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadInitial(); }, [loadInitial]);

  useEffect(() => {
    if (!filtersReady || initialLoad.current) return;
    if (!selCompanies.length && filters.companies.length) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selCompanies.length) params.companies = selCompanies.join(",");
    if (selVerticals.length) params.verticals = selVerticals.join(",");
    if (selPC.length) params.profit_centers = selPC.join(",");
    getSapData(params)
      .then(d => setData(d))
      .catch(() => message.error("Erro ao carregar dados SAP"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selCompanies, selVerticals, selPC]);

  const columnsDef = data?.columns.map(col => ({
    title: col,
    dataIndex: col,
    key: col,
    align: col === "agrupador_fpa" ? "left" as const : "right" as const,
    render: (v: number | string) => typeof v === "number" ? v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : v,
  })) || [];

  const [columns, colSettings] = useDraggableColumns(columnsDef, "sap");

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={selCompanies.length < filters.companies.length || selVerticals.length < filters.verticals.length || selPC.length < filters.profit_centers.length ? "primary" : "default"}
          style={{ marginLeft: "auto" }}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>
      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selCompanies} onChange={setSelCompanies} options={filters.companies.map(c => ({ label: c, value: c }))} maxTagCount="responsive" />
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={labelStyle}>Vertical</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selVerticals} onChange={setSelVerticals} options={filters.verticals.map(v => ({ label: v, value: v }))} placeholder="Todas" maxTagCount="responsive" />
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={labelStyle}>Profit Center</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selPC} onChange={setSelPC} options={filters.profit_centers.map(p => ({ label: p, value: p }))} placeholder="Todos" maxTagCount="responsive" />
          </div>
        </div>
      )}

      {loading ? <TableSkeleton rows={10} /> : error ? <ErrorState onRetry={loadInitial} /> : (
        <Table
          dataSource={data?.data.map((d, i) => ({ ...d, key: i })) || []}
          columns={columns}
          title={() => (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 4, padding: "0 0 4px" }}>
              {colSettings}
              <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                onClick={() => exportTableToExcel(columns, data?.data || [], "sap")}>Excel</Button>
            </div>
          )}
          pagination={false}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
        />
      )}
    </div>
  );
}

const labelStyle: React.CSSProperties = { color: theme.text, fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4 };

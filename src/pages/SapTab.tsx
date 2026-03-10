import React, { useEffect, useState } from "react";
import { Select, Table, Spin, message } from "antd";
import { getSapFilters, getSapData } from "../api";


export default function SapTab() {
  const [filters, setFilters] = useState<{ companies: string[]; verticals: string[]; profit_centers: string[] }>({ companies: [], verticals: [], profit_centers: [] });
  const [selCompanies, setSelCompanies] = useState<string[]>([]);
  const [selVerticals, setSelVerticals] = useState<string[]>([]);
  const [selPC, setSelPC] = useState<string[]>([]);
  const [data, setData] = useState<{ columns: string[]; data: any[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [filtersReady, setFiltersReady] = useState(false);

  useEffect(() => {
    getSapFilters()
      .then(f => {
        setFilters(f);
        setSelCompanies(f.companies);
        setFiltersReady(true);
      })
      .catch(err => {
        console.error("Sap Filters Error:", err);
        message.error("Erro ao carregar filtros SAP");
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!filtersReady) return;
    if (!selCompanies.length && filters.companies.length) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selCompanies.length) params.companies = selCompanies.join(",");
    if (selVerticals.length) params.verticals = selVerticals.join(",");
    if (selPC.length) params.profit_centers = selPC.join(",");
    getSapData(params)
      .then(d => {
        setData(d);
      })
      .catch(err => {
        console.error("Sap Data Error:", err);
        message.error("Erro ao carregar dados SAP");
      })
      .finally(() => {
        setLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selCompanies, selVerticals, selPC]);

  const columns = data?.columns.map(col => ({
    title: col,
    dataIndex: col,
    key: col,
    align: col === "agrupador_fpa" ? "left" as const : "right" as const,
    render: (v: number | string) => typeof v === "number" ? v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : v,
  })) || [];

  return (
    <div>
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

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <Table
          dataSource={data?.data.map((d, i) => ({ ...d, key: i })) || []}
          columns={columns}
          pagination={false}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
        />
      )}
    </div>
  );
}

const labelStyle: React.CSSProperties = { color: "#3a4f7a", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4 };

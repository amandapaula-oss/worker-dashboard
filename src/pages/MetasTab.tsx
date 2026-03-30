import React, { useEffect, useState, useMemo } from "react";
import { Select, Table, message, Input, Button } from "antd";
import TableSkeleton from "../components/TableSkeleton";
import { SearchOutlined, DownloadOutlined, FilterOutlined } from "@ant-design/icons";
import { getMetasFilters, getMetasCustoPessoal } from "../api";
import { useDraggableColumns } from "../hooks/useDraggableColumns";
import { exportTableToExcel } from "../utils/exportExcel";
import { toTitleCase } from "../utils/format";
import { theme } from "../theme";

const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

export default function MetasTab() {
  const [filters, setFilters] = useState<{ competencias: string[]; empresas: string[]; tipos: string[] }>({ competencias: [], empresas: [], tipos: [] });
  const [selComp, setSelComp] = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [selTipos, setSelTipos] = useState<string[]>([]);
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtersReady, setFiltersReady] = useState(false);
  const [searchPessoa, setSearchPessoa] = useState("");
  const [showFilters, setShowFilters]   = useState(false);

  useEffect(() => {
    getMetasFilters()
      .then(f => {
        setFilters(f);
        setSelComp(f.competencias);
        setSelEmpresas(f.empresas);
        setSelTipos(f.tipos);
        setFiltersReady(true);
      })
      .catch(() => { message.error("Erro ao carregar filtros"); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!filtersReady) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selComp.length) params.competencias = selComp.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selTipos.length) params.tipos = selTipos.join(",");
    getMetasCustoPessoal(params)
      .then(d => setData(d))
      .catch(() => message.error("Erro ao carregar dados"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selComp, selEmpresas, selTipos]);

  const columnsDef = [
    { title: "ID SAP",  dataIndex: "id_sap", key: "id_sap", width: 110 },
    { title: "CPF",     dataIndex: "cpf",    key: "cpf",    width: 160 },
    { title: "Nome",    dataIndex: "nome",   key: "nome", ellipsis: true, render: (v: string) => toTitleCase(v) || "—" },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130, render: (v: string) => toTitleCase(v) || "—" },
    { title: "Tipo",    dataIndex: "tipo",   key: "tipo", width: 80 },
    {
      title: "Custo",
      dataIndex: "custo",
      key: "custo",
      width: 150,
      align: "right" as const,
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : theme.text, fontWeight: 600 }}>
          {v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
        </span>
      ),
    },
  ];

  const filteredData = useMemo(() => {
    const q = searchPessoa.trim().toLowerCase();
    if (!q) return data;
    return data.filter(r =>
      String(r.nome || "").toLowerCase().includes(q) ||
      String(r.id_sap || "").toLowerCase().includes(q) ||
      String(r.cpf || "").toLowerCase().includes(q)
    );
  }, [data, searchPessoa]);

  const [columns, colSettings] = useDraggableColumns(columnsDef, "metas");

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: showFilters ? 8 : 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Input allowClear placeholder="Buscar pessoa..."
          prefix={<SearchOutlined style={{ color: "#aab4cc" }} />}
          style={{ flex: 1 }}
          value={searchPessoa} onChange={e => setSearchPessoa(e.target.value)} />
        <Button icon={<FilterOutlined />} onClick={() => setShowFilters(v => !v)}
          type={selComp.length < filters.competencias.length || selEmpresas.length < filters.empresas.length || selTipos.length < filters.tipos.length ? "primary" : "default"}>
          Filtros{showFilters ? " ▲" : " ▼"}
        </Button>
      </div>
      {showFilters && (
        <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={labelStyle}>Competência</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selComp} onChange={setSelComp}
              options={filters.competencias.map(c => ({ label: c, value: c }))} maxTagCount="responsive" />
          </div>
          <div style={{ flex: 1, minWidth: 180 }}>
            <div style={labelStyle}>Empresa</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas} onChange={setSelEmpresas}
              options={filters.empresas.map(e => ({ label: e, value: e }))} maxTagCount="responsive" />
          </div>
          <div style={{ flex: 0, minWidth: 140 }}>
            <div style={labelStyle}>Tipo</div>
            <Select mode="multiple" style={{ width: "100%" }} value={selTipos} onChange={setSelTipos}
              options={filters.tipos.map(t => ({ label: t, value: t }))} maxTagCount="responsive" />
          </div>
        </div>
      )}

      {loading ? <TableSkeleton rows={10} /> : (
        <Table
          dataSource={(() => {
            const total = filteredData.reduce((s, r) => s + (Number(r.custo) || 0), 0);
            return [{ key:"__t__", numero_pessoal:"TOTAL", nome:"", empresa:"", tipo:"", custo: total, _isTotal:true }, ...filteredData.map((d,i)=>({...d,key:i}))];
          })()}
          columns={columns}
          title={() => (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 4, padding: "0 0 4px" }}>
              {colSettings}
              <Button size="small" type="text" icon={<DownloadOutlined />} style={{ color: "#6b7fa3" }}
                onClick={() => exportTableToExcel(columns, filteredData, "metas_custo_pessoal")}>Excel</Button>
            </div>
          )}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={row => row._isTotal ? { style: { background: "#dce6f7", fontWeight: 700 } } : {}}
        />
      )}
    </div>
  );
}

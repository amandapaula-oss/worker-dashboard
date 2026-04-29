import React, { useEffect, useMemo, useState } from "react";
import { Table, Input, Tag, Card, Statistic, Spin } from "antd";
import { SearchOutlined, FilterOutlined } from "@ant-design/icons";
import { getPessoas } from "../api";
import { theme } from "../theme";

const brl = (v: number) =>
  v == null || isNaN(Number(v)) ? "—" :
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const TIPO_COLORS: Record<string, string> = {
  CLT: "blue", PJ: "orange",
};

const BILLABLE_COLORS: Record<string, string> = {
  billable: "green", "non-billable": "red", custo: "blue", despesa: "orange",
};

export default function PessoasTab() {
  const [loading, setLoading] = useState(true);
  const [data, setData]       = useState<any[]>([]);
  const [search, setSearch]   = useState("");

  useEffect(() => {
    setLoading(true);
    getPessoas().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data;
    const fields = ["nome", "cpf", "numero_pessoal", "empresa", "funcao", "area", "macro_area", "tipo_contrato", "billable_category"];
    return data.filter(r => fields.some(f => String(r[f] ?? "").toLowerCase().includes(q)));
  }, [data, search]);

  const totalPessoas = filtered.length;
  const totalCusto   = filtered.reduce((s, r) => s + (Number(r.custo_total) || 0), 0);
  const mediaCusto   = filtered.reduce((s, r) => s + (Number(r.custo_mensal_medio) || 0), 0) / Math.max(filtered.length, 1);
  const cltCount     = filtered.filter(r => r.tipo_contrato === "CLT").length;
  const pjCount      = filtered.filter(r => r.tipo_contrato === "PJ").length;

  const columns = [
    { title: "CPF", dataIndex: "cpf", key: "cpf", width: 130, fixed: "left" as const,
      sorter: (a: any, b: any) => String(a.cpf).localeCompare(String(b.cpf)) },
    { title: "Nome", dataIndex: "nome", key: "nome", width: 230,
      sorter: (a: any, b: any) => String(a.nome).localeCompare(String(b.nome), "pt-BR") },
    { title: "ID", dataIndex: "numero_pessoal", key: "numero_pessoal", width: 100, ellipsis: true },
    { title: "Tipo", dataIndex: "tipo_contrato", key: "tipo_contrato", width: 80,
      render: (v: string) => v ? <Tag color={TIPO_COLORS[v] || "default"}>{v}</Tag> : "—",
      filters: [{ text: "CLT", value: "CLT" }, { text: "PJ", value: "PJ" }, { text: "Sem tag", value: "" }],
      onFilter: (val: any, r: any) => (r.tipo_contrato || "") === val },
    { title: "Classificação", dataIndex: "billable_category", key: "billable_category", width: 130,
      render: (v: string) => v ? <Tag color={BILLABLE_COLORS[v] || "default"}>{v}</Tag> : "—" },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130, ellipsis: true },
    { title: "Função", dataIndex: "funcao", key: "funcao", width: 160, ellipsis: true },
    { title: "Área", dataIndex: "area", key: "area", width: 130, ellipsis: true },
    { title: "Macro Área", dataIndex: "macro_area", key: "macro_area", width: 130, ellipsis: true },
    { title: "Custo Médio Mensal", dataIndex: "custo_mensal_medio", key: "custo_mensal_medio", align: "right" as const, width: 150,
      sorter: (a: any, b: any) => (a.custo_mensal_medio || 0) - (b.custo_mensal_medio || 0),
      render: (v: number) => <span style={{ fontWeight: 600 }}>{brl(v)}</span> },
    { title: "Custo Total", dataIndex: "custo_total", key: "custo_total", align: "right" as const, width: 130,
      sorter: (a: any, b: any) => (a.custo_total || 0) - (b.custo_total || 0),
      defaultSortOrder: "descend" as const,
      render: (v: number) => brl(v) },
    { title: "Meses", dataIndex: "meses_ativos", key: "meses_ativos", align: "right" as const, width: 80,
      sorter: (a: any, b: any) => (a.meses_ativos || 0) - (b.meses_ativos || 0) },
    { title: "Primeiro", dataIndex: "primeiro_periodo", key: "primeiro_periodo", width: 90 },
    { title: "Último", dataIndex: "ultimo_periodo", key: "ultimo_periodo", width: 90 },
  ];

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.7rem 1.2rem", marginBottom: 16, display: "flex", gap: 10, alignItems: "center" }}>
        <Input prefix={<SearchOutlined />} placeholder="Buscar por nome, CPF, função, empresa..."
          value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 360 }} allowClear />
        <span style={{ color: "#6b7fa3", fontSize: "0.82rem", marginLeft: "auto" }}>
          <FilterOutlined /> {totalPessoas.toLocaleString("pt-BR")} pessoas
          {search && data.length !== totalPessoas && ` (de ${data.length.toLocaleString("pt-BR")})`}
        </span>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        {[
          { label: "Total", value: totalPessoas.toLocaleString("pt-BR"), color: theme.text },
          { label: "CLTs", value: cltCount.toLocaleString("pt-BR"), color: "#1677ff" },
          { label: "PJs", value: pjCount.toLocaleString("pt-BR"), color: "#fa8c16" },
          { label: "Custo Médio Mensal Total", value: brl(mediaCusto * totalPessoas / 12), color: theme.text },
          { label: "Custo Acumulado", value: brl(totalCusto), color: totalCusto < 0 ? "#c0392b" : theme.text },
        ].map(k => (
          <Card key={k.label} style={{ flex: 1, minWidth: 150, borderRadius: 8, border: "1px solid #dde3f0" }}
            styles={{ body: { padding: "0.6rem 0.8rem", textAlign: "center" } }}>
            <Statistic
              title={<span style={{ color: "#6b7fa3", fontSize: "0.7rem", fontWeight: 600, textTransform: "uppercase" }}>{k.label}</span>}
              value={k.value}
              valueStyle={{ color: k.color, fontSize: "1rem", fontWeight: 700 }} />
          </Card>
        ))}
      </div>

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : (
        <Table
          dataSource={filtered.map((d, i) => ({ ...d, key: d.cpf || `nome_${i}` }))}
          columns={columns}
          size="small"
          scroll={{ x: 1700, y: 560 }}
          pagination={{ defaultPageSize: 50, showSizeChanger: true, pageSizeOptions: ["50", "100", "200"] }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
        />
      )}
    </div>
  );
}

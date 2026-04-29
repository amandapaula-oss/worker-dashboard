import React, { useEffect, useState } from "react";
import { Table, Card, Spin, Tag } from "antd";
import { getRelacoes } from "../api";
import { theme } from "../theme";

export default function RelacoesTab() {
  const [loading, setLoading] = useState(true);
  const [data, setData]       = useState<any>({ centro_custo: [], profit_center: [] });

  useEffect(() => {
    setLoading(true);
    getRelacoes().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const ccCols = [
    { title: "Centro de Custo", dataIndex: "centro_custo", key: "centro_custo", width: 250,
      sorter: (a: any, b: any) => String(a.centro_custo).localeCompare(String(b.centro_custo), "pt-BR") },
    { title: "Macro Área", dataIndex: "macro_area", key: "macro_area", width: 200,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
      filters: [...new Set((data.centro_custo || []).map((r: any) => r.macro_area))].map(v => ({ text: v as string, value: v as string })),
      onFilter: (val: any, r: any) => r.macro_area === val,
      sorter: (a: any, b: any) => String(a.macro_area).localeCompare(String(b.macro_area), "pt-BR") },
  ];

  const pcCols = [
    { title: "Profit Center", dataIndex: "profit_center", key: "profit_center", width: 150,
      render: (v: string) => <Tag color="purple">{v}</Tag>,
      sorter: (a: any, b: any) => String(a.profit_center).localeCompare(String(b.profit_center)) },
    { title: "Nome", dataIndex: "name", key: "name", width: 280,
      sorter: (a: any, b: any) => String(a.name).localeCompare(String(b.name), "pt-BR") },
  ];

  if (loading) return <Spin style={{ display: "block", margin: "2rem auto" }} />;

  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
      <Card
        title={<span style={{ fontSize: "0.95rem", fontWeight: 700, color: theme.text }}>Centro de Custo → Macro Área</span>}
        extra={<span style={{ color: "#6b7fa3", fontSize: "0.78rem" }}>{(data.centro_custo || []).length} mapeamentos</span>}
        style={{ flex: 1, minWidth: 460, borderRadius: 10 }}
        styles={{ body: { padding: 0 } }}
      >
        <Table
          dataSource={(data.centro_custo || []).map((d: any, i: number) => ({ ...d, key: i }))}
          columns={ccCols}
          size="small"
          pagination={{ defaultPageSize: 50, showSizeChanger: true, pageSizeOptions: ["50", "100"] }}
        />
      </Card>

      <Card
        title={<span style={{ fontSize: "0.95rem", fontWeight: 700, color: theme.text }}>Profit Center → Nome</span>}
        extra={<span style={{ color: "#6b7fa3", fontSize: "0.78rem" }}>{(data.profit_center || []).length} mapeamentos</span>}
        style={{ flex: 1, minWidth: 460, borderRadius: 10 }}
        styles={{ body: { padding: 0 } }}
      >
        <Table
          dataSource={(data.profit_center || []).map((d: any, i: number) => ({ ...d, key: i }))}
          columns={pcCols}
          size="small"
          pagination={{ defaultPageSize: 50, showSizeChanger: true, pageSizeOptions: ["50", "100"] }}
        />
      </Card>
    </div>
  );
}

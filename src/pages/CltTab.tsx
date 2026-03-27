import React, { useEffect, useState } from "react";
import { Select, Table } from "antd";
import TableSkeleton from "../components/TableSkeleton";
import { getCltData } from "../api";
import { toTitleCase } from "../utils/format";
import { theme } from "../theme";

const labelStyle: React.CSSProperties = {
  color: theme.text, fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

export default function CltTab() {
  const [meses, setMeses] = useState<string[]>([]);
  const [selMeses, setSelMeses] = useState<string[]>([]);
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCltData({}).then(d => {
      setMeses(d.meses || []);
      setSelMeses(d.meses || []);
      setData(d.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!meses.length) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selMeses.length) params.meses = selMeses.join(",");
    getCltData(params).then(d => { setData(d.data || []); setLoading(false); });
  }, [selMeses, meses]);

  const columns = [
    {
      title: "Empresa",
      dataIndex: "empresa",
      key: "empresa",
      align: "left" as const,
      render: (v: string) => <strong>{toTitleCase(v)}</strong>,
    },
    {
      title: "Totalizador",
      dataIndex: "totalizador",
      key: "totalizador",
      align: "right" as const,
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : theme.text }}>
          {v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      ),
    },
  ];

  return (
    <div>
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={labelStyle}>Mês</div>
          <Select
            mode="multiple"
            style={{ width: "100%" }}
            value={selMeses}
            onChange={setSelMeses}
            options={meses.map(m => ({ label: m, value: m }))}
            maxTagCount="responsive"
          />
        </div>
      </div>

      {loading ? <TableSkeleton rows={8} /> : (
        <Table
          dataSource={data.map((d, i) => ({ ...d, key: i }))}
          columns={columns}
          pagination={false}
          size="small"
          scroll={{ x: "max-content" }}
          rowClassName={(record) => record.empresa === "Total" ? "total-row" : ""}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", maxWidth: 500 }}
        />
      )}
    </div>
  );
}

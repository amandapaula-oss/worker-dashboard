import React, { useEffect, useState } from "react";
import { Select, Table, Spin, message, Button, Breadcrumb } from "antd";
import { HomeOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { getRacFilters, getRacProjetos, getRacPessoas } from "../api";


const labelStyle: React.CSSProperties = {
  color: "#3a4f7a", fontSize: "0.8rem", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 4,
};

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function RacTab() {
  const [filters, setFilters] = useState<{ periodos: string[]; empresas: string[]; tipos: string[] }>({
    periodos: [], empresas: [], tipos: [],
  });
  const [selPeriodos, setSelPeriodos] = useState<string[]>([]);
  const [selEmpresas, setSelEmpresas] = useState<string[]>([]);
  const [selTipos, setSelTipos]       = useState<string[]>([]);
  const [filtersReady, setFiltersReady] = useState(false);

  const [projetos, setProjetos] = useState<any[]>([]);
  const [pessoas, setPessoas]   = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);

  // drill-down state
  const [selectedPep, setSelectedPep] = useState<{ pep: string; nome_cliente: string } | null>(null);

  // load filters
  useEffect(() => {
    getRacFilters()
      .then(f => {
        setFilters(f);
        setSelPeriodos(f.periodos);
        setSelEmpresas(f.empresas);
        setSelTipos(f.tipos);
        setFiltersReady(true);
      })
      .catch(() => { message.error("Erro ao carregar filtros"); setLoading(false); });
  }, []);

  // load projetos
  useEffect(() => {
    if (!filtersReady || selectedPep) return;
    setLoading(true);
    const params: Record<string, string> = {};
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    if (selTipos.length)    params.tipos    = selTipos.join(",");
    getRacProjetos(params)
      .then(d => setProjetos(d))
      .catch(() => message.error("Erro ao carregar projetos"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersReady, selPeriodos, selEmpresas, selTipos, selectedPep]);

  // load pessoas when a project is selected
  useEffect(() => {
    if (!selectedPep) return;
    setLoading(true);
    const params: Record<string, string> = { pep: selectedPep.pep };
    if (selPeriodos.length) params.periodos = selPeriodos.join(",");
    if (selEmpresas.length) params.empresas = selEmpresas.join(",");
    getRacPessoas(params)
      .then(d => setPessoas(d))
      .catch(() => message.error("Erro ao carregar pessoas"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPep, selPeriodos, selEmpresas]);

  const colProjetos = [
    { title: "PEP", dataIndex: "pep", key: "pep", width: 200 },
    { title: "Cliente", dataIndex: "nome_cliente", key: "nome_cliente", ellipsis: true },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130 },
    {
      title: "Valor Líquido",
      dataIndex: "valor_liquido",
      key: "valor_liquido",
      width: 160,
      align: "right" as const,
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>
      ),
    },
  ];

  const colPessoas = [
    { title: "CPF", dataIndex: "cpf", key: "cpf", width: 160 },
    { title: "Nome", dataIndex: "nome", key: "nome", ellipsis: true },
    { title: "Empresa", dataIndex: "empresa", key: "empresa", width: 130 },
    {
      title: "Valor Líquido",
      dataIndex: "valor_liquido",
      key: "valor_liquido",
      width: 160,
      align: "right" as const,
      render: (v: number) => (
        <span style={{ color: v < 0 ? "#c0392b" : "#1a2e5a", fontWeight: 600 }}>{brl(v)}</span>
      ),
    },
  ];

  const totalProjetos = projetos.reduce((s, r) => s + r.valor_liquido, 0);
  const totalPessoas  = pessoas.reduce((s, r) => s + r.valor_liquido, 0);

  const breadcrumb = [
    {
      title: (
        <span style={{ cursor: "pointer", color: "#2d50a0" }} onClick={() => setSelectedPep(null)}>
          <HomeOutlined /> Projetos
        </span>
      ),
    },
    ...(selectedPep ? [{
      title: (
        <span style={{ color: "#1a2e5a", fontWeight: 600 }}>
          {selectedPep.pep} — {selectedPep.nome_cliente}
        </span>
      ),
    }] : []),
  ];

  return (
    <div>
      {/* Filtros */}
      <div style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 10, padding: "0.9rem 1.2rem", marginBottom: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={labelStyle}>Período</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selPeriodos} onChange={v => { setSelPeriodos(v); setSelectedPep(null); }}
            options={filters.periodos.map(p => ({ label: p, value: p }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={labelStyle}>Empresa</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selEmpresas} onChange={v => { setSelEmpresas(v); setSelectedPep(null); }}
            options={filters.empresas.map(e => ({ label: e, value: e }))} maxTagCount="responsive" />
        </div>
        <div style={{ flex: 0, minWidth: 200 }}>
          <div style={labelStyle}>Tipo</div>
          <Select mode="multiple" style={{ width: "100%" }} value={selTipos} onChange={v => { setSelTipos(v); setSelectedPep(null); }}
            options={filters.tipos.map(t => ({ label: t, value: t }))} maxTagCount="responsive" />
        </div>
      </div>

      {/* Breadcrumb */}
      <Breadcrumb items={breadcrumb} style={{ background: "#fff", border: "1px solid #dde3f0", borderRadius: 8, padding: "0.6rem 1rem", marginBottom: 16 }} />

      {loading ? <Spin style={{ display: "block", margin: "2rem auto" }} /> : selectedPep ? (
        <>
          <div style={{ marginBottom: 12 }}>
            <Button icon={<ArrowLeftOutlined />} type="link" style={{ color: "#2d50a0", paddingLeft: 0 }} onClick={() => setSelectedPep(null)}>
              Voltar para projetos
            </Button>
          </div>
          <Table
            dataSource={pessoas.map((d, i) => ({ ...d, key: i }))}
            columns={colPessoas}
            pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
            size="small"
            scroll={{ x: "max-content" }}
            style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
            summary={() => (
              <Table.Summary.Row style={{ background: "#dce6f7", fontWeight: 700 }}>
                <Table.Summary.Cell index={0} colSpan={3}>Total</Table.Summary.Cell>
                <Table.Summary.Cell index={1} align="right">
                  <span style={{ color: totalPessoas < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(totalPessoas)}</span>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            )}
          />
        </>
      ) : (
        <Table
          dataSource={projetos.map((d, i) => ({ ...d, key: i }))}
          columns={colProjetos}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["50","100","200"] }}
          size="small"
          scroll={{ x: "max-content" }}
          style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          onRow={row => ({
            onClick: () => setSelectedPep({ pep: row.pep, nome_cliente: row.nome_cliente }),
            style: { cursor: "pointer" },
          })}
          summary={() => (
            <Table.Summary.Row style={{ background: "#dce6f7", fontWeight: 700 }}>
              <Table.Summary.Cell index={0} colSpan={3}>Total</Table.Summary.Cell>
              <Table.Summary.Cell index={1} align="right">
                <span style={{ color: totalProjetos < 0 ? "#c0392b" : "#1a2e5a" }}>{brl(totalProjetos)}</span>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      )}
    </div>
  );
}

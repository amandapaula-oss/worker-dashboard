import React, { useEffect, useState } from "react";
import { Table, Spin, message, Tag, Progress, Select, Input, Button, Drawer, Descriptions, Divider } from "antd";
import { SearchOutlined, ReloadOutlined, UserOutlined, FilePdfOutlined } from "@ant-design/icons";
import { getApuracaoVisaoMaster, getApuracaoCalcular, downloadApuracaoPdf } from "../api";
import { toTitleCase } from "../utils/format";

const { Option } = Select;

const fmt = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);

const fmtPct = (v: number) => `${(v * 100).toFixed(1)}%`;

type MasterRow = {
  nome: string;
  posicao: string;
  contrato: string;
  vertical: string;
  salario: number;
  bonus: number;
  ating_principal: number;
  mc_gate: number | null;
  tipo_calc: string;
  erro?: string;
};

type DetalheWS = {
  ws: string;
  peso_ws: number;
  budget_rec: number;
  trigger_rec_amount: number;
  real_rec: number;
  receita_faltante: number;
  ating_rec: number;
  budget_mb_pct: number;
  trigger_mb_pct: number;
  real_mb_pct: number;
  mb_faltante: number;
  ating_mb: number;
  mb_gate: number;
  aplica_gate_mb: boolean;
  bonus_rec: number;
  bonus_mb: number;
  bonus_ws: number;
};

type ClienteDetalhe = {
  cliente: string;
  budget_rec: number;
  real_rec: number;
  diferenca: number;
};

type DetalheCalculo = {
  nome: string;
  posicao: string;
  contrato: string;
  salario_q4: number;
  periodo: string;
  bonus_total: number;
  // AE
  peso_receita?: number;
  peso_mb?: number;
  trigger_rec?: number;
  trigger_mb?: number;
  budget_rec_total?: number;
  real_rec_total?: number;
  ating_rec_total?: number;
  budget_mb_pct?: number;
  real_mb_pct?: number;
  ating_mb_total?: number;
  detalhe_ws?: DetalheWS[];
  clientes_detalhe?: ClienteDetalhe[];
  // Diretor
  vertical?: string;
  mc_gate?: number;
  peso_tcv?: number;
  peso_mc?: number;
  budget_tcv_q4?: number;
  real_tcv_q4?: number;
  ating_tcv?: number;
  budget_rec_q4?: number;
  real_rec_q4?: number;
  ating_rec?: number;
  budget_mc_pct?: number;
  real_mc_pct?: number;
  ating_mc?: number;
  bonus_tcv?: number;
  bonus_rec?: number;
  bonus_mc?: number;
};

const posicaoColor: Record<string, string> = {
  DIRETOR: "purple",
  AE: "blue",
  AE2: "cyan",
  HUNTER: "orange",
  ESTRATEGISTAS: "green",
  CS: "gold",
};

const contratoColor: Record<string, string> = {
  CLT: "green",
  PJ: "blue",
  Socio: "purple",
};

export default function VistaMasterTab() {
  const [data, setData] = useState<MasterRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroPos, setFiltroPos] = useState<string>("Todos");
  const [filtroNome, setFiltroNome] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detalhe, setDetalhe] = useState<DetalheCalculo | null>(null);
  const [loadingDetalhe, setLoadingDetalhe] = useState(false);

  const carregar = () => {
    setLoading(true);
    getApuracaoVisaoMaster()
      .then(setData)
      .catch(() => message.error("Erro ao carregar visão master"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const abrirDetalhe = (nome: string) => {
    setDrawerOpen(true);
    setDetalhe(null);
    setLoadingDetalhe(true);
    getApuracaoCalcular(nome)
      .then(setDetalhe)
      .catch(() => message.error("Erro ao carregar detalhe"))
      .finally(() => setLoadingDetalhe(false));
  };

  const filtered = data.filter(r => {
    const posOk = filtroPos === "Todos" || r.posicao.toUpperCase() === filtroPos.toUpperCase();
    const nomeOk = !filtroNome || r.nome.toLowerCase().includes(filtroNome.toLowerCase());
    return posOk && nomeOk;
  });

  const posicoes = ["Todos", ...Array.from(new Set(data.map(r => r.posicao)))];

  const totalBonus = filtered.reduce((s, r) => s + r.bonus, 0);

  const columns = [
    {
      title: "Nome",
      dataIndex: "nome",
      key: "nome",
      render: (v: string) => (
        <span
          style={{ cursor: "pointer", color: "#1677ff", fontWeight: 500 }}
          onClick={() => abrirDetalhe(v)}
        >
          <UserOutlined style={{ marginRight: 6 }} />{toTitleCase(v)}
        </span>
      ),
    },
    {
      title: "Posição",
      dataIndex: "posicao",
      key: "posicao",
      render: (v: string) => <Tag color={posicaoColor[v.toUpperCase()] || "default"}>{v}</Tag>,
    },
    {
      title: "Contrato",
      dataIndex: "contrato",
      key: "contrato",
      render: (v: string) => <Tag color={contratoColor[v] || "default"}>{v}</Tag>,
    },
    {
      title: "Vertical",
      dataIndex: "vertical",
      key: "vertical",
      render: (v: string) => v || "—",
    },
    {
      title: "Salário Q4",
      dataIndex: "salario",
      key: "salario",
      align: "right" as const,
      render: (v: number) => fmt(v),
    },
    {
      title: "Atingimento",
      dataIndex: "ating_principal",
      key: "ating_principal",
      render: (v: number, row: MasterRow) => (
        <div style={{ minWidth: 120 }}>
          <Progress
            percent={Math.round(v * 100)}
            size="small"
            strokeColor={v >= 1 ? "#52c41a" : v >= 0.5 ? "#faad14" : "#ff4d4f"}
            format={p => `${p}%`}
          />
          {row.mc_gate !== null && row.mc_gate === 0 && (
            <Tag color="red" style={{ fontSize: 10, marginTop: 2 }}>MC Gate bloqueado</Tag>
          )}
        </div>
      ),
    },
    {
      title: "Bônus Q4",
      dataIndex: "bonus",
      key: "bonus",
      align: "right" as const,
      sorter: (a: MasterRow, b: MasterRow) => a.bonus - b.bonus,
      render: (v: number, row: MasterRow) => (
        <span style={{ fontWeight: 600, color: v > 0 ? "#52c41a" : row.erro ? "#ff4d4f" : "#999" }}>
          {row.erro ? "Erro" : fmt(v)}
        </span>
      ),
    },
  ];

  return (
    <div style={{ padding: "16px 0" }}>
      {/* Filtros */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder="Buscar por nome..."
          value={filtroNome}
          onChange={e => setFiltroNome(e.target.value)}
          style={{ width: 220 }}
          allowClear
        />
        <Select value={filtroPos} onChange={setFiltroPos} style={{ width: 160 }}>
          {posicoes.map(p => <Option key={p} value={p}>{p}</Option>)}
        </Select>
        <Button icon={<ReloadOutlined />} onClick={carregar} loading={loading}>
          Atualizar
        </Button>
        <div style={{ marginLeft: "auto", fontWeight: 600, fontSize: 15 }}>
          Total bônus filtrado: <span style={{ color: "#52c41a" }}>{fmt(totalBonus)}</span>
        </div>
      </div>

      <Spin spinning={loading}>
        <Table
          dataSource={filtered}
          columns={columns}
          rowKey="nome"
          size="small"
          pagination={false}
          summary={() => (
            <Table.Summary.Row style={{ background: "#fafafa", fontWeight: 600 }}>
              <Table.Summary.Cell index={0} colSpan={4}>Total ({filtered.length} pessoas)</Table.Summary.Cell>
              <Table.Summary.Cell index={4} align="right">
                {fmt(filtered.reduce((s, r) => s + r.salario, 0))}
              </Table.Summary.Cell>
              <Table.Summary.Cell index={5} />
              <Table.Summary.Cell index={6} align="right">
                <span style={{ color: "#52c41a" }}>{fmt(totalBonus)}</span>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      </Spin>

      {/* Drawer de Detalhe */}
      <Drawer
        title={detalhe ? `Memória de Cálculo — ${detalhe.nome}` : "Carregando..."}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={780}
        extra={
          detalhe && (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Tag color="blue" style={{ fontSize: 14 }}>
                Bônus Q4: {fmt(detalhe.bonus_total)}
              </Tag>
              <Button
                type="primary"
                icon={<FilePdfOutlined />}
                size="small"
                onClick={() =>
                  downloadApuracaoPdf(detalhe.nome)
                    .catch(() => message.error("Erro ao gerar PDF"))
                }
              >
                Exportar PDF
              </Button>
            </div>
          )
        }
      >
        {loadingDetalhe && <Spin />}
        {detalhe && !loadingDetalhe && <DetalheDrawer d={detalhe} />}
      </Drawer>
    </div>
  );
}

function DetalheDrawer({ d }: { d: DetalheCalculo }) {
  const isDir = d.posicao === "DIRETOR";

  return (
    <div>
      <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
        <Descriptions.Item label="Posição">{d.posicao}</Descriptions.Item>
        <Descriptions.Item label="Contrato">{d.contrato}</Descriptions.Item>
        <Descriptions.Item label="Salário Q4">{fmt(d.salario_q4)}</Descriptions.Item>
        <Descriptions.Item label="Período">{d.periodo}</Descriptions.Item>
        {isDir && d.vertical && (
          <Descriptions.Item label="Vertical" span={2}>{d.vertical}</Descriptions.Item>
        )}
      </Descriptions>

      {isDir ? <DetalheDir d={d} /> : <DetalheAE d={d} />}

      <Divider />
      <div style={{ textAlign: "right", fontSize: 18, fontWeight: 700, color: "#52c41a" }}>
        Bônus Total Q4: {fmt(d.bonus_total)}
      </div>
    </div>
  );
}

function MetaRealRow({ label, meta, real, ating }: { label: string; meta: number; real: number; ating: number }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", gap: 16, fontSize: 13, marginBottom: 4 }}>
        <span>Meta: <strong>{fmt(meta)}</strong></span>
        <span>Realizado: <strong>{fmt(real)}</strong></span>
      </div>
      <Progress
        percent={Math.min(Math.round(ating * 100), 100)}
        size="small"
        strokeColor={ating >= 1 ? "#52c41a" : ating >= 0.5 ? "#faad14" : "#ff4d4f"}
        format={p => `${p}%`}
      />
    </div>
  );
}

function DetalheAE({ d }: { d: DetalheCalculo }) {
  const triggerRec = d.trigger_rec ?? 0.85;
  const triggerMb  = d.trigger_mb  ?? 0.985;

  return (
    <div>
      {/* ── Regras de Apuração ── */}
      <Divider>Regras de Apuração</Divider>
      <div style={{ background: "#f6f8ff", border: "1px solid #d0d9f0", borderRadius: 8, padding: "10px 14px", fontSize: 13, marginBottom: 4 }}>
        <div style={{ marginBottom: 6 }}>
          <strong>Fórmula:</strong> Bônus = Salário × Peso Métrica × Peso WS × Atingimento
        </div>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 6 }}>
          <span>🎯 <strong>Trigger Receita:</strong> {fmtPct(triggerRec)} da meta — abaixo disso = 0%</span>
          <span>🎯 <strong>Trigger MB% (Apps):</strong> {fmtPct(triggerMb)} da meta — abaixo = bônus MB bloqueado</span>
        </div>
        <div style={{ color: "#555", marginBottom: 6 }}>
          Atingimento entre trigger e 100%: escala linear de 50% a 100%. Acima da meta: 100%.
        </div>
        <div>
          <strong>Pesos desta posição:</strong>&nbsp;
          Receita <Tag color="blue">{fmtPct(d.peso_receita || 0)}</Tag>
          MB% <Tag color="purple">{fmtPct(d.peso_mb || 0)}</Tag>
          Salário Q4 <Tag color="default">{fmt(d.salario_q4)}</Tag>
        </div>
      </div>

      {/* ── Visão Geral ── */}
      <Divider>Visão Geral</Divider>
      <MetaRealRow
        label={`Receita Total (peso ${fmtPct(d.peso_receita || 0)})`}
        meta={d.budget_rec_total || 0}
        real={d.real_rec_total || 0}
        ating={d.ating_rec_total || 0}
      />
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>
          MB% Total — Lucro Bruto (peso {fmtPct(d.peso_mb || 0)})
        </div>
        <div style={{ display: "flex", gap: 16, fontSize: 13, marginBottom: 4, flexWrap: "wrap" }}>
          <span>Meta: <strong>{(d.budget_mb_pct || 0).toFixed(2)}%</strong></span>
          <span style={{ color: "#888" }}>Mínimo Apps (98,5%): <strong>{((d.budget_mb_pct || 0) * (d.trigger_mb ?? 0.985)).toFixed(2)}%</strong></span>
          <span>Realizado: <strong style={{ color: (d.real_mb_pct || 0) >= (d.budget_mb_pct || 0) * (d.trigger_mb ?? 0.985) ? "#52c41a" : "#ff4d4f" }}>{(d.real_mb_pct || 0).toFixed(2)}%</strong></span>
        </div>
        <Progress
          percent={Math.min(Math.round((d.ating_mb_total || 0) * 100), 100)}
          size="small"
          strokeColor={(d.ating_mb_total || 0) >= 1 ? "#52c41a" : "#faad14"}
        />
      </div>

      {/* ── Detalhe por Workstream ── */}
      {d.detalhe_ws && d.detalhe_ws.length > 0 && (
        <>
          <Divider>Detalhe por Workstream</Divider>
          <Table
            size="small"
            pagination={false}
            dataSource={d.detalhe_ws}
            rowKey="ws"
            scroll={{ x: "max-content" }}
            columns={[
              { title: "WS", dataIndex: "ws", width: 70, render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
              { title: "Peso WS", dataIndex: "peso_ws", width: 80, render: (v: number) => fmtPct(v) },
              { title: "Meta", dataIndex: "budget_rec", width: 130, align: "right" as const, render: (v: number) => fmt(v) },
              {
                title: "Mínimo p/ pontuar",
                dataIndex: "trigger_rec_amount",
                width: 140,
                align: "right" as const,
                render: (v: number) => <span style={{ color: "#888" }}>{fmt(v ?? 0)}</span>,
              },
              {
                title: "Realizado",
                dataIndex: "real_rec",
                width: 130,
                align: "right" as const,
                render: (v: number, row: DetalheWS) => (
                  <span style={{ color: v >= (row.trigger_rec_amount ?? 0) ? "#52c41a" : "#ff4d4f", fontWeight: 600 }}>
                    {fmt(v)}
                  </span>
                ),
              },
              {
                title: "Falta p/ mínimo",
                dataIndex: "receita_faltante",
                width: 130,
                align: "right" as const,
                render: (v: number) =>
                  v > 0
                    ? <Tag color="red" style={{ fontWeight: 600 }}>{fmt(v)}</Tag>
                    : <Tag color="green">✓ Atingido</Tag>,
              },
              {
                title: "Ating. Rec.",
                dataIndex: "ating_rec",
                width: 80,
                render: (v: number) => (
                  <span style={{ color: v >= 1 ? "#52c41a" : v > 0 ? "#faad14" : "#ff4d4f", fontWeight: 600 }}>
                    {fmtPct(v)}
                  </span>
                ),
              },
              {
                title: "MB% Meta",
                dataIndex: "budget_mb_pct",
                width: 90,
                align: "right" as const,
                render: (v: number) => `${v.toFixed(2)}%`,
              },
              {
                title: "MB% Mínimo",
                dataIndex: "trigger_mb_pct",
                width: 100,
                align: "right" as const,
                render: (v: number, row: DetalheWS) =>
                  row.aplica_gate_mb
                    ? <span style={{ color: "#888" }}>{v.toFixed(2)}%</span>
                    : <span style={{ color: "#bbb" }}>—</span>,
              },
              {
                title: "MB% Real",
                dataIndex: "real_mb_pct",
                width: 90,
                align: "right" as const,
                render: (v: number, row: DetalheWS) => (
                  <span style={{
                    color: !row.aplica_gate_mb || v >= row.trigger_mb_pct ? "#52c41a" : "#ff4d4f",
                    fontWeight: 600,
                  }}>
                    {v.toFixed(2)}%
                  </span>
                ),
              },
              {
                title: "Gate MB",
                dataIndex: "mb_gate",
                width: 90,
                render: (_: number, row: DetalheWS) =>
                  !row.aplica_gate_mb
                    ? <Tag color="default">N/A</Tag>
                    : row.mb_gate === 1
                    ? <Tag color="green">✓ OK</Tag>
                    : <Tag color="red">✗ Bloqueado</Tag>,
              },
              {
                title: "Bônus WS",
                dataIndex: "bonus_ws",
                width: 120,
                align: "right" as const,
                render: (v: number) => <strong style={{ color: v > 0 ? "#52c41a" : "#999" }}>{fmt(v)}</strong>,
              },
            ]}
          />
        </>
      )}

      {/* ── Carteira de Clientes ── */}
      {d.clientes_detalhe && d.clientes_detalhe.length > 0 && (
        <>
          <Divider>Carteira de Clientes</Divider>
          <Table
            size="small"
            pagination={false}
            dataSource={d.clientes_detalhe}
            rowKey="cliente"
            columns={[
              {
                title: "Cliente",
                dataIndex: "cliente",
                render: (v: string) => <strong>{toTitleCase(v)}</strong>,
              },
              {
                title: "Budget Q4",
                dataIndex: "budget_rec",
                align: "right" as const,
                render: (v: number) => fmt(v),
              },
              {
                title: "Realizado",
                dataIndex: "real_rec",
                align: "right" as const,
                render: (v: number, row: ClienteDetalhe) => (
                  <span style={{
                    color: v >= row.budget_rec ? "#52c41a" : v >= row.budget_rec * triggerRec ? "#faad14" : "#ff4d4f",
                    fontWeight: 600,
                  }}>
                    {fmt(v)}
                  </span>
                ),
              },
              {
                title: "vs Budget",
                dataIndex: "diferenca",
                align: "right" as const,
                render: (v: number) => (
                  <span style={{ color: v >= 0 ? "#52c41a" : "#ff4d4f" }}>
                    {v >= 0 ? "+" : ""}{fmt(v)}
                  </span>
                ),
              },
            ]}
            summary={rows => {
              const totalBgt  = (rows as ClienteDetalhe[]).reduce((s, r) => s + r.budget_rec, 0);
              const totalReal = (rows as ClienteDetalhe[]).reduce((s, r) => s + r.real_rec, 0);
              const totalDif  = totalReal - totalBgt;
              return (
                <Table.Summary.Row style={{ fontWeight: 700, background: "#f0f4ff" }}>
                  <Table.Summary.Cell index={0}>Total</Table.Summary.Cell>
                  <Table.Summary.Cell index={1} align="right">{fmt(totalBgt)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={2} align="right"><span style={{ color: totalReal >= totalBgt ? "#52c41a" : "#ff4d4f" }}>{fmt(totalReal)}</span></Table.Summary.Cell>
                  <Table.Summary.Cell index={3} align="right"><span style={{ color: totalDif >= 0 ? "#52c41a" : "#ff4d4f" }}>{totalDif >= 0 ? "+" : ""}{fmt(totalDif)}</span></Table.Summary.Cell>
                </Table.Summary.Row>
              );
            }}
          />
        </>
      )}
    </div>
  );
}

function DetalheDir({ d }: { d: DetalheCalculo }) {
  const gate = d.mc_gate === 1;
  return (
    <div>
      {!gate && (
        <Tag color="red" style={{ marginBottom: 12, fontSize: 13 }}>
          Gatilho MC não atingido — sem apuração de Receita e TCV
        </Tag>
      )}
      <Divider >TCV (peso {fmtPct(d.peso_tcv || 0)})</Divider>
      <div style={{ fontSize: 13, marginBottom: 8, color: "#888" }}>
        * TCV realizado requer base Salesforce (não disponível)
      </div>
      <MetaRealRow label="TCV" meta={d.budget_tcv_q4 || 0} real={d.real_tcv_q4 || 0} ating={d.ating_tcv || 0} />

      <Divider >Receita (peso {fmtPct(d.peso_receita || 0)})</Divider>
      <MetaRealRow label="Receita" meta={d.budget_rec_q4 || 0} real={d.real_rec_q4 || 0} ating={d.ating_rec || 0} />

      <Divider >MC% (peso {fmtPct(d.peso_mc || 0)}) — Gatilho Mestre</Divider>
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 16, fontSize: 13, marginBottom: 4 }}>
          <span>Meta: <strong>{(d.budget_mc_pct || 0).toFixed(2)}%</strong></span>
          <span>Realizado: <strong>{(d.real_mc_pct || 0).toFixed(2)}%</strong></span>
          <Tag color={gate ? "green" : "red"}>{gate ? "Gate OK" : "Gate BLOQUEADO"}</Tag>
        </div>
        <Progress
          percent={Math.min(Math.round((d.ating_mc || 0) * 100), 100)}
          strokeColor={(d.ating_mc || 0) >= 1 ? "#52c41a" : "#faad14"}
        />
      </div>

      <Divider >Bônus por Componente</Divider>
      <Table
        size="small"
        pagination={false}
        dataSource={[
          { meta: "TCV", peso: fmtPct(d.peso_tcv || 0), ating: fmtPct(d.ating_tcv || 0), bonus: d.bonus_tcv || 0 },
          { meta: "Receita", peso: fmtPct(d.peso_receita || 0), ating: fmtPct(d.ating_rec || 0), bonus: d.bonus_rec || 0 },
          { meta: "MC%", peso: fmtPct(d.peso_mc || 0), ating: fmtPct(d.ating_mc || 0), bonus: d.bonus_mc || 0 },
        ]}
        rowKey="meta"
        columns={[
          { title: "Métrica", dataIndex: "meta" },
          { title: "Peso", dataIndex: "peso" },
          { title: "Atingimento", dataIndex: "ating" },
          { title: "Bônus", dataIndex: "bonus", render: v => <strong style={{ color: "#52c41a" }}>{fmt(v)}</strong> },
        ]}
      />
    </div>
  );
}


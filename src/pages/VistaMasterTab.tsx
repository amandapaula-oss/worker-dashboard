import React, { useEffect, useRef, useState } from "react";
import { Table, Spin, message, Tag, Select, Input, Button, Drawer, Descriptions, Divider } from "antd";
import { SearchOutlined, ReloadOutlined, UserOutlined, PrinterOutlined, CheckCircleFilled, CloseCircleFilled } from "@ant-design/icons";
import { useReactToPrint } from "react-to-print";
import { getApuracaoVisaoMaster, getApuracaoVisaoMasterQ3, getApuracaoCalcular, getApuracaoCalcularQ3 } from "../api";
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
  ating_rec: number | null;
  ating_mb: number | null;
  ating_tcv: number | null;
  ating_mc: number | null;
  pct_rec: number | null;
  pct_mb: number | null;
  pct_tcv: number | null;
  pct_mc: number | null;
  mc_gate: number | null;
  gate_ok: boolean;
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
  real_lb_financeiro?: number;
  clientes_ws?: Array<{ cliente: string; budget_rec: number; real_rec: number }>;
};

type ClienteDetalhe = {
  cliente: string;
  budget_rec: number;
  real_rec: number;
  real_custo?: number;
  real_lb?: number;
  margem_pct?: number | null;
};

type DetalheCalculo = {
  nome: string;
  posicao: string;
  contrato: string;
  salario_q4: number;
  periodo: string;
  bonus_total: number;
  // AE / Comercial
  peso_receita?: number;
  peso_mb?: number;
  trigger_rec?: number;
  trigger_mb_pct_total?: number;
  lb_gate?: number;
  meta_lb_q4?: number;
  trigger_lb_q4?: number;
  real_lb_total?: number;
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
  budget_lb_q4?: number;
  real_rec_q4?: number;
  real_rec_sap?: number;
  real_lb_q4?: number;
  ating_rec?: number;
  budget_mc_pct?: number;
  trigger_mc_pct?: number;
  real_mc_pct?: number;
  budget_mc_abs?: number;
  trigger_mc_abs?: number;
  real_mc_abs?: number;
  ating_mc?: number;
  bonus_tcv?: number;
  bonus_rec?: number;
  bonus_mc?: number;
  // Breakdown MC% (nexus)
  real_gross_rev?: number;
  real_payroll?: number;
  real_third_party?: number;
  real_other_costs?: number;
  real_payroll_exp?: number;
  real_deductions?: number;
  bgt_gross_rev?: number;
  bgt_payroll?: number;
  bgt_third_party?: number;
  bgt_other_costs?: number;
  bgt_payroll_exp?: number;
  bgt_deductions?: number;
  real_despesa_pessoas?: number;
};

const posicaoColor: Record<string, string> = {
  DIRETOR: "purple",
  AE: "blue",
  AE_GM: "geekblue",
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

// ─── Custom Achievement Bar ───────────────────────────────────────────────────

const fmtShort = (v: number) =>
  v >= 1000 ? `R$${Math.round(v / 1000)}k` : `R$${Math.round(v)}`;

function AchievementBar({ meta, trigger, realizado, bonusAtMaxAting }: {
  meta: number; trigger: number; realizado: number; bonusAtMaxAting?: number;
}) {
  const effectiveMeta = meta > 0 ? meta : trigger + 1;
  const spread = effectiveMeta - trigger || 1;
  // O início da barra é o menor entre realizado e trigger
  const leftAnchor = Math.min(realizado, trigger);
  const visMin = leftAnchor - spread * 0.04;
  const visMax = effectiveMeta + spread * 0.14;
  const range = visMax - visMin || 1;

  const toPos = (v: number) => Math.min(Math.max((v - visMin) / range * 100, 0), 100);

  const triggerPos = toPos(trigger);
  const realizadoPos = toPos(realizado);
  const hitTrigger = realizado >= trigger;

  // Ticks at 60%, 70%, 80%, 90%, 100% ating
  const ticks = effectiveMeta > trigger
    ? [0.6, 0.7, 0.8, 0.9, 1.0].map(ating => ({
        ating,
        pos: toPos(trigger + spread * (ating - 0.5) / 0.5),
        bonus: bonusAtMaxAting != null ? bonusAtMaxAting * ating : null,
      }))
    : [];

  return (
    <div style={{ position: "relative", height: bonusAtMaxAting != null ? 76 : 60, userSelect: "none" }}>
      {/* Track — starts at trigger */}
      <div style={{ position: "absolute", left: `${triggerPos}%`, right: 0, top: 22, height: 10, background: "#f0f0f0", borderRadius: 5 }} />

      {/* Fill: trigger → realizado (green) */}
      {hitTrigger && realizadoPos > triggerPos && (
        <div style={{
          position: "absolute", left: `${triggerPos}%`,
          width: `${Math.min(realizadoPos - triggerPos, 100 - triggerPos)}%`,
          top: 22, height: 10, background: "#52c41a", borderRadius: "5px 0 0 5px",
        }} />
      )}

      {/* Fill: below trigger (red) */}
      {!hitTrigger && (
        <div style={{
          position: "absolute", left: `${triggerPos}%`,
          width: `${Math.max(0, realizadoPos - triggerPos)}%`,
          top: 22, height: 10, background: "#ff7875", borderRadius: "5px 0 0 5px",
        }} />
      )}

      {/* Earning ticks */}
      {ticks.map(t => (
        <React.Fragment key={t.ating}>
          <div style={{
            position: "absolute", left: `${t.pos}%`, top: 20, width: t.ating === 1.0 ? 2 : 1, height: 14,
            background: t.ating === 1.0 ? "#1677ff80" : "rgba(0,0,0,0.12)",
            transform: "translateX(-50%)",
          }} />
          <div style={{
            position: "absolute", left: `${t.pos}%`, top: 36,
            fontSize: 9, color: t.ating === 1.0 ? "#1677ff" : "#bbb",
            transform: "translateX(-50%)", whiteSpace: "nowrap", textAlign: "center",
          }}>
            {Math.round(t.ating * 100)}%
            {t.bonus != null && <><br />{fmtShort(t.bonus)}</>}
          </div>
        </React.Fragment>
      ))}

      {/* Trigger marker */}
      <div style={{
        position: "absolute", left: `${triggerPos}%`, top: 18, width: 2, height: 18,
        background: "#ff4d4f", transform: "translateX(-50%)",
      }} />
      <div style={{
        position: "absolute", left: `${triggerPos}%`, top: 7, fontSize: 9, color: "#ff4d4f",
        transform: "translateX(-50%)", whiteSpace: "nowrap",
      }}>
        mín
      </div>

      {/* Realizado dot */}
      <div style={{
        position: "absolute", left: `${realizadoPos}%`, top: 19,
        width: 12, height: 12, borderRadius: "50%",
        background: hitTrigger ? "#52c41a" : "#ff4d4f",
        border: "2px solid #fff", boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
        transform: "translateX(-50%)",
      }} />
      <div style={{
        position: "absolute", left: `${realizadoPos}%`, top: 33,
        fontSize: 9, color: hitTrigger ? "#52c41a" : "#ff4d4f",
        transform: "translateX(-50%)", whiteSpace: "nowrap", fontWeight: 600,
      }}>
        Realizado
      </div>
    </div>
  );
}

// ─── MetaRealRow (currency) ───────────────────────────────────────────────────

function MetaRealRow({ label, meta, triggerAmt, real, ating, gate, bonusAtMaxAting, showBar = false }: {
  label: string; meta: number; triggerAmt: number; real: number; ating: number; gate?: boolean; bonusAtMaxAting?: number; showBar?: boolean;
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", gap: 20, fontSize: 13, marginBottom: 6, flexWrap: "wrap", alignItems: "center" }}>
        <span>Meta: <strong>{fmt(meta)}</strong></span>
        <span style={{ color: "#888" }}>Mín.: <strong>{fmt(triggerAmt)}</strong></span>
        <span>Realizado: <strong style={{ color: real >= meta ? "#52c41a" : real >= triggerAmt ? "#faad14" : "#ff4d4f" }}>{fmt(real)}</strong></span>
        <span style={{ fontWeight: 700, color: ating >= 1 ? "#52c41a" : ating > 0 ? "#faad14" : "#ff4d4f" }}>
          {fmtPct(ating)}
        </span>
        {gate !== undefined && (
          <Tag color={gate ? "green" : "red"}>{gate ? "✓ Gate OK" : "✗ Bloqueado"}</Tag>
        )}
      </div>
      {showBar && <AchievementBar meta={meta} trigger={triggerAmt} realizado={real} bonusAtMaxAting={bonusAtMaxAting} />}
    </div>
  );
}

// ─── MetaRealPctRow (percentage) ─────────────────────────────────────────────

function MetaRealPctRow({ label, meta, trigger, real, ating, gate, bonusAtMaxAting, showBar = false }: {
  label: string; meta: number; trigger: number; real: number; ating: number; gate?: boolean; bonusAtMaxAting?: number; showBar?: boolean;
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", gap: 16, fontSize: 13, marginBottom: 6, flexWrap: "wrap", alignItems: "center" }}>
        <span>Meta: <strong>{meta.toFixed(2)}%</strong></span>
        <span style={{ color: "#888" }}>Mín.: <strong>{trigger.toFixed(2)}%</strong></span>
        <span>Realizado: <strong style={{ color: real >= meta ? "#52c41a" : real >= trigger ? "#faad14" : "#ff4d4f" }}>{real.toFixed(2)}%</strong></span>
        <span style={{ fontWeight: 700, color: ating >= 1 ? "#52c41a" : ating > 0 ? "#faad14" : "#ff4d4f" }}>{fmtPct(ating)}</span>
        {gate !== undefined && (
          <Tag color={gate ? "green" : "red"}>{gate ? "✓ Gate OK" : "✗ Bloqueado"}</Tag>
        )}
      </div>
      {showBar && <AchievementBar meta={meta} trigger={trigger} realizado={real} bonusAtMaxAting={bonusAtMaxAting} />}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function VistaMasterTab() {
  const [data, setData] = useState<MasterRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroPos, setFiltroPos] = useState<string>("Todos");
  const [filtroNome, setFiltroNome] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detalhe, setDetalhe] = useState<DetalheCalculo | null>(null);
  const [loadingDetalhe, setLoadingDetalhe] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);
  const handlePrint = useReactToPrint({ contentRef: printRef, documentTitle: detalhe ? `Memória de Cálculo — ${detalhe.nome}` : "Memória de Cálculo" });

  const carregar = () => {
    setLoading(true);
    getApuracaoVisaoMaster()
      .then(setData)
      .catch(() => message.error("Erro ao carregar visão master"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const abrirDetalhe = (nome: string, posicao?: string) => {
    void posicao;
    setDrawerOpen(true);
    setDetalhe(null);
    setLoadingDetalhe(true);
    getApuracaoCalcular(nome)
      .then((d: DetalheCalculo) => setDetalhe(d))
      .catch((e: Error) => message.error(`Erro: ${e.message}`, 10))
      .finally(() => setLoadingDetalhe(false));
  };

  const filtered = data.filter(r => {
    const posOk = filtroPos === "Todos" || r.posicao.toUpperCase() === filtroPos.toUpperCase();
    const nomeOk = !filtroNome || r.nome.toLowerCase().includes(filtroNome.toLowerCase());
    return posOk && nomeOk;
  });

  const posicoes = ["Todos", ...Array.from(new Set(data.map(r => r.posicao)))];
  const totalBonus = filtered.reduce((s, r) => s + r.bonus, 0);

  const atCol = (v: number | null) => {
    if (v == null) return <span style={{ color: "#ccc" }}>—</span>;
    return (
      <span style={{ color: v >= 1 ? "#52c41a" : v > 0 ? "#faad14" : "#ff4d4f", fontWeight: 600 }}>
        {fmtPct(v)}
      </span>
    );
  };

  const columns = [
    {
      title: "Nome",
      dataIndex: "nome",
      key: "nome",
      render: (v: string, record: MasterRow) => (
        <span style={{ cursor: "pointer", color: "#1677ff", fontWeight: 500 }} onClick={() => abrirDetalhe(v, record.posicao)}>
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
      title: "Vertical",
      dataIndex: "vertical",
      key: "vertical",
      render: (v: string) => v || "—",
    },
    {
      title: "Gatilho Mestre",
      key: "gate_ok",
      render: (_: any, row: MasterRow) => (
        <div style={{ textAlign: "center" }}>
          {row.gate_ok
            ? <CheckCircleFilled style={{ color: "#52c41a", fontSize: 18 }} />
            : <CloseCircleFilled style={{ color: "#ff4d4f", fontSize: 18 }} />
          }
          <div style={{ fontSize: 10, color: "#888", marginTop: 2 }}>
            {row.tipo_calc === "Diretor" ? "MC%" : "LB R$"}
          </div>
        </div>
      ),
    },
    {
      title: "% TCV",
      key: "pct_tcv",
      render: (_: any, row: MasterRow) => atCol(row.pct_tcv),
    },
    {
      title: "% Receita",
      key: "pct_rec",
      render: (_: any, row: MasterRow) => atCol(row.pct_rec),
    },
    {
      title: "% MB/MC",
      key: "pct_mb",
      render: (_: any, row: MasterRow) => atCol(row.pct_mb ?? row.pct_mc),
    },
    {
      title: "Contrato",
      dataIndex: "contrato",
      key: "contrato",
      render: (v: string) => <Tag color={contratoColor[v] || "default"}>{v}</Tag>,
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
              <Table.Summary.Cell index={0} colSpan={7}>Total ({filtered.length} pessoas)</Table.Summary.Cell>
              <Table.Summary.Cell index={7} />
              <Table.Summary.Cell index={8} align="right">
                <span style={{ color: "#52c41a" }}>{fmt(totalBonus)}</span>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      </Spin>

      <Drawer
        title={detalhe ? `Memória de Cálculo — ${detalhe.nome}` : "Carregando..."}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={820}
        extra={
          detalhe && (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Tag color="blue" style={{ fontSize: 14 }}>
                Bônus Q4: {fmt(detalhe.bonus_total)}
              </Tag>
              <Button
                type="primary"
                icon={<PrinterOutlined />}
                size="small"
                onClick={() => handlePrint()}
              >
                Imprimir / PDF
              </Button>
            </div>
          )
        }
      >
        {loadingDetalhe && <Spin />}
        {detalhe && !loadingDetalhe && (
          <div ref={printRef} style={{ padding: 8 }}>
            <h2 style={{ marginBottom: 16, fontSize: 18, fontWeight: 700, color: "#1a2e5a" }}>
              Memória de Cálculo — {detalhe.nome} &nbsp;<span style={{ fontSize: 13, fontWeight: 400, color: "#888" }}>Q4 2025</span>
            </h2>
            <DetalheDrawer d={detalhe} />
          </div>
        )}
      </Drawer>
    </div>
  );
}

// ─── Drawer container ─────────────────────────────────────────────────────────

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
        Bônus Total {d.periodo || "Q4"}: {fmt(d.bonus_total)}
      </div>

    </div>
  );
}

// ─── Q3 Drawer container (apenas AE_GM) ──────────────────────────────────────

function DetalheDrawerQ3({ d }: { d: DetalheCalculo }) {
  return (
    <div>
      <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
        <Descriptions.Item label="Posição">{d.posicao}</Descriptions.Item>
        <Descriptions.Item label="Contrato">{d.contrato}</Descriptions.Item>
        <Descriptions.Item label="Salário Q3">{fmt(d.salario_q4)}</Descriptions.Item>
        <Descriptions.Item label="Período">{d.periodo}</Descriptions.Item>
      </Descriptions>
      <DetalheAE d={d} periodoLabel="Q3" />
      <Divider />
      <div style={{ textAlign: "right", fontSize: 18, fontWeight: 700, color: "#52c41a" }}>
        Bônus Total Q3: {fmt(d.bonus_total)}
      </div>
    </div>
  );
}

// ─── Detalhe AE / Comercial ───────────────────────────────────────────────────

function DetalheAE({ d, periodoLabel = "Q4" }: { d: DetalheCalculo; periodoLabel?: string }) {
  const triggerRec = d.trigger_rec ?? 0.85;
  const triggerMbPctTotal = d.trigger_mb_pct_total ?? ((d.budget_mb_pct ?? 0) - 1.5);
  const lbGateOk = (d.lb_gate ?? 1) === 1;

  return (
    <div>
      <ResultadoBox bonusTotal={d.bonus_total ?? 0} salario={d.salario_q4 ?? 0} periodo={d.periodo} />
      {/* ── Gatilho Mestre ── */}
      <Divider>Gatilho Mestre — Lucro Bruto (R$)</Divider>
      <div style={{
        background: lbGateOk ? "#f6ffed" : "#fff2f0",
        border: `1px solid ${lbGateOk ? "#b7eb8f" : "#ffccc7"}`,
        borderRadius: 8, padding: "10px 16px", marginBottom: 12,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
          {lbGateOk
            ? <CheckCircleFilled style={{ color: "#52c41a", fontSize: 22 }} />
            : <CloseCircleFilled style={{ color: "#ff4d4f", fontSize: 22 }} />
          }
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: lbGateOk ? "#52c41a" : "#ff4d4f" }}>
              {lbGateOk ? "Gatilho atingido" : "Gatilho NÃO atingido"}
            </div>
            <div style={{ fontSize: 12, color: "#666" }}>
              {lbGateOk
                ? "Lucro Bruto acima do mínimo — bônus habilitado"
                : "Lucro Bruto abaixo do mínimo — bônus bloqueado"}
            </div>
          </div>
        </div>
        {(d.meta_lb_q4 ?? 0) > 0 && (
          <MetaRealRow
            label={`Lucro Bruto ${periodoLabel}`}
            meta={d.meta_lb_q4 || 0}
            triggerAmt={d.trigger_lb_q4 || 0}
            real={d.real_lb_total || 0}
            showBar={true}
            ating={d.real_lb_total != null && d.trigger_lb_q4 != null && d.meta_lb_q4 != null
              ? (d.real_lb_total >= d.meta_lb_q4 ? 1
                : d.real_lb_total < d.trigger_lb_q4 ? 0
                : (d.real_lb_total - d.trigger_lb_q4) / (d.meta_lb_q4 - d.trigger_lb_q4) * 0.5 + 0.5)
              : 0}
          />
        )}
      </div>

      {/* ── Regras de Apuração ── */}
      <Divider>Regras de Apuração</Divider>
      <div style={{ background: "#f6f8ff", border: "1px solid #d0d9f0", borderRadius: 8, padding: "10px 14px", fontSize: 13, marginBottom: 4 }}>
        <div style={{ marginBottom: 6 }}>
          <strong>Fórmula:</strong> Bônus = Salário × Peso Métrica × Peso WS × Atingimento
        </div>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 6 }}>
          <span>🎯 <strong>Trigger Receita:</strong> {(triggerRec * 100).toFixed(0)}% da meta — abaixo disso = 0</span>
          <span>🎯 <strong>Gatilho Mestre:</strong> Lucro Bruto ≥ mínimo da planilha — abaixo disso = 0</span>
        </div>
        <div style={{ color: "#555", marginBottom: 6 }}>
          Atingimento entre trigger e meta: escala linear de 50% a 100%. Acima da meta: 100%.
        </div>
        <div>
          <strong>Pesos desta posição:</strong>&nbsp;
          {(d.peso_tcv || 0) > 0 && <>TCV Área <Tag color="geekblue">{fmtPct(d.peso_tcv || 0)}</Tag></>}
          Receita <Tag color="blue">{fmtPct(d.peso_receita || 0)}</Tag>
          MB% <Tag color="purple">{fmtPct(d.peso_mb || 0)}</Tag>
          Salário Q4 <Tag color="default">{fmt(d.salario_q4)}</Tag>
        </div>
      </div>

      {/* ── Visão Geral ── */}
      <Divider>Visão Geral</Divider>
      {(d.peso_tcv || 0) > 0 && (
        <MetaRealRow
          label={`TCV Área Grupo Mult (peso ${fmtPct(d.peso_tcv || 0)})`}
          meta={d.budget_tcv_q4 || 0}
          triggerAmt={(d.budget_tcv_q4 || 0) * (d.trigger_rec || 0.85)}
          real={d.real_tcv_q4 || 0}
          ating={d.ating_tcv || 0}
          bonusAtMaxAting={d.salario_q4 * (d.peso_tcv || 0)}
        />
      )}
      <MetaRealRow
        label={`Receita Total (peso ${fmtPct(d.peso_receita || 0)})`}
        meta={d.budget_rec_total || 0}
        triggerAmt={(d.budget_rec_total || 0) * triggerRec}
        real={d.real_rec_total || 0}
        ating={d.ating_rec_total || 0}
        bonusAtMaxAting={d.salario_q4 * (d.peso_receita || 0)}
      />
      <MetaRealPctRow
        label={`MB% Total (peso ${fmtPct(d.peso_mb || 0)})`}
        meta={d.budget_mb_pct || 0}
        trigger={triggerMbPctTotal}
        real={d.real_mb_pct || 0}
        ating={d.ating_mb_total || 0}
        gate={lbGateOk}
        bonusAtMaxAting={d.salario_q4 * (d.peso_mb || 0)}
      />

      {/* ── Tabela de Cálculo do Bônus ── */}
      {d.detalhe_ws && d.detalhe_ws.length > 0 && (
        <>
          <Divider>Cálculo do Bônus por WS</Divider>
          <Table
            size="small"
            pagination={false}
            dataSource={d.detalhe_ws.map(w => ({
              key: w.ws,
              ws: w.ws === "cloud" ? "CLOUD/CYBER" : w.ws.toUpperCase(),
              peso_ws: w.peso_ws,
              rec_meta: w.budget_rec,
              rec_real: w.real_rec,
              mb_meta: w.budget_mb_pct,
              mb_real: w.real_mb_pct,
              lb_meta: w.budget_rec * w.budget_mb_pct / 100,
              lb_real: w.real_lb_financeiro ?? (w.real_rec * w.real_mb_pct / 100),
            }))}
            summary={() => {
              const ws = d.detalhe_ws!;
              const totRecMeta = ws.reduce((s, w) => s + w.budget_rec, 0);
              const totRecReal = ws.reduce((s, w) => s + w.real_rec, 0);
              const totLbMeta  = ws.reduce((s, w) => s + w.budget_rec * w.budget_mb_pct / 100, 0);
              const totLbReal  = ws.reduce((s, w) => s + (w.real_lb_financeiro ?? w.real_rec * w.real_mb_pct / 100), 0);
              const mbMetaTot  = totRecMeta > 0 ? totLbMeta / totRecMeta * 100 : 0;
              const mbRealTot  = totRecReal > 0 ? totLbReal / totRecReal * 100 : 0;
              return (
                <Table.Summary.Row style={{ fontWeight: 700, background: "#f0f4ff" }}>
                  <Table.Summary.Cell index={0}>Total</Table.Summary.Cell>
                  <Table.Summary.Cell index={1} />
                  <Table.Summary.Cell index={2} align="right">{fmt(totRecMeta)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={3} align="right">
                    <span style={{ color: totRecReal >= totRecMeta ? "#52c41a" : "#ff4d4f" }}>{fmt(totRecReal)}</span>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right">{mbMetaTot.toFixed(1)}%</Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right">
                    <span style={{ color: mbRealTot >= mbMetaTot ? "#52c41a" : "#ff4d4f" }}>{mbRealTot.toFixed(1)}%</span>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={6} align="right">{fmt(totLbMeta)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={7} align="right">
                    <span style={{ color: totLbReal >= totLbMeta ? "#52c41a" : "#ff4d4f" }}>{fmt(totLbReal)}</span>
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              );
            }}
            columns={[
              { title: "WS", dataIndex: "ws", width: 60 },
              { title: "Peso", dataIndex: "peso_ws", width: 60, render: (v: number) => fmtPct(v) },
              {
                title: "Receita",
                children: [
                  { title: "Meta", dataIndex: "rec_meta", align: "right" as const, render: (v: number) => fmt(v) },
                  { title: "Realizado", dataIndex: "rec_real", align: "right" as const,
                    render: (v: number, row: any) => <span style={{ color: v >= row.rec_meta ? "#52c41a" : v > 0 ? "#faad14" : "#ff4d4f", fontWeight: 600 }}>{fmt(v)}</span> },
                ],
              },
              {
                title: "MB%",
                children: [
                  { title: "Meta", dataIndex: "mb_meta", align: "right" as const, render: (v: number) => `${v.toFixed(1)}%` },
                  { title: "Realizado", dataIndex: "mb_real", align: "right" as const,
                    render: (v: number, row: any) => <span style={{ color: v >= row.mb_meta ? "#52c41a" : "#faad14", fontWeight: 600 }}>{v.toFixed(1)}%</span> },
                ],
              },
              {
                title: "LB",
                children: [
                  { title: "Meta", dataIndex: "lb_meta", align: "right" as const, render: (v: number) => v ? fmt(v) : <span style={{ color: "#ccc" }}>—</span> },
                  { title: "Realizado", dataIndex: "lb_real", align: "right" as const,
                    render: (v: number, row: any) => <span style={{ color: v >= row.lb_meta ? "#52c41a" : v > 0 ? "#faad14" : "#ff4d4f", fontWeight: 600 }}>{v ? fmt(v) : "—"}</span> },
                ],
              },
            ]}
          />

          {/* ── Cálculo detalhado por WS ── */}
          <Divider plain>Cálculo do Bônus por WS</Divider>
          <div style={{ background: "#f8f9ff", border: "1px solid #d0d9f0", borderRadius: 8, padding: "10px 14px", marginBottom: 16, fontSize: 13 }}>
            <div style={{ marginBottom: 8, color: "#666" }}>
              <strong>Fórmula:</strong> Bônus Rec. = Salário × Peso Rec. × Peso WS × Ating. Rec.
              &nbsp;&nbsp;|&nbsp;&nbsp;
              Bônus MB% = Salário × Peso MB% × Peso WS × Ating. MB% {d.detalhe_ws.some(w => w.aplica_gate_mb) ? "× Gate MB" : ""}
            </div>
            {d.detalhe_ws.filter(w => w.budget_rec > 0).map(w => {
              const wsLabel = w.ws === "cloud" ? "CLOUD/CYBER" : w.ws.toUpperCase();
              const sal = d.salario_q4;
              const pRec = d.peso_receita || 0;
              const pMb  = (d as any).peso_mb || 0;
              const lbGate = (w as any).lb_gate_ws ?? 1;
              const bRec = sal * pRec * w.peso_ws * (w.ating_rec ?? 0) * lbGate;
              const gate = w.aplica_gate_mb ? (w.mb_gate ?? 1) : 1;
              const bMb  = sal * pMb  * w.peso_ws * (w.ating_mb ?? 0) * gate * lbGate;
              return (
                <div key={w.ws} style={{ borderTop: "1px solid #e8eaf0", paddingTop: 8, marginTop: 8 }}>
                  <div style={{ fontWeight: 700, color: "#1a3c6e", marginBottom: 4 }}>
                    {wsLabel} — Peso WS: {fmtPct(w.peso_ws)}
                  </div>
                  <div style={{ color: "#444", marginBottom: 1 }}>Bônus Receita = Salário × Peso Rec. × Peso WS × Ating. Rec.</div>
                  <div style={{ fontFamily: "monospace", fontSize: 12, marginBottom: 6 }}>
                    = {fmt(sal)} × {fmtPct(pRec)} × {fmtPct(w.peso_ws)} × {fmtPct(w.ating_rec ?? 0)}
                    {" = "}<strong style={{ color: bRec > 0 ? "#52c41a" : "#ff4d4f", fontSize: 13 }}>{fmt(bRec)}</strong>
                  </div>
                  <div style={{ color: "#444", marginBottom: 1 }}>
                    Bônus MB% = Salário × Peso MB% × Peso WS × Ating. MB%{w.aplica_gate_mb ? " × Gate MB" : ""}
                  </div>
                  <div style={{ fontFamily: "monospace", fontSize: 12 }}>
                    = {fmt(sal)} × {fmtPct(pMb)} × {fmtPct(w.peso_ws)} × {fmtPct(w.ating_mb ?? 0)}{w.aplica_gate_mb ? ` × ${gate}` : ""}
                    {" = "}<strong style={{ color: bMb > 0 ? "#52c41a" : "#ff4d4f", fontSize: 13 }}>{fmt(bMb)}</strong>
                  </div>
                </div>
              );
            })}
            {(d.peso_tcv || 0) > 0 && (
              <div style={{ borderTop: "1px solid #d0d9f0", paddingTop: 8, marginTop: 8 }}>
                <div style={{ fontWeight: 700, color: "#1a3c6e", marginBottom: 4 }}>TCV Área Grupo Mult — Peso: {fmtPct(d.peso_tcv || 0)}</div>
                <div style={{ color: "#444", marginBottom: 1 }}>Bônus TCV = Salário × Peso TCV × Ating. TCV Área</div>
                <div style={{ fontFamily: "monospace", fontSize: 12 }}>
                  = {fmt(d.salario_q4)} × {fmtPct(d.peso_tcv || 0)} × {fmtPct(d.ating_tcv || 0)}
                  {" = "}<strong style={{ color: (d as any).bonus_tcv > 0 ? "#52c41a" : "#ff4d4f", fontSize: 13 }}>{fmt((d as any).bonus_tcv || 0)}</strong>
                </div>
              </div>
            )}
            <div style={{ borderTop: "2px solid #d0d9f0", paddingTop: 8, marginTop: 8, textAlign: "right" }}>
              <strong>Total Bônus: </strong>
              <strong style={{ color: "#52c41a", fontSize: 14 }}>{fmt(d.bonus_total)}</strong>
            </div>
          </div>
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
                title: "Custo",
                dataIndex: "real_custo",
                align: "right" as const,
                render: (v: number) => v != null && v !== 0
                  ? <span style={{ color: "#595959" }}>{fmt(Math.abs(v))}</span>
                  : <span style={{ color: "#ccc" }}>—</span>,
              },
              {
                title: "Lucro Bruto",
                dataIndex: "real_lb",
                align: "right" as const,
                render: (v: number) => v != null && v > 0
                  ? <span style={{ color: "#595959" }}>{fmt(v)}</span>
                  : <span style={{ color: "#ccc" }}>—</span>,
              },
              {
                title: "Margem%",
                dataIndex: "margem_pct",
                align: "right" as const,
                render: (v: number | null) => v != null
                  ? <span style={{ color: v >= 30 ? "#52c41a" : v >= 20 ? "#faad14" : "#ff4d4f", fontWeight: 600 }}>{v.toFixed(1)}%</span>
                  : <span style={{ color: "#ccc" }}>—</span>,
              },
            ]}
            summary={rows => {
              const totalBgt   = (rows as ClienteDetalhe[]).reduce((s, r) => s + r.budget_rec, 0);
              const totalReal  = (rows as ClienteDetalhe[]).reduce((s, r) => s + r.real_rec, 0);
              const totalCusto = (rows as ClienteDetalhe[]).reduce((s, r) => s + (r.real_custo || 0), 0);
              const totalLb    = (rows as ClienteDetalhe[]).reduce((s, r) => s + (r.real_lb || 0), 0);
              const totalMgPct = totalReal > 0 ? totalLb / totalReal * 100 : null;
              return (
                <Table.Summary.Row style={{ fontWeight: 700, background: "#f0f4ff" }}>
                  <Table.Summary.Cell index={0}>Total</Table.Summary.Cell>
                  <Table.Summary.Cell index={1} align="right">{fmt(totalBgt)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={2} align="right">
                    <span style={{ color: totalReal >= totalBgt ? "#52c41a" : "#ff4d4f" }}>{fmt(totalReal)}</span>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={3} align="right">{fmt(Math.abs(totalCusto))}</Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right">{fmt(totalLb)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right">
                    {totalMgPct != null
                      ? <span style={{ color: totalMgPct >= 30 ? "#52c41a" : totalMgPct >= 20 ? "#faad14" : "#ff4d4f", fontWeight: 700 }}>{totalMgPct.toFixed(1)}%</span>
                      : "—"}
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              );
            }}
          />
        </>
      )}
    </div>
  );
}

// ─── Detalhe Diretor ──────────────────────────────────────────────────────────

function ResultadoBox({ bonusTotal, salario, periodo = "Q4 2025" }: { bonusTotal: number; salario: number; periodo?: string }) {
  const ating = salario > 0 ? bonusTotal / salario : 0;
  const ok = bonusTotal > 0;
  return (
    <div style={{
      background: ok ? "#f6ffed" : "#fff2f0",
      border: `2px solid ${ok ? "#52c41a" : "#ff4d4f"}`,
      borderRadius: 10, padding: "14px 20px", marginBottom: 16,
      display: "flex", alignItems: "center", justifyContent: "space-between",
    }}>
      <div>
        <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>Bônus Total {periodo}</div>
        <div style={{ fontSize: 22, fontWeight: 700, color: ok ? "#52c41a" : "#ff4d4f" }}>
          {fmt(bonusTotal)}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>Atingimento</div>
        <div style={{ fontSize: 22, fontWeight: 700, color: ok ? "#52c41a" : "#ff4d4f" }}>
          {(ating * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  );
}

function DetalheDir({ d }: { d: DetalheCalculo }) {
  const gate = d.mc_gate === 1;
  const triggerMcAbs = d.trigger_mc_abs ?? ((d.budget_mc_abs ?? 0) * 0.85);
  const triggerMcPct = d.trigger_mc_pct ?? ((d.budget_mc_pct ?? 0) - 1.5);

  return (
    <div>
      <ResultadoBox bonusTotal={d.bonus_total ?? 0} salario={d.salario_q4 ?? 0} />
      {/* ── Gatilho Mestre ── */}
      <Divider>Gatilho Mestre — MC% (Margem de Contribuição)</Divider>
      <div style={{
        background: gate ? "#f6ffed" : "#fff2f0",
        border: `1px solid ${gate ? "#b7eb8f" : "#ffccc7"}`,
        borderRadius: 8, padding: "10px 16px", marginBottom: 12, display: "flex", alignItems: "center", gap: 12,
      }}>
        {gate
          ? <CheckCircleFilled style={{ color: "#52c41a", fontSize: 22 }} />
          : <CloseCircleFilled style={{ color: "#ff4d4f", fontSize: 22 }} />
        }
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, color: gate ? "#52c41a" : "#ff4d4f" }}>
            {gate ? "Gatilho atingido" : "Gatilho NÃO atingido — sem apuração de Receita e TCV"}
          </div>
          <div style={{ fontSize: 12, color: "#666" }}>
            MC {gate ? "≥" : "<"} mínimo de {fmt(triggerMcAbs)} (85% da meta de {fmt(d.budget_mc_abs ?? 0)})
          </div>
        </div>
      </div>

      {/* ── Regras de Apuração ── */}
      <Divider>Regras de Apuração</Divider>
      <div style={{ background: "#f6f8ff", border: "1px solid #d0d9f0", borderRadius: 8, padding: "10px 14px", fontSize: 13, marginBottom: 4 }}>
        <div style={{ marginBottom: 6 }}>
          <strong>Fórmula:</strong> Bônus = Salário × Peso Métrica × Atingimento
        </div>
        <div style={{ marginBottom: 6 }}>
          🎯 <strong>Trigger Receita/TCV:</strong> 85% da meta — abaixo disso = 0
          &nbsp;&nbsp;|&nbsp;&nbsp;
          🎯 <strong>Trigger MC:</strong> 85% da meta absoluta — abaixo disso = 0 (Gatilho Mestre)
        </div>
        <div>
          <strong>Pesos:</strong>&nbsp;
          TCV <Tag color="orange">{fmtPct(d.peso_tcv || 0)}</Tag>
          Receita <Tag color="blue">{fmtPct(d.peso_receita || 0)}</Tag>
          MC% <Tag color="purple">{fmtPct(d.peso_mc || 0)}</Tag>
          Salário Q4 <Tag color="default">{fmt(d.salario_q4)}</Tag>
        </div>
      </div>

      {/* ── MC ── */}
      <Divider>Margem de Contribuição — Gatilho Mestre (peso {fmtPct(d.peso_mc || 0)})</Divider>
      <MetaRealRow
        label="Margem de Contribuição (R$)"
        meta={d.budget_mc_abs || 0}
        triggerAmt={triggerMcAbs}
        real={d.real_mc_abs || 0}
        ating={d.ating_mc || 0}
        gate={gate}
        bonusAtMaxAting={d.salario_q4 * (d.peso_mc || 0)}
        showBar={true}
      />
      {(d.budget_mc_pct || d.real_mc_pct) ? (
        <div style={{ fontSize: 12, color: "#888", marginTop: -10, marginBottom: 16 }}>
          Em %: Meta {(d.budget_mc_pct || 0).toFixed(2)}% · Mín. {triggerMcPct.toFixed(2)}% · Realizado {(d.real_mc_pct || 0).toFixed(2)}%
        </div>
      ) : null}

      {/* ── TCV ── */}
      <Divider>TCV (peso {fmtPct(d.peso_tcv || 0)})</Divider>
      <MetaRealRow
        label="TCV"
        meta={d.budget_tcv_q4 || 0}
        triggerAmt={(d.budget_tcv_q4 || 0) * 0.85}
        real={d.real_tcv_q4 || 0}
        ating={d.ating_tcv || 0}
        bonusAtMaxAting={d.salario_q4 * (d.peso_tcv || 0)}
      />

      {/* ── Receita por WS ── */}
      <Divider>Receita por WS (peso métrica {fmtPct(d.peso_receita || 0)})</Divider>
      {d.detalhe_ws && d.detalhe_ws.length > 0 && (
        <>
          <Table
            size="small"
            pagination={false}
            style={{ marginBottom: 16 }}
            dataSource={d.detalhe_ws.map(w => ({
              key: w.ws,
              ws: w.ws === "cloud" ? "CLOUD/CYBER" : w.ws.toUpperCase(),
              peso_ws: w.peso_ws,
              rec_meta: w.budget_rec,
              rec_real: w.real_rec,
              mb_meta: w.budget_mb_pct,
              mb_real: w.real_mb_pct,
              lb_meta: w.budget_rec * w.budget_mb_pct / 100,
              lb_real: w.real_lb_financeiro ?? (w.real_rec * w.real_mb_pct / 100),
            }))}
            summary={() => {
              const ws = d.detalhe_ws!;
              const totRecMeta = ws.reduce((s, w) => s + w.budget_rec, 0);
              const totRecReal = ws.reduce((s, w) => s + w.real_rec, 0);
              const totLbMeta  = ws.reduce((s, w) => s + w.budget_rec * w.budget_mb_pct / 100, 0);
              const totLbReal  = ws.reduce((s, w) => s + (w.real_lb_financeiro ?? w.real_rec * w.real_mb_pct / 100), 0);
              const mbMetaTot  = totRecMeta > 0 ? totLbMeta / totRecMeta * 100 : 0;
              const mbRealTot  = totRecReal > 0 ? totLbReal / totRecReal * 100 : 0;
              return (
                <Table.Summary.Row style={{ fontWeight: 700, background: "#f0f5ff" }}>
                  <Table.Summary.Cell index={0}>Total</Table.Summary.Cell>
                  <Table.Summary.Cell index={1} align="right">100%</Table.Summary.Cell>
                  <Table.Summary.Cell index={2} align="right">{fmt(totRecMeta)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={3} align="right">{fmt(totRecReal)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right">{mbMetaTot.toFixed(1)}%</Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right">{mbRealTot.toFixed(1)}%</Table.Summary.Cell>
                  <Table.Summary.Cell index={6} align="right">{fmt(totLbMeta)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={7} align="right">{fmt(totLbReal)}</Table.Summary.Cell>
                </Table.Summary.Row>
              );
            }}
            columns={[
              { title: "WS", dataIndex: "ws", width: 100 },
              { title: "Peso", dataIndex: "peso_ws", width: 60, render: (v: number) => fmtPct(v) },
              {
                title: "Receita",
                children: [
                  { title: "Meta", dataIndex: "rec_meta", align: "right" as const, render: (v: number) => fmt(v) },
                  { title: "Realizado", dataIndex: "rec_real", align: "right" as const,
                    render: (v: number, row: any) => <span style={{ color: v >= row.rec_meta ? "#52c41a" : v > 0 ? "#faad14" : "#ff4d4f", fontWeight: 600 }}>{fmt(v)}</span> },
                ],
              },
              {
                title: "MB%",
                children: [
                  { title: "Meta", dataIndex: "mb_meta", align: "right" as const, render: (v: number) => v ? `${v.toFixed(1)}%` : "—" },
                  { title: "Realizado", dataIndex: "mb_real", align: "right" as const, render: (v: number) => v ? `${v.toFixed(1)}%` : "—" },
                ],
              },
              {
                title: "LB",
                children: [
                  { title: "Meta", dataIndex: "lb_meta", align: "right" as const, render: (v: number) => fmt(v) },
                  { title: "Realizado", dataIndex: "lb_real", align: "right" as const, render: (v: number) => fmt(v) },
                ],
              },
            ]}
          />

          {/* ── Cálculo detalhado por WS ── */}
          <Divider plain>Cálculo do Bônus por WS</Divider>
          <div style={{ background: "#f8f9ff", border: "1px solid #d0d9f0", borderRadius: 8, padding: "10px 14px", marginBottom: 16, fontSize: 13 }}>
            <div style={{ marginBottom: 8, color: "#666" }}>
              <strong>Fórmula:</strong> Bônus WS = Salário × Peso Receita × Peso WS × Atingimento Receita
            </div>
            {d.detalhe_ws.filter(w => w.budget_rec > 0).map(w => {
              const wsLabel = w.ws === "cloud" ? "CLOUD/CYBER" : w.ws.toUpperCase();
              const sal = d.salario_q4;
              const pRec = d.peso_receita || 0;
              const ating = w.ating_rec ?? 0;
              const bonus = w.bonus_ws ?? (sal * pRec * w.peso_ws * ating * (d.mc_gate ?? 1));
              return (
                <div key={w.ws} style={{ borderTop: "1px solid #e8eaf0", paddingTop: 8, marginTop: 8 }}>
                  <div style={{ fontWeight: 700, color: "#1a3c6e", marginBottom: 4 }}>
                    {wsLabel} — Peso WS: {fmtPct(w.peso_ws)}
                  </div>
                  <div style={{ color: "#444", marginBottom: 2 }}>
                    Bônus Receita = Salário × Peso Rec. × Peso WS × Ating. Rec.
                  </div>
                  <div style={{ color: "#222", fontFamily: "monospace", fontSize: 12 }}>
                    = {fmt(sal)} × {fmtPct(pRec)} × {fmtPct(w.peso_ws)} × {fmtPct(ating)}
                    {" = "}
                    <strong style={{ color: bonus > 0 ? "#52c41a" : "#ff4d4f", fontSize: 13 }}>{fmt(bonus)}</strong>
                  </div>
                </div>
              );
            })}
            <div style={{ borderTop: "2px solid #d0d9f0", paddingTop: 8, marginTop: 8, textAlign: "right" }}>
              <strong>Total Bônus Receita: </strong>
              <strong style={{ color: "#52c41a", fontSize: 14 }}>
                {fmt(d.bonus_rec || 0)}
              </strong>
            </div>
          </div>
        </>
      )}

      {/* ── Breakdown Custos / Despesas ── */}
      <Divider>Custos e Despesas — Composição da MC% (Nexus Q4)</Divider>
      <Table
        size="small"
        pagination={false}
        style={{ marginBottom: 16 }}
        dataSource={(() => {
          const rec  = d.real_rec_sap ?? d.real_rec_q4 ?? 0;
          const lb   = d.real_lb_q4 ?? 0;
          const desp = d.real_despesa_pessoas ?? ((d.real_payroll_exp ?? 0) + (d.real_deductions ?? 0));
          const mc   = lb + desp;
          const bgtRec  = d.budget_rec_q4 ?? 0;
          const bgtLb   = d.budget_lb_q4 ?? 0;
          const bgtDesp = (d.bgt_payroll_exp ?? 0) + (d.bgt_deductions ?? 0);
          const bgtMc   = bgtLb + bgtDesp;
          return [
            { key: "rec",  linha: "Receita",                    tipo: "receita", bgt: bgtRec,  real: rec,  pct: null },
            { key: "lb",   linha: "Lucro Bruto (MB)",           tipo: "mb",      bgt: bgtLb,   real: lb,   pct: rec ? `${(lb/rec*100).toFixed(1)}%` : null },
            { key: "desp", linha: "Despesas",                   tipo: "despesa", bgt: bgtDesp, real: desp, pct: null },
            { key: "mc",   linha: "Margem de Contribuição (MC)", tipo: "mc",      bgt: bgtMc,   real: mc,   pct: rec ? `${(mc/rec*100).toFixed(1)}%` : null },
          ];
        })()}
        columns={[
          { title: "Linha", dataIndex: "linha", width: "45%",
            render: (v: string, row: any) => {
              const color = row.tipo === "receita" ? "#1a2e5a"
                : row.tipo === "mb" ? "#1a6e3c"
                : row.tipo === "despesa" ? "#e67e22"
                : "#0050b3";
              return <span style={{ color, fontWeight: row.tipo === "mb" || row.tipo === "mc" ? 700 : 400 }}>{v}</span>;
            }
          },
          { title: "Budget Q4", dataIndex: "bgt", align: "right" as const,
            render: (v: number) => <span style={{ color: "#888" }}>{v !== 0 ? fmt(v) : "—"}</span> },
          { title: "Realizado Q4", dataIndex: "real", align: "right" as const,
            render: (v: number, row: any) => {
              if (v === 0 && row.tipo !== "mb" && row.tipo !== "mc") return <span style={{ color: "#ccc" }}>—</span>;
              const color = row.tipo === "receita" ? "#1a2e5a"
                : row.tipo === "mb" ? "#1a6e3c"
                : row.tipo === "despesa" ? "#e67e22"
                : "#0050b3";
              return <span style={{ color, fontWeight: 600 }}>{fmt(v)}</span>;
            }
          },
          { title: "% s/ Receita", dataIndex: "pct", align: "right" as const,
            render: (v: string | null) => v ? <span style={{ fontWeight: 700 }}>{v}</span> : <span style={{ color: "#ccc" }}>—</span>
          },
        ]}
      />

      {/* ── Clientes da Vertical ── */}
      {d.clientes_detalhe && d.clientes_detalhe.length > 0 && (
        <>
          <Divider>Carteira de Clientes da Vertical</Divider>
          <Table
            size="small"
            pagination={false}
            dataSource={d.clientes_detalhe.map((r, i) => ({ ...r, key: i }))}
            style={{ marginBottom: 16 }}
            columns={[
              { title: "Cliente", dataIndex: "cliente", ellipsis: true },
              {
                title: "Receita",
                children: [
                  { title: "Meta", dataIndex: "budget_rec", align: "right" as const, render: (v: number) => fmt(v) },
                  { title: "Realizado", dataIndex: "real_rec", align: "right" as const,
                    render: (v: number, row: any) => (
                      <span style={{ color: v >= row.budget_rec ? "#52c41a" : "#ff4d4f", fontWeight: 600 }}>{fmt(v)}</span>
                    )},
                ],
              },
              { title: "Custo", dataIndex: "real_custo", align: "right" as const,
                render: (v: number) => v != null && v !== 0 ? <span style={{ color: "#595959" }}>{fmt(Math.abs(v))}</span> : <span style={{ color: "#ccc" }}>—</span> },
              { title: "Lucro Bruto", dataIndex: "real_lb", align: "right" as const,
                render: (v: number) => v != null && v !== 0 ? fmt(v) : <span style={{ color: "#ccc" }}>—</span> },
              { title: "Margem%", dataIndex: "margem_pct", align: "right" as const,
                render: (v: number | null) => v != null
                  ? <span style={{ color: v >= 30 ? "#52c41a" : v >= 20 ? "#faad14" : "#ff4d4f", fontWeight: 600 }}>{v.toFixed(1)}%</span>
                  : <span style={{ color: "#ccc" }}>—</span> },
            ]}
            summary={rows => {
              const tBgt  = (rows as unknown as ClienteDetalhe[]).reduce((s, r) => s + r.budget_rec, 0);
              const tReal = (rows as unknown as ClienteDetalhe[]).reduce((s, r) => s + r.real_rec, 0);
              const tCust = (rows as unknown as ClienteDetalhe[]).reduce((s, r) => s + (r.real_custo || 0), 0);
              const tLb   = (rows as unknown as ClienteDetalhe[]).reduce((s, r) => s + (r.real_lb || 0), 0);
              const tMg   = tReal > 0 ? tLb / tReal * 100 : null;
              return (
                <Table.Summary.Row style={{ fontWeight: 700, background: "#f0f4ff" }}>
                  <Table.Summary.Cell index={0}>Total</Table.Summary.Cell>
                  <Table.Summary.Cell index={1} align="right">{fmt(tBgt)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={2} align="right">
                    <span style={{ color: tReal >= tBgt ? "#52c41a" : "#ff4d4f" }}>{fmt(tReal)}</span>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={3} align="right">{fmt(Math.abs(tCust))}</Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right">{fmt(tLb)}</Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right">
                    {tMg != null
                      ? <span style={{ color: tMg >= 30 ? "#52c41a" : tMg >= 20 ? "#faad14" : "#ff4d4f" }}>{tMg.toFixed(1)}%</span>
                      : "—"}
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              );
            }}
          />
        </>
      )}

      {/* ── Tabela de Cálculo ── */}
      <Divider>Cálculo do Bônus</Divider>
      <Table
        size="small"
        pagination={false}
        dataSource={[
          { key: "tcv",    metrica: "TCV",     peso: fmtPct(d.peso_tcv || 0),     ating: gate ? fmtPct(d.ating_tcv || 0) : "0,0%",  bonus: d.bonus_tcv || 0 },
          { key: "rec",    metrica: "Receita",  peso: fmtPct(d.peso_receita || 0), ating: gate ? fmtPct(d.ating_rec || 0) : "0,0%",  bonus: d.bonus_rec || 0 },
          { key: "mc",     metrica: "MC%",      peso: fmtPct(d.peso_mc || 0),      ating: gate ? fmtPct(d.ating_mc || 0) : "0,0%",  bonus: d.bonus_mc || 0 },
        ]}
        summary={() => (
          <Table.Summary.Row style={{ fontWeight: 700, background: "#f0f4ff" }}>
            <Table.Summary.Cell index={0}>Total</Table.Summary.Cell>
            <Table.Summary.Cell index={1} />
            <Table.Summary.Cell index={2} />
            <Table.Summary.Cell index={3} align="right">
              <span style={{ color: "#52c41a" }}>{fmt(d.bonus_total)}</span>
            </Table.Summary.Cell>
          </Table.Summary.Row>
        )}
        columns={[
          { title: "Métrica", dataIndex: "metrica" },
          { title: "Peso", dataIndex: "peso" },
          { title: "Atingimento", dataIndex: "ating" },
          {
            title: "Bônus",
            dataIndex: "bonus",
            align: "right" as const,
            render: (v: number) => <strong style={{ color: v > 0 ? "#52c41a" : "#999" }}>{fmt(v)}</strong>,
          },
        ]}
      />
    </div>
  );
}

// ─── Apuração Q3 — apenas AE_GM (Grupo Mult) ─────────────────────────────────

type MasterRowQ3 = {
  nome: string;
  posicao: string;
  contrato: string;
  vertical: string;
  salario: number;
  bonus: number;
  ating_rec: number | null;
  ating_mb: number | null;
  ating_tcv: number | null;
  pct_rec: number | null;
  pct_mb: number | null;
  pct_tcv: number | null;
  gate_ok: boolean;
  tipo_calc: string;
  erro?: string;
};

export function VistaMasterTabQ3() {
  const [data, setData] = useState<MasterRowQ3[]>([]);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detalheQ3, setDetalheQ3] = useState<DetalheCalculo | null>(null);
  const [loadingDetalhe, setLoadingDetalhe] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);
  const handlePrint = useReactToPrint({ contentRef: printRef, documentTitle: detalheQ3 ? `Memória de Cálculo Q3 — ${detalheQ3.nome}` : "Memória de Cálculo Q3" });

  const carregar = () => {
    setLoading(true);
    getApuracaoVisaoMasterQ3()
      .then(setData)
      .catch(() => message.error("Erro ao carregar visão master Q3"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const abrirDetalhe = (nome: string) => {
    setDrawerOpen(true);
    setDetalheQ3(null);
    setLoadingDetalhe(true);
    getApuracaoCalcularQ3(nome)
      .then(setDetalheQ3)
      .catch((e: Error) => message.error(`Erro: ${e.message}`, 10))
      .finally(() => setLoadingDetalhe(false));
  };

  const totalBonus = data.reduce((s, r) => s + r.bonus, 0);

  const atCol = (v: number | null) => {
    if (v == null) return <span style={{ color: "#ccc" }}>—</span>;
    return (
      <span style={{ color: v >= 1 ? "#52c41a" : v > 0 ? "#faad14" : "#ff4d4f", fontWeight: 600 }}>
        {fmtPct(v)}
      </span>
    );
  };

  const columnsQ3 = [
    {
      title: "Nome",
      dataIndex: "nome",
      key: "nome",
      render: (v: string) => (
        <span style={{ cursor: "pointer", color: "#1677ff", fontWeight: 500 }} onClick={() => abrirDetalhe(v)}>
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
      title: "Gatilho LB",
      key: "gate_ok",
      render: (_: any, row: MasterRowQ3) => (
        <div style={{ textAlign: "center" }}>
          {row.gate_ok
            ? <CheckCircleFilled style={{ color: "#52c41a", fontSize: 18 }} />
            : <CloseCircleFilled style={{ color: "#ff4d4f", fontSize: 18 }} />
          }
        </div>
      ),
    },
    {
      title: "% TCV",
      key: "pct_tcv",
      render: (_: any, row: MasterRowQ3) => atCol(row.pct_tcv),
    },
    {
      title: "% Receita",
      key: "pct_rec",
      render: (_: any, row: MasterRowQ3) => atCol(row.pct_rec),
    },
    {
      title: "% MB",
      key: "pct_mb",
      render: (_: any, row: MasterRowQ3) => atCol(row.pct_mb),
    },
    {
      title: "Bônus Q3",
      dataIndex: "bonus",
      key: "bonus",
      align: "right" as const,
      sorter: (a: MasterRowQ3, b: MasterRowQ3) => a.bonus - b.bonus,
      render: (v: number, row: MasterRowQ3) => (
        <span style={{ fontWeight: 600, color: v > 0 ? "#52c41a" : row.erro ? "#ff4d4f" : "#999" }}>
          {row.erro ? "Erro" : fmt(v)}
        </span>
      ),
    },
  ];

  return (
    <div style={{ padding: "16px 0" }}>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "center" }}>
        <Tag color="geekblue" style={{ fontSize: 13 }}>Grupo Mult — AE_GM</Tag>
        <Button icon={<ReloadOutlined />} onClick={carregar} loading={loading}>
          Atualizar
        </Button>
        <div style={{ marginLeft: "auto", fontWeight: 600, fontSize: 15 }}>
          Total bônus Q3: <span style={{ color: "#52c41a" }}>{fmt(totalBonus)}</span>
        </div>
      </div>

      <Spin spinning={loading}>
        <Table
          dataSource={data}
          columns={columnsQ3}
          rowKey="nome"
          size="small"
          pagination={false}
          summary={() => (
            <Table.Summary.Row style={{ background: "#fafafa", fontWeight: 600 }}>
              <Table.Summary.Cell index={0} colSpan={6}>Total ({data.length} pessoas)</Table.Summary.Cell>
              <Table.Summary.Cell index={6} />
              <Table.Summary.Cell index={7} align="right">
                <span style={{ color: "#52c41a" }}>{fmt(totalBonus)}</span>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      </Spin>

      <Drawer
        title={detalheQ3 ? `Memória de Cálculo Q3 — ${detalheQ3.nome}` : "Carregando..."}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={820}
        extra={
          detalheQ3 && (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Tag color="geekblue" style={{ fontSize: 14 }}>
                Bônus Q3: {fmt(detalheQ3.bonus_total)}
              </Tag>
              <Button
                type="primary"
                size="small"
                icon={<PrinterOutlined />}
                onClick={() => handlePrint()}
              >
                Imprimir / PDF Q3
              </Button>
            </div>
          )
        }
      >
        {loadingDetalhe && <Spin />}
        {detalheQ3 && !loadingDetalhe && (
          <div ref={printRef} style={{ padding: 8 }}>
            <h2 style={{ marginBottom: 16, fontSize: 18, fontWeight: 700, color: "#1a3c6e" }}>
              Memória de Cálculo — {detalheQ3.nome}&nbsp;
              <span style={{ fontSize: 13, fontWeight: 400, color: "#888" }}>Q3 2025</span>
            </h2>
            <DetalheDrawerQ3 d={detalheQ3} />
          </div>
        )}
      </Drawer>
    </div>
  );
}

import React, { useCallback, useEffect, useState } from "react";
import {
  Table, Button, Modal, Form, Input, Select, Tag, Space, Popconfirm,
  Switch, Tabs, Typography, Alert, message,
} from "antd";
import {
  PlusOutlined, ReloadOutlined, KeyOutlined, DeleteOutlined,
  CopyOutlined, EditOutlined, UserOutlined, TeamOutlined, HistoryOutlined, WifiOutlined,
} from "@ant-design/icons";
import {
  adminListUsers, adminCreateUser, adminUpdateUser, adminResetPassword,
  adminDeleteUser, adminLoginHistory, adminOnline,
  AdminUserRow, LoginHistoryRow, OnlineRow,
} from "../api";

const { Text } = Typography;

const BU_OPTS = [
  "BU Finance", "BU Health", "BU Multisector", "BU Retail", "BU Logistics",
];

// Espelha ALL_CARDS no backend. label = nome do card na home.
const CARD_OPTS: { value: string; label: string }[] = [
  { value: "nova_base",        label: "Financeiro - Nova Base" },
  { value: "bus",              label: "Visão BUs" },
  { value: "budget",           label: "Budget vs Realizado" },
  { value: "nova_base_pivot",  label: "Visão Personalizada" },
  { value: "obsoleto",         label: "Obsoleto (legado)" },
];
const CARD_LABEL: Record<string, string> = Object.fromEntries(CARD_OPTS.map(o => [o.value, o.label]));

function TempPasswordModal({ value, onClose }: { value: string | null; onClose: () => void }) {
  return (
    <Modal
      open={!!value}
      title="Senha temporária gerada"
      onCancel={onClose}
      footer={<Button type="primary" onClick={onClose}>OK</Button>}
    >
      <Alert
        type="warning" showIcon
        message="Copie e repasse esta senha agora — ela não será mostrada de novo."
        style={{ marginBottom: 16 }}
      />
      <div style={{
        fontFamily: "monospace", fontSize: 18, fontWeight: 700,
        background: "#f6f8fb", padding: "12px 16px", borderRadius: 8,
        border: "1px solid #d9d9d9", textAlign: "center", letterSpacing: 1,
      }}>
        {value}
      </div>
      <div style={{ marginTop: 12, textAlign: "center" }}>
        <Button icon={<CopyOutlined />} onClick={() => { navigator.clipboard.writeText(value || ""); message.success("Copiada!"); }}>
          Copiar
        </Button>
      </div>
      <Text type="secondary" style={{ display: "block", marginTop: 12, fontSize: 12 }}>
        O usuário será obrigado a trocar a senha no primeiro login.
      </Text>
    </Modal>
  );
}

function UsersList() {
  const [rows, setRows]       = useState<AdminUserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminUserRow | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [tempPwd, setTempPwd] = useState<string | null>(null);
  const [createForm] = Form.useForm();
  const [editForm]   = Form.useForm();

  const load = useCallback(() => {
    setLoading(true);
    adminListUsers()
      .then(r => setRows(r.rows))
      .catch(e => message.error(String(e?.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const onCreate = async (values: any) => {
    try {
      const r = await adminCreateUser({
        username: String(values.username || "").trim().toLowerCase(),
        name: values.name,
        email: values.email || undefined,
        bus: values.bus || [],
        is_super_admin: !!values.is_super_admin,
        visible_cards: values.visible_cards && values.visible_cards.length ? values.visible_cards : null,
      });
      setCreateOpen(false);
      createForm.resetFields();
      setTempPwd(r.temp_password);
      load();
    } catch (e: any) {
      message.error(e?.message || "Falha ao criar.");
    }
  };

  const onSaveEdit = async (values: any) => {
    if (!editing) return;
    setSavingEdit(true);
    try {
      await adminUpdateUser(editing.username, {
        name: values.name,
        email: values.email || null,
        bus: values.bus || [],
        is_super_admin: !!values.is_super_admin,
        visible_cards: values.visible_cards && values.visible_cards.length ? values.visible_cards : null,
      });
      setEditing(null);
      editForm.resetFields();
      message.success("Atualizado.");
      load();
    } catch (e: any) {
      message.error(e?.message || "Falha ao atualizar.");
    } finally {
      setSavingEdit(false);
    }
  };

  const onReset = async (u: AdminUserRow) => {
    try {
      const r = await adminResetPassword(u.username);
      setTempPwd(r.temp_password);
      load();
    } catch (e: any) {
      message.error(e?.message || "Falha ao resetar.");
    }
  };

  const onDelete = async (u: AdminUserRow) => {
    try {
      await adminDeleteUser(u.username);
      message.success("Excluído.");
      load();
    } catch (e: any) {
      message.error(e?.message || "Falha ao excluir.");
    }
  };

  const columns = [
    { title: "Usuário", dataIndex: "username", key: "username", width: 140,
      render: (v: string) => <span style={{ fontFamily: "monospace" }}>{v}</span> },
    { title: "Nome", dataIndex: "name", key: "name", width: 160 },
    { title: "Email", dataIndex: "email", key: "email", render: (v: any) => v || <Text type="secondary">—</Text> },
    { title: "BUs", dataIndex: "bus", key: "bus", render: (b: string[]) =>
        b && b.length ? b.map(x => <Tag key={x} color="blue">{x}</Tag>) : <Tag>Admin (todas)</Tag> },
    { title: "Cards", dataIndex: "visible_cards", key: "vc",
      render: (vc: string[] | null) => vc && vc.length
        ? vc.map(x => <Tag key={x} color="purple">{CARD_LABEL[x] ?? x}</Tag>)
        : <Text type="secondary">(padrão)</Text> },
    { title: "Super admin", dataIndex: "is_super_admin", key: "is_super_admin", width: 100, align: "center" as const,
      render: (v: boolean) => v ? <Tag color="gold">SIM</Tag> : <Text type="secondary">—</Text> },
    { title: "Troca senha?", dataIndex: "must_change_password", key: "mcp", width: 110, align: "center" as const,
      render: (v: boolean) => v ? <Tag color="orange">pendente</Tag> : <Text type="secondary">—</Text> },
    { title: "Últ. login", dataIndex: "last_login_at", key: "last_login_at", width: 160,
      render: (v: string | null) => v ? new Date(v).toLocaleString("pt-BR") : <Text type="secondary">nunca</Text> },
    { title: "Ações", key: "actions", width: 220, render: (_: any, row: AdminUserRow) => (
      <Space size="small">
        <Button size="small" icon={<EditOutlined />} onClick={() => {
          setEditing(row);
          editForm.setFieldsValue({
            name: row.name, email: row.email, bus: row.bus || [],
            is_super_admin: !!row.is_super_admin,
            visible_cards: row.visible_cards || [],
          });
        }} />
        <Popconfirm title="Gerar nova senha temporária?" onConfirm={() => onReset(row)}>
          <Button size="small" icon={<KeyOutlined />} />
        </Popconfirm>
        <Popconfirm title={`Excluir ${row.username}?`} onConfirm={() => onDelete(row)} okType="danger">
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    ) },
  ];

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Novo usuário
        </Button>
        <Button icon={<ReloadOutlined />} onClick={load}>Atualizar</Button>
      </div>
      <Table
        rowKey="username"
        size="small"
        loading={loading}
        columns={columns as any}
        dataSource={rows}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        open={createOpen}
        title="Novo usuário"
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        okText="Criar (gera senha temporária)"
      >
        <Form layout="vertical" form={createForm} onFinish={onCreate}>
          <Form.Item name="username" label="Usuário" rules={[{ required: true }]}>
            <Input placeholder="ex: jdiretor" />
          </Form.Item>
          <Form.Item name="name" label="Nome" rules={[{ required: true }]}>
            <Input placeholder="ex: João Diretor" />
          </Form.Item>
          <Form.Item name="email" label="Email">
            <Input placeholder="opcional" />
          </Form.Item>
          <Form.Item name="bus" label="BUs (vazio = admin, vê tudo)">
            <Select mode="multiple" allowClear options={BU_OPTS.map(b => ({ label: b, value: b }))} />
          </Form.Item>
          <Form.Item name="visible_cards" label="Cards visíveis na home"
            tooltip="Deixe vazio pra usar o padrão (admin vê tudo, diretor de BU vê só 'Visão BUs').">
            <Select mode="multiple" allowClear options={CARD_OPTS}
              placeholder="Padrão (auto pelo perfil)" />
          </Form.Item>
          <Form.Item name="is_super_admin" label="Super admin?" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={!!editing}
        title={`Editar ${editing?.username}`}
        onCancel={() => { if (!savingEdit) setEditing(null); }}
        onOk={() => editForm.submit()}
        okText="Salvar"
        confirmLoading={savingEdit}
        maskClosable={!savingEdit}
        forceRender
      >
        <Form
          layout="vertical"
          form={editForm}
          onFinish={onSaveEdit}
          onFinishFailed={(info) => {
            const first = info?.errorFields?.[0]?.errors?.[0];
            if (first) message.error(first);
          }}
        >
          <Form.Item name="name" label="Nome" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="Email">
            <Input />
          </Form.Item>
          <Form.Item name="bus" label="BUs (vazio = admin)">
            <Select mode="multiple" allowClear options={BU_OPTS.map(b => ({ label: b, value: b }))} />
          </Form.Item>
          <Form.Item name="visible_cards" label="Cards visíveis na home"
            tooltip="Vazio = padrão pelo perfil. Senão, só esses aparecem.">
            <Select mode="multiple" allowClear options={CARD_OPTS}
              placeholder="Padrão (auto pelo perfil)" />
          </Form.Item>
          <Form.Item name="is_super_admin" label="Super admin?" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <TempPasswordModal value={tempPwd} onClose={() => setTempPwd(null)} />
    </div>
  );
}

function HistoryTab() {
  const [rows, setRows]       = useState<LoginHistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => {
    setLoading(true);
    adminLoginHistory(200).then(r => setRows(r.rows)).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const columns = [
    { title: "Quando", dataIndex: "login_at", key: "login_at", width: 180,
      render: (v: string) => new Date(v).toLocaleString("pt-BR"),
      sorter: (a: LoginHistoryRow, b: LoginHistoryRow) => a.login_at.localeCompare(b.login_at),
      defaultSortOrder: "descend" as const },
    { title: "Usuário", dataIndex: "username", key: "username", width: 140 },
    { title: "Sucesso", dataIndex: "success", key: "success", width: 90, align: "center" as const,
      render: (v: boolean) => v ? <Tag color="green">OK</Tag> : <Tag color="red">FALHA</Tag> },
    { title: "IP", dataIndex: "ip", key: "ip", width: 130, render: (v: any) => v || "—" },
    { title: "Navegador", dataIndex: "user_agent", key: "ua",
      render: (v: any) => <span style={{ fontSize: 11, color: "#6b7280" }}>{v || "—"}</span> },
  ];
  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Button icon={<ReloadOutlined />} onClick={load}>Atualizar</Button>
      </div>
      <Table rowKey="id" size="small" loading={loading} columns={columns as any}
        dataSource={rows} pagination={{ pageSize: 50 }} />
    </div>
  );
}

function OnlineTab() {
  const [rows, setRows]       = useState<OnlineRow[]>([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true);
    adminOnline().then(r => setRows(r.rows)).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    load();
    const id = setInterval(load, 15_000); // auto-refresh a cada 15s
    return () => clearInterval(id);
  }, [load]);
  const fmt = (s: number) =>
    s < 60 ? `${s}s atrás` : s < 3600 ? `${Math.floor(s / 60)} min atrás` : `${Math.floor(s / 3600)}h atrás`;
  const columns = [
    { title: "Usuário", dataIndex: "username", key: "username", width: 160,
      render: (v: string) => <span style={{ fontFamily: "monospace" }}>{v}</span> },
    { title: "Nome", dataIndex: "name", key: "name" },
    { title: "Última atividade", dataIndex: "last_seen_seconds_ago", key: "ls", width: 160,
      render: (v: number) => fmt(v) },
  ];
  return (
    <div>
      <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
        <Button icon={<ReloadOutlined />} onClick={load}>Atualizar</Button>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Atualiza automaticamente a cada 15s · janela de 5 min
        </Text>
      </div>
      <Table rowKey="username" size="small" loading={loading} columns={columns as any}
        dataSource={rows} pagination={false}
        locale={{ emptyText: "Ninguém online no momento." }} />
    </div>
  );
}

export default function AdminTab() {
  return (
    <Tabs
      defaultActiveKey="users"
      items={[
        { key: "users",   label: <span><TeamOutlined /> Usuários</span>,          children: <UsersList /> },
        { key: "online",  label: <span><WifiOutlined /> Online agora</span>,      children: <OnlineTab /> },
        { key: "history", label: <span><HistoryOutlined /> Histórico de login</span>, children: <HistoryTab /> },
      ]}
    />
  );
}

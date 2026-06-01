import React, { useState } from "react";
import { Form, Input, Button, Alert, Card, Typography } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { login, changePassword } from "../api";
import { theme } from "../theme";

const { Title, Text } = Typography;

export default function Login() {
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);
  // Quando o login devolve must_change_password=true, exibe segundo formulario.
  const [mustChange, setMustChange] = useState(false);
  const [tempPwd, setTempPwd]       = useState("");

  async function handleLogin(values: { username: string; password: string }) {
    setLoading(true);
    setError("");
    try {
      const r = await login(values.username, values.password);
      if (r.must_change_password) {
        setTempPwd(values.password);
        setMustChange(true);
      } else {
        window.location.href = "/";
      }
    } catch {
      setError("Usuário ou senha incorretos.");
    } finally {
      setLoading(false);
    }
  }

  async function handleChange(values: { new_password: string; confirm: string }) {
    if (values.new_password !== values.confirm) {
      setError("Confirmação não confere.");
      return;
    }
    if (values.new_password.length < 6) {
      setError("Senha precisa ter ao menos 6 caracteres.");
      return;
    }
    setLoading(true); setError("");
    try {
      await changePassword(tempPwd, values.new_password);
      window.location.href = "/";
    } catch (e: any) {
      setError(e?.message || "Falha ao trocar a senha.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", background: "#f4f6fb",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <Card
        style={{ width: 380, borderRadius: 12, boxShadow: "0 4px 24px rgba(0,0,0,0.08)", borderTop: `4px solid ${theme.accent}` }}
        styles={{ body: { padding: "2rem" } }}
      >
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <img src="/logo-fcamara.png" alt="FCamara" style={{ height: 48, width: "auto", marginBottom: 12 }} />
          <Title level={3} style={{ color: theme.text, margin: 0 }}>FP&A Dashboard</Title>
          <Text type="secondary">{mustChange ? "Defina uma senha permanente" : "Faça login para continuar"}</Text>
        </div>

        {error && <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />}

        {!mustChange ? (
          <Form layout="vertical" onFinish={handleLogin}>
            <Form.Item name="username" label="Usuário" rules={[{ required: true, message: "Informe o usuário" }]}>
              <Input prefix={<UserOutlined />} size="large" placeholder="Usuário" />
            </Form.Item>
            <Form.Item name="password" label="Senha" rules={[{ required: true, message: "Informe a senha" }]}>
              <Input.Password prefix={<LockOutlined />} size="large" placeholder="Senha" />
            </Form.Item>
            <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
              <Button type="primary" htmlType="submit" size="large" block loading={loading}
                style={{ background: theme.accent, borderColor: theme.accent, borderRadius: 8 }}>
                Entrar
              </Button>
            </Form.Item>
          </Form>
        ) : (
          <Form layout="vertical" onFinish={handleChange}>
            <Alert
              message="Primeira entrada"
              description="Sua senha atual é temporária. Defina uma nova senha para continuar."
              type="info" showIcon style={{ marginBottom: 16 }}
            />
            <Form.Item name="new_password" label="Nova senha" rules={[{ required: true, message: "Informe a nova senha" }]}>
              <Input.Password prefix={<LockOutlined />} size="large" placeholder="Mínimo 6 caracteres" />
            </Form.Item>
            <Form.Item name="confirm" label="Confirme a nova senha" rules={[{ required: true, message: "Confirme a senha" }]}>
              <Input.Password prefix={<LockOutlined />} size="large" placeholder="Repetir senha" />
            </Form.Item>
            <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
              <Button type="primary" htmlType="submit" size="large" block loading={loading}
                style={{ background: theme.accent, borderColor: theme.accent, borderRadius: 8 }}>
                Salvar senha e entrar
              </Button>
            </Form.Item>
          </Form>
        )}
      </Card>
    </div>
  );
}

import React, { useState } from "react";
import { Form, Input, Button, Alert, Card, Typography } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { login } from "../api";
import { theme } from "../theme";

const { Title, Text } = Typography;

export default function Login() {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(values: { username: string; password: string }) {
    setLoading(true);
    setError("");
    try {
      await login(values.username, values.password);
      window.location.href = "/";
    } catch {
      setError("Usuário ou senha incorretos.");
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
          <Text type="secondary">Faça login para continuar</Text>
        </div>

        {error && <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />}

        <Form layout="vertical" onFinish={handleSubmit}>
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
      </Card>
    </div>
  );
}

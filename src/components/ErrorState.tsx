import React from "react";
import { Button } from "antd";
import { ReloadOutlined, WifiOutlined } from "@ant-design/icons";
import { theme } from "../theme";

interface Props {
  onRetry?: () => void;
  message?: string;
}

export default function ErrorState({ onRetry, message = "Não foi possível carregar os dados." }: Props) {
  return (
    <div style={{
      background: "#fff", borderRadius: 10, padding: "3rem 2rem", textAlign: "center",
      boxShadow: "0 2px 8px rgba(0,0,0,0.06)", border: "1px solid #fde8e8",
    }}>
      <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.5 }}>
        <WifiOutlined style={{ color: "#c0392b" }} />
      </div>
      <div style={{ color: theme.text, fontWeight: 600, fontSize: "1rem", marginBottom: 6 }}>
        Erro ao carregar
      </div>
      <div style={{ color: "#6b7fa3", fontSize: "0.85rem", marginBottom: 20 }}>
        {message}
      </div>
      {onRetry && (
        <Button icon={<ReloadOutlined />} onClick={onRetry} type="primary">
          Tentar novamente
        </Button>
      )}
    </div>
  );
}

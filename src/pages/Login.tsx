import React, { useState } from "react";
import { login } from "../api";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(username, password);
      window.location.href = "/";
    } catch {
      setError("Usuário ou senha incorretos.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>👷 Worker Dashboard</h1>
        <p style={styles.subtitle}>Faça login para continuar</p>
        <form onSubmit={handleSubmit}>
          <div style={styles.field}>
            <label style={styles.label}>Usuário</label>
            <input
              style={styles.input}
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus
            />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Senha</label>
            <input
              style={styles.input}
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </div>
          {error && <p style={styles.error}>{error}</p>}
          <button style={styles.button} type="submit" disabled={loading}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh", background: "#f4f6fb",
    display: "flex", alignItems: "center", justifyContent: "center",
  },
  card: {
    background: "#fff", borderRadius: 12, padding: "2.5rem 2rem",
    boxShadow: "0 4px 24px rgba(0,0,0,0.08)", width: 360,
    borderTop: "4px solid #2d50a0",
  },
  title: { color: "#1a2e5a", fontSize: "1.4rem", fontWeight: 700, margin: 0 },
  subtitle: { color: "#6b7fa3", fontSize: "0.85rem", marginTop: 4, marginBottom: 24 },
  field: { marginBottom: 16 },
  label: { display: "block", color: "#1a2e5a", fontSize: "0.85rem", fontWeight: 600, marginBottom: 6 },
  input: {
    width: "100%", padding: "0.6rem 0.8rem", border: "1px solid #dde3f0",
    borderRadius: 8, fontSize: "0.95rem", color: "#1a2e5a",
    outline: "none", boxSizing: "border-box",
  },
  error: { color: "#c0392b", fontSize: "0.85rem", marginBottom: 12 },
  button: {
    width: "100%", padding: "0.75rem", background: "#2d50a0",
    color: "#fff", border: "none", borderRadius: 8,
    fontSize: "1rem", fontWeight: 600, cursor: "pointer", marginTop: 8,
  },
};

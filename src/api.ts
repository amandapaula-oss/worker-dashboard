const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

function getToken() {
  return localStorage.getItem("token") || "";
}

async function apiFetch(path: string, options: RequestInit = {}, retries = 36): Promise<any> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
      ...options.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
  if (res.status === 503 && retries > 0) {
    await new Promise(r => setTimeout(r, 5000));
    return apiFetch(path, options, retries - 1);
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function login(username: string, password: string) {
  const form = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) throw new Error("Usuário ou senha incorretos");
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
}

export function logout() {
  localStorage.removeItem("token");
  window.location.href = "/login";
}

export function isAuthenticated() {
  return !!localStorage.getItem("token");
}

function buildQuery(params: Record<string, string>) {
  const q = new URLSearchParams(params);
  return q.toString() ? `?${q.toString()}` : "";
}

// ── Worker ────────────────────────────────────────────────────────────────────

export async function getCompetencias(): Promise<string[]> {
  return apiFetch("/api/competencias");
}

export async function getKPIs(params: Record<string, string>) {
  return apiFetch(`/api/kpis${buildQuery(params)}`);
}

export async function getMetricas(level: string, params: Record<string, string>) {
  return apiFetch(`/api/metricas${buildQuery({ level, ...params })}`);
}

export async function getMensal(params: Record<string, string>) {
  return apiFetch(`/api/mensal${buildQuery(params)}`);
}

// ── SAP ───────────────────────────────────────────────────────────────────────

export async function getSapFilters() {
  return apiFetch("/api/sap/filters");
}

export async function getSapData(params: Record<string, string>) {
  return apiFetch(`/api/sap/data${buildQuery(params)}`);
}

// ── Nexus ─────────────────────────────────────────────────────────────────────

export async function getNexusFilters() {
  return apiFetch("/api/nexus/filters");
}

export async function getDre(params: Record<string, string>) {
  return apiFetch(`/api/dre${buildQuery(params)}`);
}

export async function getStreams(params: Record<string, string>) {
  return apiFetch(`/api/streams${buildQuery(params)}`);
}

export async function getMatricial(params: Record<string, string>) {
  return apiFetch(`/api/matricial${buildQuery(params)}`);
}

// ── CLT ───────────────────────────────────────────────────────────────────────

export async function getCltData(params: Record<string, string>) {
  return apiFetch(`/api/clt/data${buildQuery(params)}`);
}

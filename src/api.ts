const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

function getToken() {
  return localStorage.getItem("token") || "";
}

async function apiFetch(path: string, options: RequestInit = {}, retries = 36): Promise<any> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken()}`,
        ...options.headers,
      },
    });
  } catch (err) {
    // Network error (backend sleeping / connection refused) — retry
    if (retries > 0) {
      await new Promise(r => setTimeout(r, 5000));
      return apiFetch(path, options, retries - 1);
    }
    throw err;
  }
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
  if (res.status === 503 && retries > 0) {
    await new Promise(r => setTimeout(r, 5000));
    return apiFetch(path, options, retries - 1);
  }
  if (res.status === 500 && retries > 0) {
    await new Promise(r => setTimeout(r, 3000));
    return apiFetch(path, options, retries - 1);
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function login(username: string, password: string): Promise<{ must_change_password: boolean }> {
  const form = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) throw new Error("Usuário ou senha incorretos");
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return { must_change_password: !!data.must_change_password };
}

export function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("me");
  window.location.href = "/login";
}

export function isAuthenticated() {
  return !!localStorage.getItem("token");
}

export interface MeResponse {
  username: string;
  name: string;
  email: string | null;
  is_admin: boolean;
  is_super_admin: boolean;
  must_change_password: boolean;
  bus: string[];            // BUs liberadas (vazio = admin)
  visible_bus: string[];    // BUs que devem aparecer como card
  visible_cards: string[];  // Cards da home liberados pro usuario
  all_cards: string[];      // Lista completa de cards (pro form do admin)
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch("/api/me");
}

export async function changePassword(current_password: string, new_password: string) {
  return apiFetch("/api/me/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password }),
  });
}

// ── Admin: gestao de usuarios (super_admin only) ─────────────────────────────

export interface AdminUserRow {
  username: string;
  name: string;
  email: string | null;
  bus: string[];
  is_super_admin: boolean;
  must_change_password: boolean;
  visible_cards: string[] | null;
  created_at?: string;
  last_login_at?: string | null;
}

export async function adminListUsers(): Promise<{ rows: AdminUserRow[] }> {
  return apiFetch("/api/admin/users");
}

export async function adminCreateUser(body: {
  username: string; name: string; email?: string;
  bus?: string[]; is_super_admin?: boolean;
  visible_cards?: string[] | null;
}): Promise<{ user: AdminUserRow; temp_password: string }> {
  return apiFetch("/api/admin/users", { method: "POST", body: JSON.stringify(body) });
}

export async function adminUpdateUser(username: string, body: Partial<AdminUserRow>) {
  return apiFetch(`/api/admin/users/${encodeURIComponent(username)}`, {
    method: "PATCH", body: JSON.stringify(body),
  });
}

export async function adminResetPassword(username: string): Promise<{ temp_password: string }> {
  return apiFetch(`/api/admin/users/${encodeURIComponent(username)}/reset-password`, { method: "POST" });
}

export async function adminDeleteUser(username: string) {
  return apiFetch(`/api/admin/users/${encodeURIComponent(username)}`, { method: "DELETE" });
}

export interface LoginHistoryRow {
  id: number; username: string; login_at: string;
  ip: string | null; user_agent: string | null; success: boolean;
}

export async function adminLoginHistory(limit = 200): Promise<{ rows: LoginHistoryRow[] }> {
  return apiFetch(`/api/admin/login-history?limit=${limit}`);
}

export interface OnlineRow {
  username: string; name: string; last_seen_seconds_ago: number;
}

export async function adminOnline(): Promise<{ rows: OnlineRow[] }> {
  return apiFetch("/api/admin/online");
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

// ── Metas ─────────────────────────────────────────────────────────────────────

export async function getMetasFilters() {
  return apiFetch("/api/metas/filters");
}

export async function getMetasCustoPessoal(params: Record<string, string>) {
  return apiFetch(`/api/metas/custo-pessoal${buildQuery(params)}`);
}

// ── RAC Financial ─────────────────────────────────────────────────────────────

export async function getRacFilters() {
  return apiFetch("/api/rac/filters");
}

export async function getRacProjetos(params: Record<string, string>) {
  return apiFetch(`/api/rac/projetos${buildQuery(params)}`);
}

export async function getRacPessoas(params: Record<string, string>) {
  return apiFetch(`/api/rac/pessoas${buildQuery(params)}`);
}

export async function getRacPessoaProjetos(params: Record<string, string>) {
  return apiFetch(`/api/rac/pessoa_projetos${buildQuery(params)}`);
}

// ── Margem ────────────────────────────────────────────────────────────────────

export async function getMargemFilters() {
  return apiFetch("/api/margem/filters");
}

export async function getResumo(params: Record<string, string>) {
  return apiFetch(`/api/resumo${buildQuery(params)}`);
}

export async function getMargemProjetos(params: Record<string, string>) {
  return apiFetch(`/api/margem/projetos${buildQuery(params)}`);
}

export async function getMargemPessoas(params: Record<string, string>) {
  return apiFetch(`/api/margem/pessoas${buildQuery(params)}`);
}

export async function getMargemPessoaProjetos(params: Record<string, string>) {
  return apiFetch(`/api/margem/pessoa_projetos${buildQuery(params)}`);
}

// ── Razão / Check Lucas ────────────────────────────────────────────────────────

export async function getRazaoFilters() {
  return apiFetch("/api/razao/filters");
}

export async function getRazaoComparativo(params: Record<string, string>) {
  return apiFetch(`/api/razao/comparativo${buildQuery(params)}`);
}

// ── CLT ───────────────────────────────────────────────────────────────────────

export async function getCltData(params: Record<string, string>) {
  return apiFetch(`/api/clt/data${buildQuery(params)}`);
}

// ── Apuração de Metas ─────────────────────────────────────────────────────────

export async function getApuracaoPessoas() {
  return apiFetch("/api/apuracao/pessoas");
}

export async function getApuracaoCalcular(nome: string) {
  return apiFetch(`/api/apuracao/calcular${buildQuery({ nome })}`);
}

export async function getApuracaoCalcularQ3(nome: string) {
  return apiFetch(`/api/apuracao/calcular-q3${buildQuery({ nome })}`);
}

export async function getApuracaoVisaoMaster() {
  return apiFetch("/api/apuracao/visao-master");
}

export async function getApuracaoVisaoMasterQ3() {
  return apiFetch("/api/apuracao/visao-master-q3");
}

export async function getApuracaoBonusAnual(nome: string) {
  return apiFetch(`/api/apuracao/bonus-anual/${encodeURIComponent(nome)}`);
}

export async function exportarApuracaoQ4(): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/api/apuracao/exportar-xlsx`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

// ── Clientes ──────────────────────────────────────────────────────────────────

export async function getClientes(params: Record<string, string> = {}) {
  return apiFetch(`/api/clientes${buildQuery(params)}`);
}

// ── Nova Base 2026 ────────────────────────────────────────────────────────────

export async function getNovaBaseFilters() {
  return apiFetch("/api/nova-base/filters");
}

export async function getNovaBaseData(params: Record<string, string> = {}) {
  return apiFetch(`/api/nova-base/data${buildQuery(params)}`);
}

export async function getNovaBaseResumo(params: Record<string, string> = {}) {
  return apiFetch(`/api/nova-base/resumo${buildQuery(params)}`);
}

export async function getNovaBaseDre(params: Record<string, string> = {}) {
  return apiFetch(`/api/nova-base/dre${buildQuery(params)}`);
}

export async function getNovaBasePivot(params: Record<string, string> = {}) {
  return apiFetch(`/api/nova-base/pivot${buildQuery(params)}`);
}

export async function getNovaBaseMargemClientes(params: Record<string, string> = {}) {
  return apiFetch(`/api/nova-base/margem/clientes${buildQuery(params)}`);
}
export async function getNovaBaseMargemClienteDetalhe(params: Record<string, string> = {}) {
  return apiFetch(`/api/nova-base/margem/cliente-detalhe${buildQuery(params)}`);
}
export async function getNovaBaseMargemProjetoPessoas(params: Record<string, string> = {}) {
  return apiFetch(`/api/nova-base/margem/projeto-pessoas${buildQuery(params)}`);
}
export async function getNovaBaseMargemPessoaClientes(params: Record<string, string> = {}) {
  return apiFetch(`/api/nova-base/margem/pessoa-clientes${buildQuery(params)}`);
}

export async function getBudgetVsRealizado(params: Record<string, string> = {}) {
  return apiFetch(`/api/budget-vs-realizado${buildQuery(params)}`);
}

export async function getWorkers(params: Record<string, string> = {}) {
  return apiFetch(`/api/workers${buildQuery(params)}`);
}

export async function getWorkerDetalhe(params: Record<string, string> = {}) {
  return apiFetch(`/api/workers/detalhe${buildQuery(params)}`);
}

export async function downloadNovaBase(): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/nova-base/download`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "nova_base_completa.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}

export async function clearNovaBaseCache(): Promise<any> {
  return apiFetch("/api/nova-base/clear-cache", { method: "POST" });
}

export async function uploadNovaBase(file: File): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/api/nova-base/upload-file`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateClienteAe(nome_cliente: string, ae: string) {
  return apiFetch("/api/clientes/ae", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome_cliente, ae }),
  });
}

export async function downloadApuracaoPdfQ3(nome: string): Promise<void> {
  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
  const res = await fetch(
    `${BASE_URL}/api/apuracao/pdf-q3?nome=${encodeURIComponent(nome)}`,
    { headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` } }
  );
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `apuracao_q3_${nome.replace(/ /g, "_")}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadApuracaoPdf(nome: string): Promise<void> {
  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
  const res = await fetch(
    `${BASE_URL}/api/apuracao/pdf?nome=${encodeURIComponent(nome)}`,
    { headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` } }
  );
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `apuracao_q4_${nome.replace(/ /g, "_")}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

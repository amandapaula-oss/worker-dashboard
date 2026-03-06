export interface Metrica {
  nome: string;
  receita_bruta: number;
  receita_liquida: number;
  custo: number;
  lucro_bruto: number;
  margem_bruta: number;
  [key: string]: string | number;
}

export interface Mensal {
  competencia: string;
  receita_bruta: number;
  receita_liquida: number;
  custo: number;
  lucro_bruto: number;
  margem_bruta: number;
}

export interface KPIs {
  receita_bruta: number;
  receita_liquida: number;
  custo: number;
  lucro_bruto: number;
  margem_bruta: number;
}

export interface PathItem {
  level: string;
  value: string;
  label: string;
}

export const LEVELS = ["sap_code", "client_name", "project_id", "worker_id"];
export const LEVEL_LABELS: Record<string, string> = {
  sap_code: "Empresa",
  client_name: "Cliente",
  project_id: "Projeto",
  worker_id: "Worker",
};

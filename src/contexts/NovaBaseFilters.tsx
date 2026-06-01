import React, { createContext, useContext, useState, useCallback, ReactNode } from "react";

const DEFAULT_PERIODOS = ["2026-01", "2026-02", "2026-03"];

interface NovaBaseFiltersState {
  selPeriodos: string[];      setSelPeriodos: (v: string[]) => void;
  selEmpresas: string[];      setSelEmpresas: (v: string[]) => void;
  selFontes: string[];        setSelFontes: (v: string[]) => void;
  selMacroAreas: string[];    setSelMacroAreas: (v: string[]) => void;
  selTipos: string[];         setSelTipos: (v: string[]) => void;
  selClassif: string[];       setSelClassif: (v: string[]) => void;
  selVerticais: string[];     setSelVerticais: (v: string[]) => void;
  selApuracoes: string[];     setSelApuracoes: (v: string[]) => void;
  selNoHier: string[];        setSelNoHier: (v: string[]) => void;
  selClientes: string[];      setSelClientes: (v: string[]) => void;
  resetFilters: () => void;
  hasAnyFilter: boolean;
  lockedVertical: string | null;
}

const Ctx = createContext<NovaBaseFiltersState | null>(null);

interface ProviderProps {
  children: ReactNode;
  lockedVertical?: string;
}

export function NovaBaseFiltersProvider({ children, lockedVertical }: ProviderProps) {
  const [selPeriodos, setSelPeriodos]   = useState<string[]>(DEFAULT_PERIODOS);
  const [selEmpresas, setSelEmpresas]   = useState<string[]>([]);
  const [selFontes, setSelFontes]       = useState<string[]>([]);
  const [selMacroAreas, setSelMacroAreas] = useState<string[]>([]);
  const [selTipos, setSelTipos]         = useState<string[]>([]);
  const [selClassif, setSelClassif]     = useState<string[]>([]);
  const [selVerticaisRaw, setSelVerticaisRaw] = useState<string[]>(
    lockedVertical ? [lockedVertical] : []
  );
  const [selApuracoes, setSelApuracoes] = useState<string[]>([]);
  const [selNoHier, setSelNoHier]       = useState<string[]>([]);
  const [selClientes, setSelClientes]   = useState<string[]>([]);

  // Se há BU travada, o setter ignora e força a BU fixa.
  const selVerticais = lockedVertical ? [lockedVertical] : selVerticaisRaw;
  const setSelVerticais = lockedVertical
    ? (() => { /* travado */ })
    : setSelVerticaisRaw;

  const resetFilters = useCallback(() => {
    setSelPeriodos(DEFAULT_PERIODOS);
    setSelEmpresas([]);
    setSelFontes([]);
    setSelMacroAreas([]);
    setSelTipos([]);
    setSelClassif([]);
    if (!lockedVertical) setSelVerticaisRaw([]);
    setSelApuracoes([]);
    setSelNoHier([]);
    setSelClientes([]);
  }, [lockedVertical]);

  const isPeriodosDefault = selPeriodos.length === DEFAULT_PERIODOS.length &&
    selPeriodos.every(p => DEFAULT_PERIODOS.includes(p));
  const hasAnyFilter = !isPeriodosDefault || selEmpresas.length > 0 || selFontes.length > 0
    || selMacroAreas.length > 0 || selTipos.length > 0 || selClassif.length > 0
    || (!lockedVertical && selVerticaisRaw.length > 0)
    || selApuracoes.length > 0 || selNoHier.length > 0
    || selClientes.length > 0;

  return (
    <Ctx.Provider value={{
      selPeriodos, setSelPeriodos,
      selEmpresas, setSelEmpresas,
      selFontes, setSelFontes,
      selMacroAreas, setSelMacroAreas,
      selTipos, setSelTipos,
      selClassif, setSelClassif,
      selVerticais, setSelVerticais,
      selApuracoes, setSelApuracoes,
      selNoHier, setSelNoHier,
      selClientes, setSelClientes,
      resetFilters, hasAnyFilter,
      lockedVertical: lockedVertical ?? null,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export function useNovaBaseFilters(): NovaBaseFiltersState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useNovaBaseFilters must be used inside NovaBaseFiltersProvider");
  return v;
}

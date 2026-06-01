import React, { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { getMe, MeResponse } from "../api";

const Ctx = createContext<MeResponse | null>(null);

export function MeProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeResponse | null>(() => {
    try {
      const raw = localStorage.getItem("me");
      return raw ? (JSON.parse(raw) as MeResponse) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    getMe()
      .then(r => { setMe(r); localStorage.setItem("me", JSON.stringify(r)); })
      .catch(() => { /* token invalido — apiFetch ja redireciona */ });
  }, []);

  return <Ctx.Provider value={me}>{children}</Ctx.Provider>;
}

export function useMe(): MeResponse | null {
  return useContext(Ctx);
}

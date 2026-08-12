"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createLingxiIdentityClient, type LingxiIdentityClient } from "@/lib/lingxi-identity";

interface AuthContextValue {
  client: LingxiIdentityClient | null;
  configured: boolean;
  ready: boolean;
  authenticated: boolean;
  callbackError?: string;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function LingxiIdentityProvider({ children }: { children: ReactNode }) {
  const [client, setClient] = useState<LingxiIdentityClient | null>(null);
  const [callbackError, setCallbackError] = useState<string>();
  const [configured, setConfigured] = useState(true);
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    try {
      const nextClient = createLingxiIdentityClient();
      setClient(nextClient);
      if (window.location.pathname === "/auth/callback/" || window.location.pathname === "/auth/callback") {
        void nextClient.handleCallback().then((handled) => {
          setAuthenticated(handled);
          if (handled) window.history.replaceState({}, document.title, window.location.pathname);
        }).catch((cause) => setCallbackError(cause instanceof Error ? cause.message : String(cause))).finally(() => setReady(true));
      } else {
        setReady(true);
      }
    } catch {
      setConfigured(false);
      setReady(true);
    }
  }, []);

  const login = useCallback(async () => { if (!client) throw new Error("LingxiIdentity 尚未配置。"); await client.login(); }, [client]);
  const logout = useCallback(async () => { await client?.logout(); }, [client]);
  const value = useMemo(() => ({ client, configured, ready, authenticated, callbackError, login, logout }), [authenticated, callbackError, client, configured, login, logout, ready]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useLingxiIdentity(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useLingxiIdentity must be used inside LingxiIdentityProvider");
  return value;
}

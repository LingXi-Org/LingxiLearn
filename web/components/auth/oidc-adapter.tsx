"use client";

import { LogtoProvider, useHandleSignInCallback, useLogto, type LogtoConfig } from "@logto/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { setAccessTokenProvider, setAccessTokenRefreshHandler, setAuthenticationFailureHandler } from "@/lib/api";

const endpoint = process.env.NEXT_PUBLIC_LOGTO_ENDPOINT;
const appId = process.env.NEXT_PUBLIC_LOGTO_APP_ID;
const resource = process.env.NEXT_PUBLIC_LOGTO_RESOURCE;
const POST_LOGIN_REDIRECT_KEY = "lingxilearn.post-login-redirect";
function getRedirectUri() {
  return process.env.NEXT_PUBLIC_LOGTO_REDIRECT_URI || `${window.location.origin}/auth/callback/`;
}

export const oidcConfigured = Boolean(endpoint && appId);

const config: LogtoConfig = {
  endpoint: endpoint || "https://invalid.logto.local",
  appId: appId || "unconfigured",
  scopes: ["offline_access"],
  ...(resource ? { resources: [resource] } : {}),
};

function TokenBridge() {
  const { clearAccessToken, getAccessToken, getAccessTokenClaims, isAuthenticated } = useLogto();

  useEffect(() => setAccessTokenProvider(async () => {
    if (!resource || !isAuthenticated) return null;
    try {
      return await getAccessToken(resource) || null;
    } catch {
      return null;
    }
  }), [getAccessToken, isAuthenticated]);

  useEffect(() => setAuthenticationFailureHandler(() => window.dispatchEvent(new Event("lingxilearn:auth-failed"))), []);
  useEffect(() => setAccessTokenRefreshHandler(() => clearAccessToken()), [clearAccessToken]);

  // Logto refreshes on demand by default. Schedule a silent refresh before the
  // access token expires so idle tabs do not suddenly appear offline.
  useEffect(() => {
    if (!resource || !isAuthenticated) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedule = async () => {
      try {
        const claims = await getAccessTokenClaims(resource);
        if (cancelled) return;
        const expiresAt = typeof claims?.exp === "number" ? claims.exp * 1000 : Date.now() + 5 * 60_000;
        const refreshIn = Math.max(15_000, expiresAt - Date.now() - 60_000);
        timer = setTimeout(async () => {
          if (cancelled) return;
          try {
            await clearAccessToken();
            await getAccessToken(resource);
          } catch {
            // The next scheduled attempt or an API request can recover from a
            // transient identity-provider/network failure without logging out.
          }
          if (!cancelled) void schedule();
        }, refreshIn);
      } catch {
        if (!cancelled) timer = setTimeout(() => void schedule(), 30_000);
      }
    };

    void schedule();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [clearAccessToken, getAccessToken, getAccessTokenClaims, isAuthenticated]);

  return null;
}

export function OidcAdapterProvider({ children }: { children: ReactNode }) {
  return <LogtoProvider config={config}><TokenBridge />{children}</LogtoProvider>;
}

export function useOidcAdapter() {
  const logto = useLogto();
  const [authFailed, setAuthFailed] = useState(false);
  useEffect(() => {
    const handleFailure = () => setAuthFailed(true);
    window.addEventListener("lingxilearn:auth-failed", handleFailure);
    return () => window.removeEventListener("lingxilearn:auth-failed", handleFailure);
  }, []);
  return useMemo(() => ({
    configured: oidcConfigured,
    isAuthenticated: logto.isAuthenticated && !authFailed,
    isLoading: logto.isLoading,
    error: logto.error,
    signIn: () => {
      sessionStorage.setItem(POST_LOGIN_REDIRECT_KEY, `${window.location.pathname}${window.location.search}`);
      setAuthFailed(false);
      return logto.signIn(getRedirectUri());
    },
    signOut: () => logto.signOut(window.location.origin),
  }), [authFailed, logto]);
}

export function OidcCallback() {
  const { isLoading, isAuthenticated, error } = useHandleSignInCallback(() => {
    const redirect = sessionStorage.getItem(POST_LOGIN_REDIRECT_KEY) || "/";
    sessionStorage.removeItem(POST_LOGIN_REDIRECT_KEY);
    window.location.replace(redirect);
  });

  if (isLoading) return <p>正在跳转回灵犀智学…</p>;
  if (error) return <p className="text-red-700">Logto 登录失败：{error.message}</p>;
  if (isAuthenticated) return <p>登录成功，正在进入学习工作台…</p>;
  return <p>正在处理登录回调…</p>;
}

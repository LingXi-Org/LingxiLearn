"use client";

import { LogtoProvider, useHandleSignInCallback, useLogto, type LogtoConfig } from "@logto/react";
import { useEffect, useMemo, type ReactNode } from "react";
import { setAccessTokenProvider } from "@/lib/api";

const endpoint = process.env.NEXT_PUBLIC_LOGTO_ENDPOINT;
const appId = process.env.NEXT_PUBLIC_LOGTO_APP_ID;
const resource = process.env.NEXT_PUBLIC_LOGTO_RESOURCE;
function getRedirectUri() {
  return process.env.NEXT_PUBLIC_LOGTO_REDIRECT_URI || `${window.location.origin}/auth/callback/`;
}

export const oidcConfigured = Boolean(endpoint && appId);

const config: LogtoConfig = {
  endpoint: endpoint || "https://invalid.logto.local",
  appId: appId || "unconfigured",
  ...(resource ? { resources: [resource] } : {}),
};

function TokenBridge() {
  const { getAccessToken, isAuthenticated } = useLogto();

  useEffect(() => setAccessTokenProvider(async () => {
    if (!resource || !isAuthenticated) return null;
    try {
      return await getAccessToken(resource) || null;
    } catch {
      return null;
    }
  }), [getAccessToken, isAuthenticated]);

  return null;
}

export function OidcAdapterProvider({ children }: { children: ReactNode }) {
  return <LogtoProvider config={config}><TokenBridge />{children}</LogtoProvider>;
}

export function useOidcAdapter() {
  const logto = useLogto();
  return useMemo(() => ({
    configured: oidcConfigured,
    isAuthenticated: logto.isAuthenticated,
    isLoading: logto.isLoading,
    error: logto.error,
    signIn: () => logto.signIn(getRedirectUri()),
    signOut: () => logto.signOut(window.location.origin),
  }), [logto]);
}

export function OidcCallback() {
  const { isLoading, isAuthenticated, error } = useHandleSignInCallback(() => {
    window.location.replace("/");
  });

  if (isLoading) return <p>正在跳转回灵犀智学…</p>;
  if (error) return <p className="text-red-700">Logto 登录失败：{error.message}</p>;
  if (isAuthenticated) return <p>登录成功，正在进入学习工作台…</p>;
  return <p>正在处理登录回调…</p>;
}

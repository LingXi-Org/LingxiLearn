import { OidcCallback, oidcConfigured } from "@/components/auth/oidc-adapter";

export default function AuthCallbackPage() {
  return <main className="grid min-h-dvh place-items-center bg-[var(--bg)] p-6 text-center text-sm text-[var(--text-secondary)]"><div>{oidcConfigured ? <OidcCallback /> : <><p className="font-medium text-[var(--text-primary)]">Logto 尚未配置</p><p className="mt-2 text-xs">请配置 NEXT_PUBLIC_LOGTO_ENDPOINT 和 NEXT_PUBLIC_LOGTO_APP_ID。</p></>}</div></main>;
}

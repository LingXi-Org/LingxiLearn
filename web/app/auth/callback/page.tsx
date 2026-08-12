"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useLingxiIdentity } from "@/components/auth/lingxi-identity-provider";

export default function AuthCallbackPage() {
  const { callbackError, ready, authenticated } = useLingxiIdentity();
  const router = useRouter();
  useEffect(() => {
    if (ready && authenticated) router.replace("/");
  }, [authenticated, ready, router]);
  return <main className="grid min-h-dvh place-items-center bg-[var(--bg)] p-6 text-sm text-[var(--text-secondary)]">{callbackError ? `登录失败：${callbackError}` : "正在完成 LingxiIdentity 登录…"}</main>;
}

import type { Metadata, Viewport } from "next";
import "./globals.css";
import { OidcAdapterProvider } from "@/components/auth/oidc-adapter";
import { ThemeProvider } from "@/components/theme/theme-provider";

export const metadata: Metadata = {
  title: "灵犀智学",
  description: "对话驱动的智能学习工作台。",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f4f4f5",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="icon" href="/logo_icon_white.svg" />
        <meta property="og:title" content="灵犀智学" />
        <meta property="og:description" content="对话驱动的智能学习工作台。" />
        <meta property="og:image" content="/og.png" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:image" content="/og.png" />
      </head>
      <body><ThemeProvider><OidcAdapterProvider>{children}</OidcAdapterProvider></ThemeProvider></body>
    </html>
  );
}

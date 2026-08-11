import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LingxiLearn · 工科 AI 助教",
  description:
    "面向高校工科学生的 AI 学习与工程实践助教：用真实工具处理真实任务，引导你自己得出结论。",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f8f9" },
    { media: "(prefers-color-scheme: dark)", color: "#0d1116" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-full">{children}</body>
    </html>
  );
}

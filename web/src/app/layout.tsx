import type { Metadata } from "next";
import { ja } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: ja.appTitle,
  description: ja.appSubtitle,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}

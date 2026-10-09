import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import SessionKeeper from "@/components/SessionKeeper";
import BottomNav from "@/components/BottomNav";

export const metadata: Metadata = {
  title: "Прораб",
  description: "Управление строительными объектами и задачами",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Прораб" },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const saved = cookies().get("theme")?.value;
  const theme = saved === "light" || saved === "dark" ? saved : "system";

  return (
    <html lang="ru" data-theme={theme}>
      <body>
        <SessionKeeper />
        {children}
        <BottomNav />
      </body>
    </html>
  );
}

import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";
import SessionKeeper from "@/components/SessionKeeper";
import BottomNav from "@/components/BottomNav";

export const metadata: Metadata = {
  title: { default: "ProrabTask", template: "%s · ProrabTask" },
  description: "ProrabTask — контроль, оптимизация, ремонт: управление строительными объектами и задачами",
  applicationName: "ProrabTask",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [{ url: "/icon-192.png", sizes: "192x192", type: "image/png" }],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  appleWebApp: { capable: true, statusBarStyle: "default", title: "ProrabTask" },
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
        <Analytics />
      </body>
    </html>
  );
}

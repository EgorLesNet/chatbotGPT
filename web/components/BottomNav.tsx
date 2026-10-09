"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/sites", label: "Объекты", icon: "🏗" },
  { href: "/tasks", label: "Задачи", icon: "✅" },
  { href: "/profile", label: "Профиль", icon: "👤" },
];

function matches(path: string, href: string): boolean {
  return path === href || path.startsWith(`${href}/`);
}

export default function BottomNav() {
  const path = usePathname() ?? "";
  if (!TABS.some((t) => matches(path, t.href))) return null;

  return (
    <nav className="bottom-nav" aria-label="Основное меню">
      {TABS.map((t) => {
        const active = matches(path, t.href);
        return (
          <Link key={t.href} href={t.href} className={active ? "nav-item active" : "nav-item"} aria-current={active ? "page" : undefined}>
            <span className="nav-icon" aria-hidden="true">{t.icon}</span>
            <span>{t.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

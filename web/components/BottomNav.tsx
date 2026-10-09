"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const ICON_PROPS = {
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

const TABS: { href: string; label: string; icon: ReactNode }[] = [
  {
    href: "/sites",
    label: "Объекты",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M4 21V7l8-4 8 4v14" />
        <path d="M9 21v-6h6v6" />
        <path d="M9 10h.01M15 10h.01" />
      </svg>
    ),
  },
  {
    href: "/tasks",
    label: "Задачи",
    icon: (
      <svg {...ICON_PROPS}>
        <rect x="4" y="4" width="16" height="16" rx="4" />
        <path d="m8.5 12.5 2.5 2.5 4.5-5" />
      </svg>
    ),
  },
  {
    href: "/profile",
    label: "Профиль",
    icon: (
      <svg {...ICON_PROPS}>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
      </svg>
    ),
  },
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
            <span className="nav-icon">{t.icon}</span>
            <span>{t.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

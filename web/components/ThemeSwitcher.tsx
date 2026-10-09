"use client";

import { useState } from "react";

type Theme = "system" | "light" | "dark";

const OPTIONS: { value: Theme; label: string }[] = [
  { value: "system", label: "Как в системе" },
  { value: "light", label: "Светлая" },
  { value: "dark", label: "Тёмная" },
];

export default function ThemeSwitcher({ initial }: { initial: Theme }) {
  const [theme, setTheme] = useState<Theme>(initial);

  function choose(value: Theme) {
    setTheme(value);
    document.documentElement.dataset.theme = value;
    document.cookie = `theme=${value}; path=/; max-age=31536000; samesite=lax`;
  }

  return (
    <>
      <h2>Тема оформления</h2>
      <div className="tabs three">
        {OPTIONS.map((o) => (
          <button key={o.value} type="button" className={theme === o.value ? "tab active" : "tab"} onClick={() => choose(o.value)}>
            {o.label}
          </button>
        ))}
      </div>
    </>
  );
}

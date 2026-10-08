"use client";

import { FormEvent, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { safeNext } from "@/lib/next-path";

const ERRORS: Record<string, string> = {
  "invalid or expired code": "Код неверный или истёк. Отправьте /link боту и попробуйте снова.",
  "account already linked": "Этот аккаунт уже привязан.",
  "profile already linked to another account": "Этот профиль бота уже привязан к другому аккаунту.",
  "profile already exists": "Профиль уже создан.",
  "name too short": "Введите имя (минимум 2 символа).",
  "not authenticated": "Сессия истекла. Войдите заново.",
};

function explain(message: string): string {
  if (message.includes("users_phone_key")) return "Этот телефон уже занят профилем бота. Привяжите профиль по коду из бота.";
  return ERRORS[message] ?? message;
}

export default function OnboardingPage() {
  const [tab, setTab] = useState<"link" | "new">("link");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState<"foreman" | "worker">("worker");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  function done() {
    const next = safeNext(new URLSearchParams(window.location.search).get("next")) ?? "/dashboard";
    window.location.assign(next);
  }

  async function link(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    const { error } = await createClient().rpc("link_telegram_account", { p_code: code });
    setLoading(false);
    if (error) return setMessage(explain(error.message));
    done();
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    const { error } = await createClient().rpc("create_pwa_profile", { p_name: name, p_phone: phone, p_role: role });
    setLoading(false);
    if (error) return setMessage(explain(error.message));
    done();
  }

  return (
    <main className="container narrow">
      <section className="card">
        <p className="eyebrow">ПРОФИЛЬ</p>
        <h1>Настройка профиля</h1>
        <div className="tabs">
          <button className={tab === "link" ? "tab active" : "tab"} onClick={() => setTab("link")}>Я уже в Telegram-боте</button>
          <button className={tab === "new" ? "tab active" : "tab"} onClick={() => setTab("new")}>Новый пользователь</button>
        </div>
        {tab === "link" ? (
          <form onSubmit={link} className="form">
            <p className="muted">Отправьте боту команду <b>/link</b> и введите полученный код.</p>
            <label>Код привязки<input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={12} required autoCapitalize="characters" /></label>
            <button className="button" disabled={loading}>{loading ? "Подождите…" : "Привязать"}</button>
          </form>
        ) : (
          <form onSubmit={create} className="form">
            <label>Имя<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
            <label>Телефон (необязательно)<input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
            <label>Роль
              <select value={role} onChange={(e) => setRole(e.target.value as "foreman" | "worker")}>
                <option value="worker">Рабочий</option>
                <option value="foreman">Прораб</option>
              </select>
            </label>
            <button className="button" disabled={loading}>{loading ? "Подождите…" : "Создать профиль"}</button>
          </form>
        )}
        {message && <p className="notice">{message}</p>}
      </section>
    </main>
  );
}

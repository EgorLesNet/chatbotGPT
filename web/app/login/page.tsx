"use client";

import { FormEvent, useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    const supabase = createClient();
    const result = mode === "login"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password });
    setLoading(false);
    if (result.error) {
      setMessage(result.error.message);
      return;
    }
    if (mode === "register") {
      setMessage("Аккаунт создан. Подтвердите email, если это включено в Supabase.");
      return;
    }
    window.location.assign("/dashboard");
  }

  return (
    <main className="container narrow">
      <section className="card">
        <p className="eyebrow">ПРОРАБ</p>
        <h1>{mode === "login" ? "Вход" : "Регистрация"}</h1>
        <form onSubmit={submit} className="form">
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
          <label>Пароль<input type="password" minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          <button className="button" disabled={loading}>{loading ? "Подождите…" : mode === "login" ? "Войти" : "Создать аккаунт"}</button>
        </form>
        {message && <p className="notice">{message}</p>}
        <button className="link-button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "Нет аккаунта? Зарегистрироваться" : "Уже есть аккаунт? Войти"}
        </button>
      </section>
    </main>
  );
}

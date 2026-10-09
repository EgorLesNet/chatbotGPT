"use client";

import { FormEvent, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { safeNext } from "@/lib/next-path";
import { passkeyAuth, passkeyMessage, passkeySupported } from "@/lib/passkey";

function nextPath(): string {
  return safeNext(new URLSearchParams(window.location.search).get("next")) ?? "/dashboard";
}

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [canPasskey, setCanPasskey] = useState(false);

  // The browser client refreshes an expired token itself; if a session exists, continue.
  useEffect(() => {
    setCanPasskey(passkeySupported());
    createClient().auth.getSession().then(({ data }) => {
      if (data.session) window.location.assign(nextPath());
    });
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    const supabase = createClient();
    if (mode === "register") {
      const { data, error } = await supabase.auth.signUp({ email, password });
      setLoading(false);
      if (error) {
        setMessage(error.message);
        return;
      }
      if (data.session) {
        window.location.assign(nextPath());
      } else {
        setMessage("Аккаунт создан. Подтвердите email по письму и затем войдите.");
      }
      return;
    }
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      setMessage(error.message);
      return;
    }
    window.location.assign(nextPath());
  }

  async function passkeyLogin() {
    const auth = passkeyAuth(createClient());
    if (!auth) return setMessage("Passkey не поддерживаются в этой версии сайта.");
    setLoading(true);
    setMessage("");
    const { error } = await auth.signInWithPasskey();
    setLoading(false);
    if (error) return setMessage(passkeyMessage(error));
    window.location.assign(nextPath());
  }

  return (
    <main className="container narrow">
      <section className="card">
        <p className="eyebrow">ПРОРАБ</p>
        <h1>{mode === "login" ? "Вход" : "Регистрация"}</h1>
        {mode === "login" && canPasskey && (
          <div className="actions">
            <button type="button" className="button" disabled={loading} onClick={passkeyLogin}>Войти по Passkey</button>
            <p className="muted">или по email и паролю:</p>
          </div>
        )}
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

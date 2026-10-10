"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { rpcAction } from "@/app/actions";

export default function TelegramConnect({
  connected,
  notifications,
  botUsername,
}: {
  connected: boolean;
  notifications: boolean;
  botUsername: string | null;
}) {
  const router = useRouter();
  const [code, setCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const bot = botUsername ? botUsername.replace(/^@/, "") : null;
  const deepLink = bot && code ? `https://t.me/${bot}?start=connect_${code}` : null;

  // After the user returns from Telegram, pick up the connected state without a manual refresh.
  useEffect(() => {
    if (!code || connected) return;
    const refresh = () => router.refresh();
    const onVisible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(refresh, 5000);
    const stop = window.setTimeout(() => window.clearInterval(timer), 15 * 60 * 1000);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
      window.clearTimeout(stop);
    };
  }, [code, connected, router]);

  async function bind() {
    setBusy(true);
    setError("");
    try {
      const res = await rpcAction("create_telegram_connect_code", {});
      if (res.error) {
        setError(res.error);
      } else {
        const value = String(res.data);
        setCode(value);
        if (bot) window.location.assign(`https://t.me/${bot}?start=connect_${value}`);
      }
    } catch {
      setError("Нет связи с сервером. Повторите попытку.");
    }
    setBusy(false);
  }

  async function toggle() {
    setBusy(true);
    setError("");
    try {
      const res = await rpcAction("set_notifications", { p_on: !notifications });
      if (res.error) setError(res.error);
      else router.refresh();
    } catch {
      setError("Нет связи с сервером. Повторите попытку.");
    }
    setBusy(false);
  }

  return (
    <>
      <h2>Уведомления в Telegram</h2>
      {connected ? (
        <div className="actions">
          <p className="muted">✅ Telegram подключён. Сообщения из чатов ваших объектов приходят в бота.</p>
          <button type="button" className="button small" disabled={busy} onClick={toggle}>
            {notifications ? "Уведомления включены — выключить" : "Уведомления выключены — включить"}
          </button>
          {error && <p className="notice">{error}</p>}
        </div>
      ) : (
        <div className="actions">
          <p className="muted">Привяжите бота, чтобы получать новые сообщения чата объектов в Telegram. Бот откроется сам, останется нажать «Запустить».</p>
          {!code && (
            <button type="button" className="button" disabled={busy} onClick={bind}>
              {busy ? "Подождите…" : "Привязать бота"}
            </button>
          )}
          {code && (
            <>
              {deepLink ? (
                <>
                  <p className="notice">Если бот не открылся, нажмите кнопку ниже и в чате нажмите «Запустить». Код <b>{code}</b> уже подставлен. Он действует 15 минут и работает один раз.</p>
                  <a className="button" href={deepLink}>Открыть бота</a>
                </>
              ) : (
                <p className="notice">Код: <b>{code}</b>. Отправьте боту команду <b>/connect {code}</b>. Код действует 15 минут и работает один раз.</p>
              )}
              <button type="button" className="button secondary" onClick={() => router.refresh()}>Я отправил код — проверить</button>
            </>
          )}
          {error && <p className="notice">{error}</p>}
        </div>
      )}
    </>
  );
}

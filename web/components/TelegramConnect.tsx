"use client";

import { useState } from "react";
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

  async function createCode() {
    setBusy(true);
    setError("");
    try {
      const res = await rpcAction("create_telegram_connect_code", {});
      if (res.error) setError(res.error);
      else setCode(String(res.data));
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
          <p className="muted">Подключите Telegram, чтобы получать новые сообщения чата объектов в бота.</p>
          {!code && <button type="button" className="button" disabled={busy} onClick={createCode}>{busy ? "Подождите…" : "Подключить Telegram"}</button>}
          {code && (
            <>
              <p className="notice">Код: <b>{code}</b>. Отправьте боту команду <b>/connect {code}</b>. Код действует 15 минут и работает один раз.</p>
              {botUsername && (
                <a className="button" href={`https://t.me/${botUsername}?start=connect_${code}`} target="_blank" rel="noreferrer">Открыть бота</a>
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

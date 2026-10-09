"use client";

import { useCallback, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { passkeyAuth, passkeyMessage, passkeySupported, type PasskeyItem } from "@/lib/passkey";

function fmt(value?: string): string {
  return value ? new Date(value).toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" }) : "—";
}

export default function PasskeySettings() {
  const [supported, setSupported] = useState(false);
  const [items, setItems] = useState<PasskeyItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const auth = passkeyAuth(createClient());
    if (!auth) return;
    const { data } = await auth.passkey.list();
    setItems(data ?? []);
  }, []);

  useEffect(() => {
    setSupported(passkeySupported());
    load();
  }, [load]);

  async function add() {
    const auth = passkeyAuth(createClient());
    if (!auth) return setMessage("Passkey не поддерживаются в этой версии сайта.");
    setBusy(true);
    setMessage("");
    const { error } = await auth.registerPasskey();
    setBusy(false);
    if (error) return setMessage(passkeyMessage(error));
    setMessage("Passkey добавлен. Теперь можно входить без пароля.");
    await load();
  }

  async function remove(id: string) {
    if (!confirm("Удалить этот passkey?")) return;
    const auth = passkeyAuth(createClient());
    if (!auth) return;
    setBusy(true);
    setMessage("");
    const { error } = await auth.passkey.delete({ passkeyId: id });
    setBusy(false);
    if (error) return setMessage(passkeyMessage(error));
    await load();
  }

  if (!supported) return null;

  return (
    <>
      <h2>Вход по Passkey</h2>
      <p className="muted">Вход по отпечатку, Face ID или PIN-коду устройства, без пароля.</p>
      {items.length > 0 && (
        <div className="list">
          {items.map((p) => (
            <div key={p.id} className="row row-flex">
              <span>
                <b>{p.friendly_name || "Passkey"}</b>
                <br />
                <span className="muted">Добавлен: {fmt(p.created_at)} · Вход: {fmt(p.last_used_at)}</span>
              </span>
              <button className="button danger small" disabled={busy} onClick={() => remove(p.id)}>Удалить</button>
            </div>
          ))}
        </div>
      )}
      <div className="actions">
        <button className="button" disabled={busy} onClick={add}>{busy ? "Подождите…" : "Добавить passkey"}</button>
        {message && <p className="notice">{message}</p>}
      </div>
    </>
  );
}

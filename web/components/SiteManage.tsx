"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { callRpc } from "@/lib/rpc";
import { createClient } from "@/lib/supabase/client";

type Props = { siteId: number; name: string; address: string };

export default function SiteManage({ siteId, name: initialName, address: initialAddress }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [address, setAddress] = useState(initialAddress);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [subscribed, setSubscribed] = useState<boolean | null>(null);

  async function run(fn: string, args: Record<string, unknown>, done: () => void, okText = "") {
    setBusy(true);
    setMessage("");
    const err = await callRpc(fn, args);
    setBusy(false);
    if (err) {
      setMessage(err);
      return;
    }
    if (okText) setMessage(okText);
    done();
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    run("update_site", { p_site_id: siteId, p_name: name, p_address: address }, () => router.refresh(), "Сохранено.");
  }

  async function askDelete() {
    setMessage("");
    setConfirming(true);
    setSubscribed(null);
    try {
      const { data } = await createClient().rpc("billing_status");
      const status = data as { unlocked?: boolean } | null;
      setSubscribed(Boolean(status?.unlocked));
    } catch {
      setSubscribed(null);
    }
  }

  return (
    <details className="manage">
      <summary>Управление объектом</summary>
      <form onSubmit={save} className="form">
        <label>Название<input value={name} maxLength={200} onChange={(e) => setName(e.target.value)} required /></label>
        <label>Адрес<input value={address} maxLength={300} onChange={(e) => setAddress(e.target.value)} /></label>
        <button className="button" disabled={busy}>Сохранить</button>
      </form>
      <div className="actions">
        <button
          type="button"
          className="button secondary"
          disabled={busy}
          onClick={() => {
            if (confirm("Старая ссылка-приглашение перестанет работать. Продолжить?")) {
              run("regenerate_invite", { p_site_id: siteId }, () => router.refresh(), "Ссылка обновлена.");
            }
          }}
        >
          Обновить ссылку-приглашение
        </button>
        {!confirming && (
          <button type="button" className="button danger" disabled={busy} onClick={askDelete}>
            Удалить объект
          </button>
        )}
      </div>
      {confirming && (
        <div className="actions" role="alertdialog" aria-label="Подтверждение удаления">
          <p className="notice">
            Удалить объект «{initialName}» вместе со всеми задачами, отчётами, финансами и сообщениями? Это необратимо.
          </p>
          {subscribed === false && (
            <p className="notice">
              <b>Подписки нет.</b> Место не освободится: чтобы создать новый объект после удаления, потребуется подписка.
            </p>
          )}
          <button
            type="button"
            className="button danger"
            disabled={busy}
            onClick={() => run("delete_site", { p_site_id: siteId }, () => router.push("/sites"))}
          >
            {busy ? "Удаляем…" : "Да, удалить объект"}
          </button>
          <button type="button" className="button secondary" disabled={busy} onClick={() => setConfirming(false)}>
            Отмена
          </button>
        </div>
      )}
      {message && <p className="notice">{message}</p>}
    </details>
  );
}

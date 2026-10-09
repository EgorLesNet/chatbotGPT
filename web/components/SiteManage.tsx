"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { callRpc } from "@/lib/rpc";

type Props = { siteId: number; name: string; address: string };

export default function SiteManage({ siteId, name: initialName, address: initialAddress }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [address, setAddress] = useState(initialAddress);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

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
        <button
          type="button"
          className="button danger"
          disabled={busy}
          onClick={() => {
            if (confirm("Удалить объект со всеми задачами, отчётами и сообщениями? Это необратимо.")) {
              run("delete_site", { p_site_id: siteId }, () => router.push("/sites"));
            }
          }}
        >
          Удалить объект
        </button>
      </div>
      {message && <p className="notice">{message}</p>}
    </details>
  );
}

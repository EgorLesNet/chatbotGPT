"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { callRpc } from "@/lib/rpc";

export default function NewTaskForm({ siteId }: { siteId: number }) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const err = await callRpc("create_task", {
      p_site_id: siteId,
      p_title: title,
      p_description: description,
    });
    setBusy(false);
    if (err) return setError(err);
    setTitle("");
    setDescription("");
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="form">
      <label>Название задачи<input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} required /></label>
      <label>Описание<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} /></label>
      <button className="button" disabled={busy}>{busy ? "Подождите…" : "Создать задачу"}</button>
      {error && <p className="notice">{error}</p>}
    </form>
  );
}

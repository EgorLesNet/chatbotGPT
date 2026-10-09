"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { callRpc } from "@/lib/rpc";

type Props = { taskId: number; title: string; description: string };

export default function TaskEditor({ taskId, title: initialTitle, description: initialDescription }: Props) {
  const router = useRouter();
  const [title, setTitle] = useState(initialTitle);
  const [description, setDescription] = useState(initialDescription);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const err = await callRpc("update_task", { p_task_id: taskId, p_title: title, p_description: description });
    setBusy(false);
    if (err) {
      setMessage(err);
      return;
    }
    setMessage("Сохранено.");
    router.refresh();
  }

  return (
    <details className="manage">
      <summary>Редактировать задачу</summary>
      <form onSubmit={save} className="form">
        <label>Название<input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} required /></label>
        <label>Описание<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} /></label>
        <button className="button" disabled={busy}>Сохранить</button>
      </form>
      {message && <p className="notice">{message}</p>}
    </details>
  );
}

"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { callRpc } from "@/lib/rpc";

type Role = "foreman" | "worker";

export default function ProfileForm({ name: initialName, role: initialRole }: { name: string; role: Role }) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [role, setRole] = useState<Role>(initialRole);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const err = await callRpc("update_my_profile", { p_name: name, p_role: role });
    setBusy(false);
    if (err) {
      setRole(initialRole);
      return setMessage(err);
    }
    setMessage("Сохранено.");
    router.refresh();
  }

  return (
    <>
      <h2>Данные профиля</h2>
      <form onSubmit={submit} className="form">
        <label>Имя<input value={name} maxLength={100} onChange={(e) => setName(e.target.value)} required /></label>
        <label>
          Роль
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="foreman">Прораб</option>
            <option value="worker">Рабочий</option>
          </select>
        </label>
        <p className="muted">Роль можно сменить, если нет связанных данных: у прораба — созданных объектов, у рабочего — участия в объектах и задач.</p>
        <button className="button" disabled={busy}>{busy ? "Подождите…" : "Сохранить"}</button>
        {message && <p className="notice">{message}</p>}
      </form>
    </>
  );
}

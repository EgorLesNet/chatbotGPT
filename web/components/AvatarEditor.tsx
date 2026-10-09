"use client";

import { ChangeEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { compressImage } from "@/lib/image";
import { removeAvatar, uploadAvatar } from "@/app/actions";

export default function AvatarEditor({ name, url }: { name: string; url: string | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function pick(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const small = await compressImage(file, 512, 0.85, true);
      const formData = new FormData();
      formData.append("file", small);
      const result = await uploadAvatar(formData);
      if (result.error) setError(result.error);
      else router.refresh();
    } catch {
      setError("Не удалось загрузить фото. Повторите попытку.");
    }
    setBusy(false);
  }

  async function remove() {
    setBusy(true);
    setError("");
    try {
      const result = await removeAvatar();
      if (result.error) setError(result.error);
      else router.refresh();
    } catch {
      setError("Нет связи с сервером. Повторите попытку.");
    }
    setBusy(false);
  }

  return (
    <div className="avatar-block">
      {url ? (
        <img className="avatar" src={url} alt="Аватарка" />
      ) : (
        <div className="avatar" aria-hidden="true">{name.trim().charAt(0).toUpperCase() || "?"}</div>
      )}
      <div className="actions">
        <label className={busy ? "button small file-button disabled" : "button small file-button"}>
          {busy ? "Подождите…" : url ? "Сменить фото" : "Поставить аватарку"}
          <input type="file" accept="image/*" style={{ display: "none" }} onChange={pick} disabled={busy} />
        </label>
        {url && <button type="button" className="button danger small" disabled={busy} onClick={remove}>Убрать</button>}
        {error && <p className="notice">{error}</p>}
      </div>
    </div>
  );
}

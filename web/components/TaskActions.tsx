"use client";

import { ChangeEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { callRpc, uploadPhoto } from "@/lib/rpc";
import { compressImage } from "@/lib/image";

type Props = {
  taskId: number;
  siteId: number;
  canTake: boolean;
  canSubmit: boolean;
  canReview: boolean;
  canDelete: boolean;
  canRelease: boolean;
  releaseLabel: string;
  canReopen: boolean;
};

type Photo = { file: File; url: string };

const MAX_PHOTOS = 10;

export default function TaskActions({
  taskId, siteId, canTake, canSubmit, canReview, canDelete, canRelease, releaseLabel, canReopen,
}: Props) {
  const router = useRouter();
  const [comment, setComment] = useState("");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function call(fn: string, args: Record<string, unknown>, after?: () => void) {
    setBusy(true);
    setError("");
    const err = await callRpc(fn, args);
    setBusy(false);
    if (err) {
      setError(err);
      return;
    }
    setComment("");
    if (after) after();
    else router.refresh();
  }

  async function addPhotos(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    setBusy(true);
    setError("");
    try {
      const added: Photo[] = [];
      for (const f of files) {
        if (photos.length + added.length >= MAX_PHOTOS) break;
        const compressed = await compressImage(f);
        added.push({ file: compressed, url: URL.createObjectURL(compressed) });
      }
      setPhotos((prev) => [...prev, ...added]);
    } catch {
      setError("Не удалось обработать фото. Попробуйте другое.");
    }
    setBusy(false);
  }

  function removePhoto(index: number) {
    setPhotos((prev) => {
      URL.revokeObjectURL(prev[index].url);
      return prev.filter((_, i) => i !== index);
    });
  }

  async function submitReport() {
    if (!comment.trim()) return setError("Напишите комментарий к отчёту.");
    if (!photos.length) return setError("Добавьте хотя бы одно фото.");

    setBusy(true);
    setError("");
    const paths: string[] = [];
    for (const photo of photos) {
      const result = await uploadPhoto(taskId, photo.file);
      if (result.error || !result.path) {
        setBusy(false);
        setError(result.error ?? "Не удалось загрузить фото.");
        return;
      }
      paths.push(result.path);
    }

    const err = await callRpc("submit_task", { p_task_id: taskId, p_comment: comment, p_photos: paths });
    setBusy(false);
    if (err) return setError(err);

    photos.forEach((p) => URL.revokeObjectURL(p.url));
    setPhotos([]);
    setComment("");
    router.refresh();
  }

  if (!canTake && !canSubmit && !canReview && !canDelete && !canRelease && !canReopen) return null;

  return (
    <div className="actions">
      {canTake && (
        <button className="button" disabled={busy} onClick={() => call("take_task", { p_task_id: taskId })}>
          Взять в работу
        </button>
      )}

      {canSubmit && (
        <>
          <label>
            Комментарий (обязательно)
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} />
          </label>
          <label>
            Фото результата (обязательно, до {MAX_PHOTOS})
            <input type="file" accept="image/*" multiple onChange={addPhotos} disabled={busy || photos.length >= MAX_PHOTOS} />
          </label>
          {photos.length > 0 && (
            <div className="photos">
              {photos.map((p, i) => (
                <div key={p.url} className="thumb">
                  <img src={p.url} alt={`Фото ${i + 1}`} />
                  <button type="button" className="thumb-remove" onClick={() => removePhoto(i)} aria-label="Убрать фото">×</button>
                </div>
              ))}
            </div>
          )}
          <button className="button" disabled={busy} onClick={submitReport}>
            {busy ? "Подождите…" : "Сдать на проверку"}
          </button>
        </>
      )}

      {canReview && (
        <>
          <label>
            Комментарий
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} />
          </label>
          <div className="row-actions">
            <button className="button" disabled={busy} onClick={() => call("review_task", { p_task_id: taskId, p_accept: true, p_comment: comment })}>
              Принять
            </button>
            <button className="button secondary" disabled={busy} onClick={() => call("review_task", { p_task_id: taskId, p_accept: false, p_comment: comment })}>
              На доработку
            </button>
          </div>
        </>
      )}

      {canRelease && (
        <button className="button secondary" disabled={busy} onClick={() => call("release_task", { p_task_id: taskId })}>
          {releaseLabel}
        </button>
      )}

      {canReopen && (
        <button className="button secondary" disabled={busy} onClick={() => call("reopen_task", { p_task_id: taskId })}>
          Вернуть в работу
        </button>
      )}

      {canDelete && (
        <button
          className="button danger"
          disabled={busy}
          onClick={() => {
            if (confirm("Удалить задачу?")) call("delete_task", { p_task_id: taskId }, () => router.push(`/sites/${siteId}`));
          }}
        >
          Удалить задачу
        </button>
      )}

      {error && <p className="notice">{error}</p>}
    </div>
  );
}

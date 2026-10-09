"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { explain } from "@/lib/errors";

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

export default function TaskActions({
  taskId, siteId, canTake, canSubmit, canReview, canDelete, canRelease, releaseLabel, canReopen,
}: Props) {
  const router = useRouter();
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function call(fn: string, args: Record<string, unknown>, after?: () => void) {
    setBusy(true);
    setError("");
    const { error } = await createClient().rpc(fn, args);
    setBusy(false);
    if (error) {
      setError(explain(error.message));
      return;
    }
    setComment("");
    if (after) after();
    else router.refresh();
  }

  if (!canTake && !canSubmit && !canReview && !canDelete && !canRelease && !canReopen) return null;

  return (
    <div className="actions">
      {canTake && (
        <button className="button" disabled={busy} onClick={() => call("take_task", { p_task_id: taskId })}>
          Взять в работу
        </button>
      )}

      {(canSubmit || canReview) && (
        <label>
          Комментарий
          <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} />
        </label>
      )}

      {canSubmit && (
        <button className="button" disabled={busy} onClick={() => call("submit_task", { p_task_id: taskId, p_comment: comment })}>
          Сдать на проверку
        </button>
      )}

      {canReview && (
        <div className="row-actions">
          <button className="button" disabled={busy} onClick={() => call("review_task", { p_task_id: taskId, p_accept: true, p_comment: comment })}>
            Принять
          </button>
          <button className="button secondary" disabled={busy} onClick={() => call("review_task", { p_task_id: taskId, p_accept: false, p_comment: comment })}>
            На доработку
          </button>
        </div>
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

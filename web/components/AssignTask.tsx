"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { callRpc } from "@/lib/rpc";

type Worker = { id: number; name: string };
type Props = { taskId: number; workers: Worker[]; currentId: number | null };

export default function AssignTask({ taskId, workers, currentId }: Props) {
  const router = useRouter();
  const [workerId, setWorkerId] = useState<string>(currentId ? String(currentId) : workers[0] ? String(workers[0].id) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!workers.length) return <p className="muted">Назначить некого: на объекте нет рабочих.</p>;

  async function assign() {
    setBusy(true);
    setError("");
    const err = await callRpc("assign_task", { p_task_id: taskId, p_worker_id: Number(workerId) });
    setBusy(false);
    if (err) setError(err);
    else router.refresh();
  }

  return (
    <div className="actions">
      <label>
        Назначить исполнителя
        <select value={workerId} onChange={(e) => setWorkerId(e.target.value)}>
          {workers.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
      </label>
      <button type="button" className="button" disabled={busy || !workerId} onClick={assign}>Назначить</button>
      {error && <p className="notice">{error}</p>}
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { callRpc } from "@/lib/rpc";

type Props = { siteId: number; workerId: number; name: string };

export default function RemoveMember({ siteId, workerId, name }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    if (!confirm(`Убрать ${name} с объекта? Его задачи в работе вернутся в список открытых.`)) return;
    setBusy(true);
    setError("");
    const err = await callRpc("remove_member", { p_site_id: siteId, p_worker_id: workerId });
    setBusy(false);
    if (err) setError(err);
    else router.refresh();
  }

  return (
    <span>
      <button type="button" className="button danger small" disabled={busy} onClick={remove}>Убрать</button>
      {error && <span className="muted"> {error}</span>}
    </span>
  );
}

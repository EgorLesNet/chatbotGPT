"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import CopyLink from "@/components/CopyLink";
import { bizRpc } from "@/app/biz-actions";

export default function ClientLink({ siteId, token }: { siteId: number; token: string | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(fn: "enable_client_link" | "disable_client_link") {
    if (fn === "disable_client_link" && !confirm("Отключить ссылку? Заказчик больше не увидит объект по ней.")) return;
    setBusy(true);
    setError("");
    try {
      const res = await bizRpc(fn, { p_site: siteId });
      if (res.error) setError(res.error);
      else router.refresh();
    } catch {
      setError("Нет связи с сервером. Повторите попытку.");
    }
    setBusy(false);
  }

  return (
    <div className="actions">
      <p className="muted">Только просмотр: статус задач и смета, без регистрации. Финансы, рабочие и фото не показываются.</p>
      {token ? (
        <>
          <CopyLink path={`/view/${token}`} />
          <button type="button" className="button small secondary" disabled={busy} onClick={() => run("disable_client_link")}>Отключить ссылку</button>
        </>
      ) : (
        <button type="button" className="button small" disabled={busy} onClick={() => run("enable_client_link")}>{busy ? "Подождите…" : "Создать ссылку для заказчика"}</button>
      )}
      {error && <p className="notice">{error}</p>}
    </div>
  );
}

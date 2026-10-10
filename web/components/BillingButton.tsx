"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { checkPayment, startPayment } from "@/app/biz-actions";

export default function BillingButton({ price, renew }: { price: number; renew: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function pay() {
    setBusy(true);
    setError("");
    try {
      const res = await startPayment();
      if (res.error || !res.url) {
        setError(res.error ?? "Не удалось создать платёж.");
        setBusy(false);
        return;
      }
      window.location.href = res.url;
    } catch {
      setError("Нет связи с сервером. Повторите попытку.");
      setBusy(false);
    }
  }

  async function check() {
    setBusy(true);
    setError("");
    try {
      const res = await checkPayment();
      if (res.error) setError(res.error);
      else if (!res.unlocked) setError("Оплата пока не найдена. Если вы уже заплатили, подождите минуту и проверьте ещё раз.");
      router.refresh();
    } catch {
      setError("Нет связи с сервером. Повторите попытку.");
    }
    setBusy(false);
  }

  return (
    <div className="actions">
      <button type="button" className="button" disabled={busy} onClick={pay}>
        {busy ? "Подождите…" : renew ? `Продлить на 30 дней — ${price} ₽` : `Оформить подписку — ${price} ₽ в месяц`}
      </button>
      <button type="button" className="button secondary" disabled={busy} onClick={check}>Я уже оплатил — проверить</button>
      {error && <p className="notice">{error}</p>}
    </div>
  );
}

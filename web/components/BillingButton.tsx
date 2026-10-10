"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function BillingButton({ url, price, renew }: { url: string | null; price: number; renew: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  if (!url) {
    return <p className="notice">Оплата ещё не настроена: не задана ссылка на подписку Tribute (TRIBUTE_SUBSCRIPTION_URL).</p>;
  }

  function refresh() {
    setBusy(true);
    router.refresh();
    setTimeout(() => setBusy(false), 1500);
  }

  return (
    <div className="actions">
      <a className="button" href={url} target="_blank" rel="noopener noreferrer">
        {renew ? `Управлять подпиской в Tribute — ${price} ₽/мес` : `Оформить подписку в Tribute — ${price} ₽/мес`}
      </a>
      <button type="button" className="button secondary" disabled={busy} onClick={refresh}>
        {busy ? "Проверяем…" : "Я оплатил — обновить статус"}
      </button>
    </div>
  );
}

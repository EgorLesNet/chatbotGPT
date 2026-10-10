import Link from "next/link";
import { getProfile } from "@/lib/profile";
import BillingButton from "@/components/BillingButton";

export const dynamic = "force-dynamic";

type Status = {
  sites: number;
  free_limit: number;
  price: number;
  period_days: number;
  paid_until: string | null;
  telegram_linked: boolean;
  unlocked: boolean;
};

function formatDate(value: string): string {
  const hasZone = /[zZ]$|[+-]\d\d:?\d\d$/.test(value);
  return new Date(hasZone ? value : `${value}Z`).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export default async function BillingPage() {
  const { supabase, profile } = await getProfile();

  if (profile.role !== "foreman") {
    return (
      <main className="container">
        <section className="card">
          <h1>Подписка</h1>
          <p className="muted">Для рабочих оплата не требуется: подписка нужна только прорабам.</p>
        </section>
      </main>
    );
  }

  await supabase.rpc("claim_tribute");
  const { data, error } = await supabase.rpc("billing_status");
  const status = data as unknown as Status | null;
  const url = process.env.TRIBUTE_SUBSCRIPTION_URL ?? null;

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href="/sites">← К объектам</Link>
        <h1>Подписка прораба</h1>
        {error && <p className="notice">Не удалось загрузить данные: {error.message}. Выполните SQL-файлы supabase_pwa_subscription.sql и supabase_pwa_tribute.sql.</p>}
        {status && (
          <>
            <div className="list">
              <div className="row row-flex"><span>Тариф «Бесплатный»</span><b>до {status.free_limit} объектов</b></div>
              <div className="row row-flex"><span>Тариф «Подписка»</span><b>больше {status.free_limit} объектов — {status.price} ₽ в месяц</b></div>
            </div>
            <p>Сейчас у вас объектов: <b>{status.sites}</b>.</p>

            {status.unlocked && status.paid_until ? (
              <p className="notice">✅ Подписка активна до {formatDate(status.paid_until)}. Можно создавать больше {status.free_limit} объектов. Если подписку не отменять, Tribute продлит её автоматически.</p>
            ) : (
              <p className="muted">
                {status.paid_until ? `Подписка закончилась ${formatDate(status.paid_until)}. ` : ""}
                Вы платите за доступ к большему количеству объектов: с подпиской можно создавать новые объекты сверх {status.free_limit}. Без подписки уже созданные объекты остаются доступными, но новый объект сверх лимита создать нельзя.
              </p>
            )}

            {!status.telegram_linked && (
              <p className="notice">⚠️ К вашему профилю не привязан Telegram. Подписка оформляется в Telegram и сопоставляется с вами по Telegram ID, поэтому сначала привяжите Telegram, а оплачивайте с того же аккаунта.</p>
            )}

            <BillingButton url={url} price={status.price} renew={status.unlocked} />
            <p className="muted">Оплата через Tribute (карта, СБП или Telegram Stars). Подписка продлевается каждые {status.period_days} дней автоматически, пока вы её не отмените в Tribute. После отмены доступ сохраняется до конца оплаченного срока.</p>
          </>
        )}
      </section>
    </main>
  );
}

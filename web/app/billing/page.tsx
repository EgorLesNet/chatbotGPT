import Link from "next/link";
import { getProfile } from "@/lib/profile";
import { verifyAndConfirm } from "@/lib/billing";
import BillingButton from "@/components/BillingButton";

export const dynamic = "force-dynamic";

type Status = {
  sites: number;
  free_limit: number;
  price: number;
  period_days: number;
  paid_until: string | null;
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

  // Back from the payment page: confirm a pending payment right away, without waiting for the webhook.
  const { data: pending } = await supabase.rpc("my_pending_payment");
  if (pending) await verifyAndConfirm(String(pending));

  const { data, error } = await supabase.rpc("billing_status");
  const status = data as unknown as Status | null;

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href="/sites">← К объектам</Link>
        <h1>Подписка прораба</h1>
        {error && <p className="notice">Не удалось загрузить данные: {error.message}. Выполните SQL-файлы supabase_pwa_business.sql и supabase_pwa_subscription.sql.</p>}
        {status && (
          <>
            <div className="list">
              <div className="row row-flex"><span>Тариф «Бесплатный»</span><b>до {status.free_limit} объектов</b></div>
              <div className="row row-flex"><span>Тариф «Подписка»</span><b>больше {status.free_limit} объектов — {status.price} ₽ за {status.period_days} дней</b></div>
            </div>
            <p>Сейчас у вас объектов: <b>{status.sites}</b>.</p>

            {status.unlocked && status.paid_until ? (
              <p className="notice">✅ Подписка активна до {formatDate(status.paid_until)}. Можно создавать больше {status.free_limit} объектов.</p>
            ) : (
              <p className="muted">
                {status.paid_until ? `Подписка закончилась ${formatDate(status.paid_until)}. ` : ""}
                Вы платите за доступ к большему количеству объектов: с подпиской можно создавать новые объекты сверх {status.free_limit}. Без подписки уже созданные объекты остаются доступны, но новый объект сверх лимита создать нельзя.
              </p>
            )}

            <BillingButton price={status.price} renew={status.unlocked} />
            <p className="muted">Оплата через ЮKassa (карта или СБП). Подписка не продлевается автоматически: оплата списывается только когда вы сами нажимаете кнопку. Повторная оплата добавляет ещё {status.period_days} дней к текущему сроку.</p>
          </>
        )}
      </section>
    </main>
  );
}

import Link from "next/link";
import { getProfile } from "@/lib/profile";
import { verifyAndConfirm } from "@/lib/billing";
import BillingButton from "@/components/BillingButton";

export const dynamic = "force-dynamic";

type Status = { sites: number; free_limit: number; price: number; unlocked: boolean };

export default async function BillingPage() {
  const { supabase, profile } = await getProfile();

  if (profile.role !== "foreman") {
    return (
      <main className="container">
        <section className="card">
          <h1>Оплата</h1>
          <p className="muted">Для рабочих оплата не требуется.</p>
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
        <h1>Оплата</h1>
        {error && <p className="notice">Не удалось загрузить данные: {error.message}. Выполните SQL-файл supabase_pwa_business.sql.</p>}
        {status && (
          <>
            <p>Объектов: <b>{status.sites}</b>. Бесплатно можно вести {status.free_limit}.</p>
            {status.unlocked ? (
              <p className="notice">✅ Доступ оплачен: можно создавать любое число объектов.</p>
            ) : (
              <>
                <p className="muted">Чтобы создать больше {status.free_limit} объектов, оплатите доступ один раз: {status.price} ₽. Платёж проходит через ЮKassa, оплатить можно картой или через СБП.</p>
                <BillingButton price={status.price} />
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}

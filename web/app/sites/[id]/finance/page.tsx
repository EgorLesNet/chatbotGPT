import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getProfile } from "@/lib/profile";
import { rub } from "@/lib/money";
import FinanceManager from "@/components/FinanceManager";
import type { EstimateItem, FinanceEntry, WorkerOption } from "@/components/FinanceManager";

type Overview = {
  advance: number;
  expense: number;
  salary: number;
  estimate_total: number;
  entries: FinanceEntry[];
  estimate_items: EstimateItem[];
  workers: WorkerOption[];
};

export default async function FinancePage({ params }: { params: { id: string } }) {
  const siteId = Number(params.id);
  if (!Number.isInteger(siteId)) notFound();

  const { supabase, profile } = await getProfile();
  if (profile.role !== "foreman") redirect(`/sites/${siteId}`);

  const { data: site } = await supabase.from("sites").select("id, name").eq("id", siteId).maybeSingle();
  if (!site) notFound();
  const siteName = (site as unknown as { name: string }).name;

  const { data, error } = await supabase.rpc("finance_overview", { p_site: siteId });
  const o = data as unknown as Overview | null;
  const spent = o ? Number(o.expense) + Number(o.salary) : 0;
  const balance = o ? Number(o.advance) - spent : 0;

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href={`/sites/${siteId}`}>← К объекту</Link>
        <h1>💰 {siteName}</h1>
        {error && <p className="notice">Финансы недоступны: {error.message}. Выполните SQL-файл supabase_pwa_business.sql.</p>}
        {o && (
          <>
            <div className="list">
              <div className="row row-flex"><span>Авансы от заказчика</span><b>{rub(o.advance)}</b></div>
              <div className="row row-flex"><span>Расходы</span><b>{rub(o.expense)}</b></div>
              <div className="row row-flex"><span>Зарплата</span><b>{rub(o.salary)}</b></div>
              <div className="row row-flex"><span>Остаток (авансы − расходы − зарплата)</span><b>{rub(balance)}</b></div>
              <div className="row row-flex"><span>Смета (план)</span><b>{rub(o.estimate_total)}</b></div>
              <div className="row row-flex"><span>Потрачено от сметы</span><b>{o.estimate_total > 0 ? `${Math.round((spent / Number(o.estimate_total)) * 100)}%` : "—"}</b></div>
            </div>
            <FinanceManager siteId={siteId} workers={o.workers} entries={o.entries} estimateItems={o.estimate_items} />
          </>
        )}
      </section>
    </main>
  );
}

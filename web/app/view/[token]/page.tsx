import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { STATUS_LABEL } from "@/lib/status";
import { rub } from "@/lib/money";

export const dynamic = "force-dynamic";
export const metadata = { title: "Объект — просмотр", robots: { index: false, follow: false } };

type View = {
  name: string;
  address: string;
  tasks: { title: string; status: string }[];
  estimate_items: { title: string; qty: number; unit: string; price: number }[];
  estimate_total: number;
};

export default async function ClientViewPage({ params }: { params: { token: string } }) {
  const supabase = createClient();
  const { data } = await supabase.rpc("get_client_view", { p_token: params.token });
  if (!data) notFound();
  const v = data as unknown as View;

  const done = v.tasks.filter((t) => t.status === "done").length;

  return (
    <main className="container">
      <section className="card">
        <p className="eyebrow">ПРОСМОТР ДЛЯ ЗАКАЗЧИКА</p>
        <h1>{v.name}</h1>
        <p className="muted">{v.address}</p>

        <h2>Ход работ</h2>
        {!v.tasks.length ? (
          <p className="muted">Задач пока нет.</p>
        ) : (
          <>
            <p>Выполнено {done} из {v.tasks.length}</p>
            <progress value={done} max={v.tasks.length} style={{ width: "100%" }} />
            <div className="list">
              {v.tasks.map((t, i) => (
                <div key={i} className="row row-flex">
                  <b>{t.title}</b>
                  <span className="muted">{STATUS_LABEL[t.status] ?? t.status}</span>
                </div>
              ))}
            </div>
          </>
        )}

        <h2>Смета</h2>
        {!v.estimate_items.length ? (
          <p className="muted">Смета пока не добавлена.</p>
        ) : (
          <div className="list">
            {v.estimate_items.map((i, n) => (
              <div key={n} className="row row-flex">
                <span>
                  <b>{i.title}</b>
                  <br />
                  <span className="muted">{i.qty} {i.unit} × {rub(i.price)}</span>
                </span>
                <b>{rub(i.qty * i.price)}</b>
              </div>
            ))}
            <div className="row row-flex"><b>Итого</b><b>{rub(v.estimate_total)}</b></div>
          </div>
        )}
      </section>
    </main>
  );
}

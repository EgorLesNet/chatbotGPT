import { redirect, notFound } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

const STATUS: Record<string, string> = {
  open: "🔵 Открыта",
  in_progress: "🟡 В работе",
  review: "🟠 На проверке",
  done: "🟢 Выполнена",
};

export default async function SitePage({ params }: { params: { id: string } }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const siteId = Number(params.id);
  if (!Number.isInteger(siteId)) notFound();

  const { data: site } = await supabase.from("sites").select("id, name, address").eq("id", siteId).maybeSingle();
  if (!site) notFound();
  const { data: tasks } = await supabase.from("tasks").select("id, title, status").eq("site_id", siteId).order("created_at", { ascending: false });

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href="/sites">← Назад</Link>
        <h1>{site.name}</h1>
        <p className="muted">{site.address}</p>
        <h2>Задачи</h2>
        {!tasks?.length && <p className="muted">Задач пока нет.</p>}
        <div className="list">
          {tasks?.map((t) => (
            <div key={t.id} className="row">
              <b>{t.title}</b>
              <span className="muted">{STATUS[t.status] ?? t.status}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

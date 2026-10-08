import Link from "next/link";
import { getProfile } from "@/lib/profile";
import { STATUS_KEYS, STATUS_LABEL } from "@/lib/status";

type TaskRow = { id: number; title: string; status: string; sites: { name: string } | null };

export default async function TasksPage({ searchParams }: { searchParams: { status?: string } }) {
  const { supabase } = await getProfile();
  const filter = searchParams.status && STATUS_KEYS.includes(searchParams.status) ? searchParams.status : null;

  let query = supabase.from("tasks").select("id, title, status, sites(name)").order("created_at", { ascending: false });
  if (filter) query = query.eq("status", filter);
  const { data } = await query;
  const tasks = (data ?? []) as unknown as TaskRow[];

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href="/dashboard">← Назад</Link>
        <h1>Задачи</h1>
        <div className="chips">
          <Link className={!filter ? "chip active" : "chip"} href="/tasks">Все</Link>
          {STATUS_KEYS.map((k) => (
            <Link key={k} className={filter === k ? "chip active" : "chip"} href={`/tasks?status=${k}`}>{STATUS_LABEL[k]}</Link>
          ))}
        </div>
        {!tasks.length && <p className="muted">Задач нет.</p>}
        <div className="list">
          {tasks.map((t) => (
            <Link key={t.id} className="row" href={`/tasks/${t.id}`}>
              <b>{t.title}</b>
              <span className="muted">{STATUS_LABEL[t.status] ?? t.status} · {t.sites?.name ?? "—"}</span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}

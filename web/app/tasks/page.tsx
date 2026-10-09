import Link from "next/link";
import { getProfile } from "@/lib/profile";
import { STATUS_KEYS, STATUS_LABEL } from "@/lib/status";

type TaskRow = {
  id: number;
  title: string;
  status: string;
  site_id: number;
  sites: { name: string } | null;
};

export default async function TasksPage({ searchParams }: { searchParams: { status?: string } }) {
  const { supabase } = await getProfile();
  const filter = searchParams.status && STATUS_KEYS.includes(searchParams.status) ? searchParams.status : null;

  let query = supabase
    .from("tasks")
    .select("id, title, status, site_id, sites(name)")
    .order("site_id", { ascending: true })
    .order("created_at", { ascending: false });
  if (filter) query = query.eq("status", filter);
  const { data } = await query;
  const tasks = (data ?? []) as unknown as TaskRow[];

  const groups = new Map<number, { name: string; tasks: TaskRow[] }>();
  for (const t of tasks) {
    const group = groups.get(t.site_id) ?? { name: t.sites?.name ?? "Без объекта", tasks: [] };
    group.tasks.push(t);
    groups.set(t.site_id, group);
  }

  return (
    <main className="container">
      <section className="card">
        <h1>Задачи</h1>
        <div className="chips">
          <Link className={!filter ? "chip active" : "chip"} href="/tasks">Все</Link>
          {STATUS_KEYS.map((k) => (
            <Link key={k} className={filter === k ? "chip active" : "chip"} href={`/tasks?status=${k}`}>{STATUS_LABEL[k]}</Link>
          ))}
        </div>
        {!tasks.length && <p className="muted">Задач нет.</p>}
        {Array.from(groups.entries()).map(([siteId, group]) => (
          <div key={siteId}>
            <h2 className="group-title">
              <Link href={`/sites/${siteId}`}>🏗 {group.name}</Link>
              <span className="count">{group.tasks.length}</span>
            </h2>
            <div className="list">
              {group.tasks.map((t) => (
                <Link key={t.id} className="row" href={`/tasks/${t.id}`}>
                  <b>{t.title}</b>
                  <span className="muted">{STATUS_LABEL[t.status] ?? t.status}</span>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}

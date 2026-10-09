import Link from "next/link";
import { getProfile } from "@/lib/profile";
import { STATUS_KEYS, STATUS_LABEL } from "@/lib/status";

type SiteRow = { id: number; name: string; address: string };
type TaskRow = { id: number; site_id: number; title: string; status: string };

export default async function SitesPage() {
  const { supabase, profile } = await getProfile();
  const isForeman = profile.role === "foreman";

  const { data, error } = await supabase
    .from("sites")
    .select("id, name, address")
    .order("created_at", { ascending: false });
  const sites = (data ?? []) as unknown as SiteRow[];

  const { data: taskData } = await supabase
    .from("tasks")
    .select("id, site_id, title, status")
    .order("created_at", { ascending: false });
  const tasks = (taskData ?? []) as unknown as TaskRow[];

  const bySite = new Map<number, TaskRow[]>();
  for (const t of tasks) {
    const list = bySite.get(t.site_id) ?? [];
    list.push(t);
    bySite.set(t.site_id, list);
  }

  return (
    <main className="container">
      <section className="card">
        <h1>Объекты</h1>
        {isForeman && <Link className="button" href="/sites/new">+ Создать объект</Link>}
        {error && <p className="notice">Ошибка загрузки объектов: {error.message}</p>}
        {!error && !sites.length && (
          <p className="muted">
            {isForeman ? "Объектов пока нет." : "Нет доступных объектов. Откройте ссылку-приглашение от прораба."}
          </p>
        )}
        <div className="list">
          {sites.map((s) => {
            const siteTasks = bySite.get(s.id) ?? [];
            return (
              <details key={s.id} className="site">
                <summary>
                  <b>🏗 {s.name}</b>
                  <span className="muted">{s.address}</span>
                  <span className="counts">
                    {siteTasks.length === 0 && <span className="count">Задач нет</span>}
                    {STATUS_KEYS.map((k) => {
                      const n = siteTasks.filter((t) => t.status === k).length;
                      return n > 0 ? <span key={k} className="count">{STATUS_LABEL[k]}: {n}</span> : null;
                    })}
                  </span>
                </summary>
                <div className="list inner">
                  {siteTasks.map((t) => (
                    <Link key={t.id} className="row" href={`/tasks/${t.id}`}>
                      <b>{t.title}</b>
                      <span className="muted">{STATUS_LABEL[t.status] ?? t.status}</span>
                    </Link>
                  ))}
                  <Link className="button small" href={`/sites/${s.id}`}>Открыть объект</Link>
                </div>
              </details>
            );
          })}
        </div>
      </section>
    </main>
  );
}

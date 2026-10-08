import Link from "next/link";
import { notFound } from "next/navigation";
import { getProfile } from "@/lib/profile";
import { STATUS_LABEL } from "@/lib/status";
import TaskActions from "@/components/TaskActions";

type TaskRow = {
  id: number; site_id: number; title: string; description: string;
  status: string; taken_by_id: number | null; created_at: string;
};
type SiteRow = { id: number; name: string; foreman_id: number };
type NoteRow = { id: number; comment: string; created_at: string };

function fmt(value: string): string {
  return new Date(value).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
}

export default async function TaskPage({ params }: { params: { id: string } }) {
  const { supabase, profile } = await getProfile();
  const taskId = Number(params.id);
  if (!Number.isInteger(taskId)) notFound();

  const { data: taskData } = await supabase
    .from("tasks")
    .select("id, site_id, title, description, status, taken_by_id, created_at")
    .eq("id", taskId)
    .maybeSingle();
  if (!taskData) notFound();
  const task = taskData as unknown as TaskRow;

  const { data: siteData } = await supabase
    .from("sites")
    .select("id, name, foreman_id")
    .eq("id", task.site_id)
    .maybeSingle();
  const site = siteData as unknown as SiteRow | null;

  let workerName: string | null = null;
  if (task.taken_by_id) {
    const { data: w } = await supabase.from("users").select("name").eq("id", task.taken_by_id).maybeSingle();
    workerName = (w as unknown as { name: string } | null)?.name ?? null;
  }

  const { data: reportData } = await supabase
    .from("task_reports")
    .select("id, comment, created_at")
    .eq("task_id", taskId)
    .order("created_at", { ascending: false })
    .limit(5);
  const reports = (reportData ?? []) as unknown as NoteRow[];

  const { data: reviewData } = await supabase
    .from("task_reviews")
    .select("id, comment, created_at")
    .eq("task_id", taskId)
    .order("created_at", { ascending: false })
    .limit(5);
  const reviews = (reviewData ?? []) as unknown as NoteRow[];

  const isForeman = profile.role === "foreman" && site?.foreman_id === profile.id;
  const isWorker = profile.role === "worker";
  const canTake = isWorker && task.status === "open";
  const canSubmit = isWorker && task.status === "in_progress" && task.taken_by_id === profile.id;
  const canReview = isForeman && task.status === "review";

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href={`/sites/${task.site_id}`}>← {site?.name ?? "К объекту"}</Link>
        <h1>{task.title}</h1>
        <p><span className="badge">{STATUS_LABEL[task.status] ?? task.status}</span></p>
        {task.description && <p className="muted pre">{task.description}</p>}
        <p className="muted">Создана: {fmt(task.created_at)}{workerName ? ` · Исполнитель: ${workerName}` : ""}</p>

        <TaskActions
          taskId={task.id}
          siteId={task.site_id}
          canTake={canTake}
          canSubmit={canSubmit}
          canReview={canReview}
          canDelete={isForeman}
        />

        {reports.length > 0 && (
          <>
            <h2>Отчёты рабочих</h2>
            <div className="list">
              {reports.map((r) => (
                <div key={r.id} className="row"><span className="pre">{r.comment || "Без комментария"}</span><span className="muted">{fmt(r.created_at)}</span></div>
              ))}
            </div>
          </>
        )}

        {reviews.length > 0 && (
          <>
            <h2>Проверка прорабом</h2>
            <div className="list">
              {reviews.map((r) => (
                <div key={r.id} className="row"><span className="pre">{r.comment || "Без комментария"}</span><span className="muted">{fmt(r.created_at)}</span></div>
              ))}
            </div>
          </>
        )}
      </section>
    </main>
  );
}

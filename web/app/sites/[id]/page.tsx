import Link from "next/link";
import { notFound } from "next/navigation";
import { getProfile } from "@/lib/profile";
import { STATUS_LABEL } from "@/lib/status";
import CopyLink from "@/components/CopyLink";
import NewTaskForm from "@/components/NewTaskForm";

type SiteRow = { id: number; name: string; address: string; foreman_id: number; invite_code: string };
type TaskRow = { id: number; title: string; status: string };
type MemberRow = { worker_id: number; users: { name: string } | null };

export default async function SitePage({ params }: { params: { id: string } }) {
  const { supabase, profile } = await getProfile();
  const siteId = Number(params.id);
  if (!Number.isInteger(siteId)) notFound();

  const { data: siteData } = await supabase
    .from("sites")
    .select("id, name, address, foreman_id, invite_code")
    .eq("id", siteId)
    .maybeSingle();
  if (!siteData) notFound();
  const site = siteData as unknown as SiteRow;
  const isForeman = profile.role === "foreman" && site.foreman_id === profile.id;

  const { data: taskData } = await supabase
    .from("tasks")
    .select("id, title, status")
    .eq("site_id", siteId)
    .order("created_at", { ascending: false });
  const tasks = (taskData ?? []) as unknown as TaskRow[];

  const { data: memberData } = await supabase
    .from("site_members")
    .select("worker_id, users(name)")
    .eq("site_id", siteId);
  const members = (memberData ?? []) as unknown as MemberRow[];

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href="/sites">← Назад</Link>
        <h1>{site.name}</h1>
        <p className="muted">{site.address}</p>

        {isForeman && (
          <>
            <h2>Приглашение для рабочих</h2>
            <CopyLink path={`/join/${site.invite_code}`} />
          </>
        )}

        <h2>Рабочие ({members.length})</h2>
        {!members.length && <p className="muted">Пока никто не присоединился.</p>}
        <div className="list">
          {members.map((m) => (
            <div key={m.worker_id} className="row"><b>👷 {m.users?.name ?? "Без имени"}</b></div>
          ))}
        </div>

        <h2>Задачи</h2>
        {!tasks.length && <p className="muted">Задач пока нет.</p>}
        <div className="list">
          {tasks.map((t) => (
            <Link key={t.id} className="row" href={`/tasks/${t.id}`}>
              <b>{t.title}</b>
              <span className="muted">{STATUS_LABEL[t.status] ?? t.status}</span>
            </Link>
          ))}
        </div>

        {isForeman && (
          <>
            <h2>Новая задача</h2>
            <NewTaskForm siteId={siteId} />
          </>
        )}
      </section>
    </main>
  );
}

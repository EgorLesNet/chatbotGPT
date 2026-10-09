import Link from "next/link";
import { notFound } from "next/navigation";
import { getProfile } from "@/lib/profile";
import Chat from "@/components/Chat";
import type { ChatMessage } from "@/lib/chat";

export default async function SiteChatPage({ params }: { params: { id: string } }) {
  const siteId = Number(params.id);
  if (!Number.isInteger(siteId)) notFound();

  const { supabase, profile } = await getProfile();

  const { data: site } = await supabase.from("sites").select("id, name").eq("id", siteId).maybeSingle();
  if (!site) notFound();
  const siteName = (site as unknown as { name: string }).name;

  const { data, error } = await supabase.rpc("get_chat", { p_site: siteId });
  const initial = (data ?? []) as unknown as ChatMessage[];

  const { data: taskData } = await supabase
    .from("tasks")
    .select("id, title")
    .eq("site_id", siteId)
    .order("created_at", { ascending: false });
  const tasks = (taskData ?? []) as unknown as { id: number; title: string }[];

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href={`/sites/${siteId}`}>← К объекту</Link>
        <h1>💬 {siteName}</h1>
        <p className="muted">Чат объекта: прораб и рабочие. Сообщения из Telegram-бота тоже показываются здесь.</p>
        {error ? (
          <p className="notice">Чат недоступен: {error.message}. Выполните SQL-файл supabase_pwa_chat.sql.</p>
        ) : (
          <Chat siteId={siteId} meId={profile.id} initial={initial} tasks={tasks} />
        )}
      </section>
    </main>
  );
}

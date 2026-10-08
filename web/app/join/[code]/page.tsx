import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

export default async function JoinPage({ params }: { params: { code: string } }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const next = `/join/${encodeURIComponent(params.code)}`;
  if (!user) redirect(`/login?next=${encodeURIComponent(next)}`);

  const { data: profile } = await supabase.from("users").select("id").eq("auth_id", user.id).maybeSingle();
  if (!profile) redirect(`/onboarding?next=${encodeURIComponent(next)}`);

  const { data: siteId, error } = await supabase.rpc("join_site", { p_invite: decodeURIComponent(params.code) });
  if (error || !siteId) {
    return (
      <main className="container narrow">
        <section className="card">
          <h1>Не удалось открыть объект</h1>
          <p className="muted">Приглашение недействительно или у вашей роли нет доступа к этому объекту.</p>
          <Link className="button" href="/dashboard">В кабинет</Link>
        </section>
      </main>
    );
  }
  redirect(`/sites/${siteId}`);
}

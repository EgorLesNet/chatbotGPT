import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

export default async function SitesPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: sites } = await supabase.from("sites").select("id, name, address").order("created_at", { ascending: false });
  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href="/dashboard">← Назад</Link>
        <h1>Объекты</h1>
        {!sites?.length && <p className="muted">Пока нет доступных объектов.</p>}
        <div className="list">
          {sites?.map((s) => (
            <Link key={s.id} className="row" href={`/sites/${s.id}`}>
              <b>🏗 {s.name}</b>
              <span className="muted">{s.address}</span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}

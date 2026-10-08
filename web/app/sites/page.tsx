import Link from "next/link";
import { getProfile } from "@/lib/profile";

type SiteRow = { id: number; name: string; address: string };

export default async function SitesPage() {
  const { supabase, profile } = await getProfile();
  const { data } = await supabase
    .from("sites")
    .select("id, name, address")
    .order("created_at", { ascending: false });
  const sites = (data ?? []) as unknown as SiteRow[];

  return (
    <main className="container">
      <section className="card">
        <Link className="link-button" href="/dashboard">← Назад</Link>
        <h1>Объекты</h1>
        {profile.role === "foreman" && (
          <Link className="button" href="/sites/new">+ Создать объект</Link>
        )}
        {!sites.length && (
          <p className="muted">
            {profile.role === "foreman" ? "Объектов пока нет." : "Нет доступных объектов. Откройте ссылку-приглашение от прораба."}
          </p>
        )}
        <div className="list">
          {sites.map((s) => (
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

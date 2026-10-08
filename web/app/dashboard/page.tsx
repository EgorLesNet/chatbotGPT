import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import Link from "next/link";

export default async function DashboardPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase.from("users").select("name, role").eq("auth_id", user.id).maybeSingle();
  return (
    <main className="container">
      <section className="card">
        <p className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</p>
        <h1>{profile ? `Здравствуйте, ${profile.name}` : "Завершите настройку профиля"}</h1>
        <p className="muted">{profile ? `Роль: ${profile.role === "foreman" ? "прораб" : "рабочий"}` : "Профиль ещё не связан с пользователем бота."}</p>
        <div className="grid">
          <Link className="tile" href="/sites">Объекты</Link>
          <Link className="tile" href="/tasks">Задачи</Link>
        </div>
      </section>
    </main>
  );
}

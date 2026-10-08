import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import SignOut from "./sign-out";

export default async function DashboardPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase.from("users").select("name, role").eq("auth_id", user.id).maybeSingle();
  if (!profile) redirect("/onboarding");

  return (
    <main className="container">
      <section className="card">
        <p className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</p>
        <h1>Здравствуйте, {profile.name}</h1>
        <p className="muted">Роль: {profile.role === "foreman" ? "прораб" : "рабочий"}</p>
        <div className="grid">
          <Link className="tile" href="/sites">Объекты</Link>
        </div>
        <SignOut />
      </section>
    </main>
  );
}

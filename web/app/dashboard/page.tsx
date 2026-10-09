import Link from "next/link";
import { getProfile } from "@/lib/profile";
import PasskeySettings from "@/components/PasskeySettings";
import SignOut from "./sign-out";

export default async function DashboardPage() {
  const { profile } = await getProfile();

  return (
    <main className="container">
      <section className="card">
        <p className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</p>
        <h1>Здравствуйте, {profile.name}</h1>
        <p className="muted">Роль: {profile.role === "foreman" ? "прораб" : "рабочий"}</p>
        <div className="grid">
          <Link className="tile" href="/sites">Объекты</Link>
          <Link className="tile" href="/tasks">Задачи</Link>
        </div>
        <PasskeySettings />
        <SignOut />
      </section>
    </main>
  );
}

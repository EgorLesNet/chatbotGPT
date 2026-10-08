import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container">
      <section className="card hero">
        <p className="eyebrow">ПРОРАБ</p>
        <h1>Управляйте объектами и задачами с телефона</h1>
        <p className="muted">Войдите, чтобы открыть свои объекты, задачи и рабочий чат.</p>
        <Link className="button" href="/login">Войти</Link>
      </section>
    </main>
  );
}

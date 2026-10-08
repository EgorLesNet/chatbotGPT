"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { explain } from "@/lib/errors";

export default function NewSitePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const { data, error } = await createClient().rpc("create_site", { p_name: name, p_address: address });
    setBusy(false);
    if (error) return setError(explain(error.message));
    router.push(`/sites/${data}`);
  }

  return (
    <main className="container narrow">
      <section className="card">
        <Link className="link-button" href="/sites">← Назад</Link>
        <h1>Новый объект</h1>
        <form onSubmit={submit} className="form">
          <label>Название<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
          <label>Адрес<input value={address} onChange={(e) => setAddress(e.target.value)} /></label>
          <button className="button" disabled={busy}>{busy ? "Подождите…" : "Создать"}</button>
        </form>
        {error && <p className="notice">{error}</p>}
      </section>
    </main>
  );
}

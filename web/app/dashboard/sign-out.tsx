"use client";

import { createClient } from "@/lib/supabase/client";

export default function SignOut() {
  async function out() {
    await createClient().auth.signOut();
    window.location.assign("/login");
  }
  return <button className="link-button" onClick={out}>Выйти</button>;
}

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export type Profile = { id: number; name: string; role: "foreman" | "worker" };

export async function getProfile() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data } = await supabase
    .from("users")
    .select("id, name, role")
    .eq("auth_id", user.id)
    .maybeSingle();
  if (!data) redirect("/onboarding");

  return { supabase, profile: data as unknown as Profile };
}

"use server";

import { headers } from "next/headers";
import { createClient } from "@/lib/supabase/server";
import { explain } from "@/lib/errors";
import { createYooPayment, verifyAndConfirm } from "@/lib/billing";

const ALLOWED = new Set([
  "add_finance_entry", "delete_finance_entry",
  "add_estimate_item", "delete_estimate_item",
  "enable_client_link", "disable_client_link",
]);

export async function bizRpc(
  fn: string,
  args: Record<string, unknown>,
): Promise<{ data: unknown; error: string | null }> {
  if (!ALLOWED.has(fn)) return { data: null, error: "Недопустимое действие." };

  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { data: null, error: explain("not authenticated") };

  const { data, error } = await supabase.rpc(fn, args);
  if (error) return { data: null, error: explain(error.message) };
  return { data, error: null };
}

export async function startPayment(): Promise<{ url: string | null; error: string | null }> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { url: null, error: explain("not authenticated") };

  const { data: me } = await supabase.from("users").select("id").eq("auth_id", user.id).maybeSingle();
  const userId = (me as unknown as { id: number } | null)?.id;
  if (!userId) return { url: null, error: explain("profile required") };

  const h = headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  const proto = h.get("x-forwarded-proto") ?? "https";
  const origin = process.env.APP_URL ?? `${proto}://${host}`;

  const payment = await createYooPayment(userId, `${origin}/billing`);
  if ("error" in payment) return { url: null, error: payment.error };

  const { error } = await supabase.rpc("register_payment", { p_external_id: payment.id });
  if (error) return { url: null, error: explain(error.message) };
  return { url: payment.url, error: null };
}

export async function checkPayment(): Promise<{ unlocked: boolean; error: string | null }> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { unlocked: false, error: explain("not authenticated") };

  const { data: pending } = await supabase.rpc("my_pending_payment");
  if (!pending) return { unlocked: false, error: null };

  const ok = await verifyAndConfirm(String(pending));
  return { unlocked: ok, error: null };
}

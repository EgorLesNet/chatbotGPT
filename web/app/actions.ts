"use server";

import { createClient } from "@/lib/supabase/server";
import { explain } from "@/lib/errors";

const ALLOWED = new Set([
  "create_site", "update_site", "regenerate_invite", "delete_site", "remove_member",
  "create_task", "update_task", "assign_task", "take_task", "submit_task",
  "review_task", "release_task", "reopen_task", "delete_task",
  "create_pwa_profile", "link_telegram_account", "join_site",
]);

export async function rpcAction(
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

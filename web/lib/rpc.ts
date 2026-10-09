import { createClient } from "@/lib/supabase/client";
import { explain } from "@/lib/errors";

/** Calls a Supabase RPC; returns an error text for the user, or null on success. */
export async function callRpc(fn: string, args: Record<string, unknown>): Promise<string | null> {
  const { error } = await createClient().rpc(fn, args);
  return error ? explain(error.message) : null;
}

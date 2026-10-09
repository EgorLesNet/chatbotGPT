import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    // Passkeys are experimental in supabase-js and need an explicit opt-in.
    { auth: { experimental: { passkey: true } } } as never,
  );
}

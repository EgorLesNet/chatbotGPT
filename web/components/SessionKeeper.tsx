"use client";

import { useEffect } from "react";
import { createClient } from "@/lib/supabase/client";

/** Keeps the Supabase auth cookie fresh from the browser (server components cannot write cookies). */
export default function SessionKeeper() {
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession();

    const { data } = supabase.auth.onAuthStateChange(() => {});
    const refresh = () => {
      if (document.visibilityState === "visible") supabase.auth.getSession();
    };
    document.addEventListener("visibilitychange", refresh);

    return () => {
      data.subscription.unsubscribe();
      document.removeEventListener("visibilitychange", refresh);
    };
  }, []);

  return null;
}

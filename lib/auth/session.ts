import "server-only";
import { connection } from "next/server";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

/** Verified user for server code. Redirects to /login when signed out. Always use this, not the proxy, to guard data. */
export async function requireUser() {
  await connection(); // user-specific data is never prerendered (cacheComponents)
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) redirect("/login");
  return { supabase, user: data.user };
}

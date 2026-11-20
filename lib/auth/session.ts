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

/** Admin-only server code. Non-admins (and signed-out users) get a 404 so the page's existence is not revealed.
 *  The flag is read with the service role because users have no privilege on profiles.is_admin. */
export async function requireAdmin() {
  const { user } = await requireUser();
  const { createAdminClient } = await import("@/lib/supabase/admin");
  const admin = createAdminClient();
  const { data } = await admin.from("profiles").select("is_admin").eq("user_id", user.id).maybeSingle();
  if (!data?.is_admin) {
    const { notFound } = await import("next/navigation");
    notFound();
  }
  return { admin, user };
}

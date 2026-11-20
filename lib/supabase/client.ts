import { createBrowserClient } from "@supabase/ssr";

/** Browser client: publishable key + user session, so RLS applies. */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}

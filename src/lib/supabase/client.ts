import { createBrowserClient } from "@supabase/ssr";

/** Cliente Supabase para componentes de cliente (login, logout). RLS aplica. */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}

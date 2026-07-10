import { createClient } from "@supabase/supabase-js";

/**
 * Cliente con SERVICE-ROLE key. Bypassa RLS. SOLO servidor (ingesta y
 * recálculo de métricas). Nunca importar desde código de cliente.
 */
export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error(
      "Faltan NEXT_PUBLIC_SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY (ver .env.example).",
    );
  }
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

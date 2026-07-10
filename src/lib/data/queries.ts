/**
 * Capa de lectura (server-only). Todo pasa por el cliente con RLS: cada
 * usuario ve solo las campañas de su organización. Si Supabase no está
 * configurado todavía, las funciones devuelven vacío en vez de reventar,
 * para que la UI muestre su estado vacío.
 */
import { createClient } from "../supabase/server";

function isConfigured() {
  return (
    !!process.env.NEXT_PUBLIC_SUPABASE_URL &&
    !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  );
}

async function safe<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  if (!isConfigured()) return fallback;
  try {
    return await fn();
  } catch {
    return fallback;
  }
}

export interface CampaignRow {
  id: string;
  anio_campania: string;
  nombre: string;
  fecha_liberacion: string | null;
  fecha_corte_datos: string | null;
  saldo_asignado: number;
  deudas: number;
  consultoras: number;
  created_at: string;
}

export async function getProfile() {
  return safe(async () => {
    const db = createClient();
    const { data: auth } = await db.auth.getUser();
    if (!auth.user) return null;
    const { data } = await db
      .from("profiles")
      .select("user_id, rol, equipo, nombre, org_id")
      .eq("user_id", auth.user.id)
      .single();
    return data ?? null;
  }, null);
}

export async function getCampaigns(): Promise<CampaignRow[]> {
  return safe(async () => {
    const db = createClient();
    const { data } = await db
      .from("campaigns")
      .select("*")
      .order("anio_campania", { ascending: false });
    return (data as CampaignRow[]) ?? [];
  }, []);
}

/** Resuelve la campaña activa: el param `c` o la más reciente. */
export async function resolveCampaign(
  campaigns: CampaignRow[],
  c?: string,
): Promise<CampaignRow | null> {
  if (campaigns.length === 0) return null;
  if (c) return campaigns.find((x) => x.id === c) ?? campaigns[0];
  return campaigns[0];
}

async function tableFor(campaignId: string, table: string, orderBy?: string) {
  return safe(async () => {
    const db = createClient();
    let q = db.from(table).select("*").eq("campaign_id", campaignId);
    if (orderBy) q = q.order(orderBy, { ascending: true });
    const { data } = await q;
    return data ?? [];
  }, [] as any[]);
}

export const getResumen = (id: string) =>
  safe(async () => {
    const db = createClient();
    const { data } = await db.from("metrics_resumen").select("*").eq("campaign_id", id).single();
    return data;
  }, null as any);

export const getCanal = (id: string) => tableFor(id, "metrics_canal");

/** metrics_agente + nombre_display del catálogo de agentes. */
export const getAgentes = (id: string) =>
  safe(async () => {
    const db = createClient();
    const { data } = await db
      .from("metrics_agente")
      .select("*, agentes:agente_id(nombre_display), mentor:mentor_sugerido(nombre_display)")
      .eq("campaign_id", id);
    return (data ?? []).map((a: any) => ({
      ...a,
      nombre: a.agentes?.nombre_display ?? null,
      mentor_nombre: a.mentor?.nombre_display ?? null,
    }));
  }, [] as any[]);
export const getTemporalidad = (id: string) => tableFor(id, "metrics_temporalidad");
export const getDiaria = (id: string) => tableFor(id, "metrics_diaria", "fecha");
export const getSecuencias = (id: string) => tableFor(id, "metrics_secuencia");
export const getQualityFlags = (id: string) => tableFor(id, "quality_flags");
export const getAgentesCatalogo = (id: string) => tableFor(id, "agentes");

export const getCostoMarcador = (id: string) =>
  safe(async () => {
    const db = createClient();
    const { data } = await db.from("costo_marcador").select("*").eq("campaign_id", id).single();
    return data;
  }, null as any);

/**
 * Historia de cada gestor a través de campañas (§6 — evolución campaña a
 * campaña). Empareja por nombre_norm entre campañas de la organización.
 */
export async function getHistoriaGestores() {
  return safe(async () => {
    const db = createClient();
    const { data } = await db
      .from("metrics_agente")
      .select(
        "tasa_contacto, pct_cumplimiento, clasificacion, recuperado_atribuido, " +
          "agentes:agente_id(nombre_norm, nombre_display), " +
          "campaigns:campaign_id(anio_campania)",
      );
    type HistPunto = { anio: string; contacto: number; cumplimiento: number; clasificacion: string };
    type HistEntry = { display: string; puntos: HistPunto[] };
    const hist = new Map<string, HistEntry>();
    for (const r of (data ?? []) as any[]) {
      const norm = r.agentes?.nombre_norm;
      if (!norm) continue;
      const entry: HistEntry = hist.get(norm) ?? { display: r.agentes?.nombre_display ?? norm, puntos: [] };
      entry.puntos.push({
        anio: r.campaigns?.anio_campania ?? "?",
        contacto: Number(r.tasa_contacto),
        cumplimiento: Number(r.pct_cumplimiento),
        clasificacion: r.clasificacion,
      });
      hist.set(norm, entry);
    }
    for (const e of hist.values())
      e.puntos.sort((a, b) => a.anio.localeCompare(b.anio));
    return Object.fromEntries(hist);
  }, {} as Record<string, { display: string; puntos: { anio: string; contacto: number; cumplimiento: number; clasificacion: string }[] }>);
}

/** Todas las campañas con su resumen, para la vista comparativa. */
export async function getComparativa() {
  return safe(async () => {
    const db = createClient();
    const { data: camps } = await db
      .from("campaigns")
      .select("*")
      .order("anio_campania", { ascending: true });
    const { data: resumenes } = await db.from("metrics_resumen").select("*");
    const { data: canales } = await db.from("metrics_canal").select("*");
    const { data: agentes } = await db
      .from("metrics_agente")
      .select("campaign_id, pdp, pdp_cumplidas");
    // Cumplimiento promedio ponderado por campaña.
    const cumplByCampaign = new Map<string, { pdp: number; cumpl: number }>();
    for (const a of (agentes ?? []) as any[]) {
      const cur = cumplByCampaign.get(a.campaign_id) ?? { pdp: 0, cumpl: 0 };
      cur.pdp += Number(a.pdp);
      cur.cumpl += Number(a.pdp_cumplidas);
      cumplByCampaign.set(a.campaign_id, cur);
    }
    const cumplimiento = Object.fromEntries(
      [...cumplByCampaign.entries()].map(([id, v]) => [id, v.pdp > 0 ? v.cumpl / v.pdp : 0]),
    );
    return {
      campaigns: (camps as CampaignRow[]) ?? [],
      resumenes: resumenes ?? [],
      canales: canales ?? [],
      cumplimiento,
    };
  }, { campaigns: [] as CampaignRow[], resumenes: [] as any[], canales: [] as any[], cumplimiento: {} as Record<string, number> });
}

/** Resumen de la campaña anterior (para deltas), por orden de anio_campania. */
export async function getResumenPrevio(
  campaigns: CampaignRow[],
  actual: CampaignRow,
) {
  const ordenadas = [...campaigns].sort((a, b) =>
    a.anio_campania.localeCompare(b.anio_campania),
  );
  const idx = ordenadas.findIndex((c) => c.id === actual.id);
  if (idx <= 0) return null;
  const prev = ordenadas[idx - 1];
  return getResumen(prev.id);
}

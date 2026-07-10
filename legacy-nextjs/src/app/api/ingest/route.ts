import { NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { buildIngestFromBuffers } from "@/lib/ingest/pipeline";
import { persistCampaign } from "@/lib/metrics/persist";

export const runtime = "nodejs";
export const maxDuration = 60;

const CAMPOS = ["cartera", "pagos", "gestiones", "vicidial", "ivr", "sms"] as const;

/**
 * Ingesta de los 6 .xlsx (§8 pág. 10). Solo admin. Dos modos:
 *   commit=false → perfila y devuelve tasas de cruce + quality_flags (preview).
 *   commit=true  → persiste idempotente + guarda crudos en Storage + auditoría.
 */
export async function POST(request: Request) {
  // 1) Auth + RBAC.
  const supabase = createClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) return NextResponse.json({ error: "No autenticado" }, { status: 401 });
  const { data: profile } = await supabase
    .from("profiles")
    .select("rol, org_id")
    .eq("user_id", auth.user.id)
    .single();
  if (!profile || profile.rol !== "admin")
    return NextResponse.json({ error: "Solo admin puede cargar campañas" }, { status: 403 });

  // 2) Leer formData.
  const form = await request.formData();
  const anio = String(form.get("anio") ?? "").trim();
  const nombre = String(form.get("nombre") ?? "").trim() || `Campaña ${anio}`;
  const commit = String(form.get("commit") ?? "false") === "true";
  if (!anio) return NextResponse.json({ error: "Falta AnioCampaniaSaldo" }, { status: 400 });

  const buffers: Record<string, Buffer> = {};
  const hashes: Record<string, { name: string; sha256: string; size: number }> = {};
  for (const campo of CAMPOS) {
    const file = form.get(campo);
    if (!(file instanceof File))
      return NextResponse.json({ error: `Falta el archivo: ${campo}` }, { status: 400 });
    const buf = Buffer.from(await file.arrayBuffer());
    buffers[campo] = buf;
    hashes[campo] = {
      name: file.name,
      sha256: createHash("sha256").update(buf).digest("hex"),
      size: buf.length,
    };
  }

  // 3) Construir dataset normalizado + perfilado.
  let ingest;
  try {
    ingest = buildIngestFromBuffers(buffers as any);
  } catch (e: any) {
    return NextResponse.json({ error: `Error al parsear: ${e.message}` }, { status: 422 });
  }

  const preview = {
    profile: ingest.profile,
    flags: ingest.flags,
    header: ingest.header,
  };

  if (!commit) return NextResponse.json({ ok: true, commit: false, ...preview });

  // 4) Persistir (service-role, bypassa RLS; corre solo aquí en el servidor).
  const admin = createAdminClient();
  const { campaignId } = await persistCampaign(admin, {
    orgId: profile.org_id,
    anioCampania: anio,
    nombre,
    cargadoPor: auth.user.id,
    ingest,
  });

  // 5) Guardar crudos en Storage (auditoría) + registrar hashes.
  const bucket = process.env.SUPABASE_STORAGE_BUCKET ?? "raw-campaigns";
  for (const campo of CAMPOS) {
    const h = hashes[campo];
    const path = `${profile.org_id}/${anio}/${campo}-${h.sha256.slice(0, 12)}.xlsx`;
    try {
      await admin.storage.from(bucket).upload(path, buffers[campo], {
        contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        upsert: true,
      });
      await admin.from("ingest_audit").insert({
        campaign_id: campaignId,
        org_id: profile.org_id,
        user_id: auth.user.id,
        archivo: h.name,
        sha256: h.sha256,
        storage_path: path,
        filas: null,
      });
    } catch {
      // Si el bucket no existe todavía, no bloquea la ingesta; se reporta en flags.
      ingest.flags.push({
        tipo: "storage_no_disponible",
        detalle: `No se pudo subir ${campo} a Storage (bucket '${bucket}'). Crea el bucket para habilitar auditoría de crudos.`,
        severidad: "warn",
      });
    }
  }

  return NextResponse.json({ ok: true, commit: true, campaignId, ...preview });
}

/**
 * Persistencia idempotente de una campaña (§5): recargar reemplaza, no duplica.
 * Corre SOLO en el servidor con el service-role client. Borra las filas de la
 * campaña y reinserta (delete+insert por campaign_id) dentro del mismo flujo.
 */
import type { SupabaseClient } from "@supabase/supabase-js";
import { IngestResult } from "../ingest/pipeline";
import { computeMetrics } from "./compute";

export interface PersistInput {
  orgId: string;
  anioCampania: string;
  nombre: string;
  cargadoPor: string | null;
  ingest: IngestResult;
}

const chunk = <T>(arr: T[], n = 1000): T[][] => {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
  return out;
};

export async function persistCampaign(
  db: SupabaseClient,
  input: PersistInput,
): Promise<{ campaignId: string }> {
  const { ingest, orgId } = input;
  const metrics = computeMetrics(ingest);

  // 1) Upsert cabecera de campaña.
  const { data: camp, error: e0 } = await db
    .from("campaigns")
    .upsert(
      {
        org_id: orgId,
        anio_campania: input.anioCampania,
        nombre: input.nombre,
        fecha_liberacion: ingest.profile.fechaLiberacion,
        fecha_corte_datos: ingest.profile.fechaCorteDatos,
        saldo_asignado: ingest.header.saldoAsignado,
        deudas: ingest.header.deudas,
        consultoras: ingest.header.consultoras,
        cargado_por: input.cargadoPor,
      },
      { onConflict: "org_id,anio_campania" },
    )
    .select("id")
    .single();
  if (e0 || !camp) throw e0 ?? new Error("No se pudo crear la campaña");
  const campaignId = camp.id as string;

  // 2) Limpieza idempotente de las tablas hijas de esta campaña.
  const tablas = [
    "cartera", "pagos", "toques", "gestiones", "agentes", "costo_marcador",
    "metrics_canal", "metrics_agente", "metrics_temporalidad", "metrics_diaria",
    "metrics_secuencia", "metrics_resumen", "quality_flags",
  ];
  for (const t of tablas) {
    const { error } = await db.from(t).delete().eq("campaign_id", campaignId);
    if (error) throw error;
  }

  // 3) Insertar agentes y mapear norm → id.
  const agentesRows = ingest.agentes.map((a) => ({
    campaign_id: campaignId,
    nombre_norm: a.nombreNorm,
    nombre_display: a.nombreDisplay,
    fuentes: a.fuentes,
  }));
  const agenteIdByNorm = new Map<string, string>();
  if (agentesRows.length) {
    const { data, error } = await db.from("agentes").insert(agentesRows).select("id,nombre_norm");
    if (error) throw error;
    for (const r of data ?? []) agenteIdByNorm.set(r.nombre_norm as string, r.id as string);
  }

  // 4) Cartera / Pagos / Toques / Gestiones.
  for (const c of chunk(ingest.cartera.map((x) => ({
    campaign_id: campaignId, dama_deuda: x.damaDeuda, num_dama: x.numDama,
    saldo_cobro: x.saldoCobro, zona: x.zona, ruta: x.ruta, fecha_entrega: x.fechaEntrega,
  })))) {
    const { error } = await db.from("cartera").insert(c);
    if (error) throw error;
  }
  for (const c of chunk(ingest.pagos.map((x) => ({
    campaign_id: campaignId, dama_deuda: x.damaDeuda, num_dama: x.numDama,
    id_cobrador: x.idCobrador, fecha_pago: x.fechaPago, saldo_remanente: x.saldoRemanente,
    estado_proceso: x.estadoProceso, recuperado: x.recuperado,
  })))) {
    const { error } = await db.from("pagos").insert(c);
    if (error) throw error;
  }
  for (const c of chunk(ingest.toques.map((x) => ({
    campaign_id: campaignId, num_dama: x.numDama, canal: x.canal, dia: x.dia,
    efectivo: x.efectivo, meta: x.meta,
  })))) {
    const { error } = await db.from("toques").insert(c);
    if (error) throw error;
  }
  for (const c of chunk(ingest.gestiones.map((x) => ({
    campaign_id: campaignId,
    agente_id: x.agenteNorm ? agenteIdByNorm.get(x.agenteNorm) ?? null : null,
    num_dama: x.numDama, fecha: x.fecha, tipo_gestion: x.tipoGestion,
    tipificacion: x.tipificacion, promesa_fecha: x.promesaFecha,
    monto_prometido: x.montoPrometido, temp: x.temp,
  })))) {
    const { error } = await db.from("gestiones").insert(c);
    if (error) throw error;
  }

  // 5) Costo del marcador (C3).
  await db.from("costo_marcador").insert({
    campaign_id: campaignId,
    llamadas: ingest.profile.costoMarcador.llamadas,
    minutos: ingest.profile.costoMarcador.minutos,
    contactos_efectivos: ingest.profile.costoMarcador.contactosEfectivos,
  });

  // 6) Métricas derivadas.
  if (metrics.canal.length)
    await db.from("metrics_canal").insert(metrics.canal.map((m) => ({
      campaign_id: campaignId, canal: m.canal, monto_ultimo_toque: m.montoUltimoToque,
      pagos: m.pagos, consultoras: m.consultoras, pct: m.pct,
      eficiencia_por_toque: m.eficienciaPorToque, influencia_monto: m.influenciaMonto,
      influencia_pct: m.influenciaPct,
    })));

  if (metrics.agentes.length)
    await db.from("metrics_agente").insert(metrics.agentes.map((a) => ({
      campaign_id: campaignId, agente_id: agenteIdByNorm.get(a.agenteId)!,
      gestiones: a.gestiones, contactos_efectivos: a.contactosEfectivos,
      tasa_contacto: a.tasaContacto, pdp: a.pdp, pdp_cumplidas: a.pdpCumplidas,
      pct_cumplimiento: a.pctCumplimiento, recuperado_atribuido: a.recuperadoAtribuido,
      pagadoras: 0, clasificacion: a.clasificacion,
      percentil_contacto: a.percentilContacto, percentil_cumplimiento: a.percentilCumplimiento,
      mentor_sugerido: a.mentorSugerido ? agenteIdByNorm.get(a.mentorSugerido) ?? null : null,
    })));

  if (metrics.temporalidad.length)
    await db.from("metrics_temporalidad").insert(metrics.temporalidad.map((t) => ({
      campaign_id: campaignId, temp: t.temp, saldo: t.saldo, recuperado: t.recuperado,
      tasa: t.tasa, deudas: t.deudas,
    })));

  if (metrics.diaria.length)
    await db.from("metrics_diaria").insert(metrics.diaria.map((d) => ({
      campaign_id: campaignId, fecha: d.fecha, recuperado: d.recuperado, pagos: d.pagos,
      sms_enviados: d.smsEnviados, es_blast: d.esBlast, fuera_ventana: d.fueraVentana,
    })));

  if (metrics.secuencias.length)
    await db.from("metrics_secuencia").insert(metrics.secuencias.map((s) => ({
      campaign_id: campaignId, cadena: s.cadena, pagos: s.pagos, recuperado: s.recuperado,
    })));

  await db.from("metrics_resumen").insert({
    campaign_id: campaignId,
    recuperado: metrics.resumen.recuperado,
    saldo_asignado: metrics.resumen.saldoAsignado,
    pct_recuperado: metrics.resumen.pctRecuperado,
    deudas_liquidadas: metrics.resumen.deudasLiquidadas,
    saldo_pendiente: metrics.resumen.saldoPendiente,
    pct_pagos_sin_contacto: metrics.resumen.pctPagosSinContacto,
    pct_espontaneo: metrics.resumen.pctEspontaneo,
    pct_fuera_ventana: metrics.resumen.pctFueraVentana,
    pct_cartera_no_contactada: metrics.resumen.pctCarteraNoContactada,
  });

  // 7) Quality flags.
  if (ingest.flags.length)
    await db.from("quality_flags").insert(ingest.flags.map((f) => ({
      campaign_id: campaignId, tipo: f.tipo, detalle: f.detalle, severidad: f.severidad,
    })));

  return { campaignId };
}

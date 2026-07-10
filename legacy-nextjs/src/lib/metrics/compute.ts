/**
 * Cálculo de métricas derivadas (§5 tablas materializadas) a partir del
 * dataset normalizado. Usa el motor de atribución y la clasificación de
 * gestores; no escribe una sola cifra que no salga de aquí (§11).
 */
import {
  attributeAll,
  resumenPrimario,
  influenceModel,
  sesgoTemporal,
  eficienciaPorToque,
  difDias,
} from "../attribution/engine";
import { Payment, Touch } from "../attribution/types";
import { clasificarEquipo, GestorInput } from "../classify/gestores";
import { IngestResult } from "../ingest/pipeline";

export interface ComputedMetrics {
  canal: {
    canal: string;
    montoUltimoToque: number;
    pagos: number;
    consultoras: number;
    pct: number;
    eficienciaPorToque: number;
    influenciaMonto: number;
    influenciaPct: number;
  }[];
  agentes: ReturnType<typeof clasificarEquipo>;
  temporalidad: { temp: string; saldo: number; recuperado: number; tasa: number; deudas: number }[];
  diaria: { fecha: string; recuperado: number; pagos: number; smsEnviados: number; esBlast: boolean; fueraVentana: boolean }[];
  secuencias: { cadena: string; pagos: number; recuperado: number }[];
  resumen: {
    recuperado: number;
    saldoAsignado: number;
    pctRecuperado: number;
    deudasLiquidadas: number;
    saldoPendiente: number;
    pctPagosSinContacto: number;
    pctEspontaneo: number;
    pctFueraVentana: number;
    pctCarteraNoContactada: number;
  };
}

export function computeMetrics(ing: IngestResult): ComputedMetrics {
  const fechaCorte = ing.profile.fechaCorteDatos;

  // ── Entradas del motor ──
  const payments: Payment[] = ing.pagos
    .filter((p) => p.fechaPago && p.recuperado > 0)
    .map((p) => ({
      damaDeuda: p.damaDeuda,
      numDama: p.numDama,
      fechaPago: p.fechaPago!,
      recuperado: p.recuperado,
    }));

  const touches: Touch[] = ing.toques.map((t) => ({
    numDama: t.numDama,
    canal: t.canal,
    dia: t.dia,
    efectivo: t.efectivo,
    meta: t.meta,
  }));

  // ── Modelo primario + secundario + sesgo ──
  const atribs = attributeAll(payments, touches, fechaCorte);
  const primario = resumenPrimario(atribs);
  const { canales: influencia } = influenceModel(payments, touches);
  const ef = eficienciaPorToque(atribs, touches);
  const sesgo = sesgoTemporal(payments, fechaCorte);

  const totalRecuperado = payments.reduce((s, p) => s + p.recuperado, 0);
  const influByCanal = new Map(influencia.map((i) => [i.canal, i]));

  const canal: ComputedMetrics["canal"] = ["Llamada", "IVR", "SMS", "Espontaneo"].map(
    (c) => {
      const p = primario.find((x) => x.canal === c);
      const inf = influByCanal.get(c as "Llamada" | "IVR" | "SMS");
      return {
        canal: c,
        montoUltimoToque: p?.monto ?? 0,
        pagos: p?.pagos ?? 0,
        consultoras: p?.consultoras ?? 0,
        pct: p?.pct ?? 0,
        eficienciaPorToque: c === "Espontaneo" ? 0 : ef[c as "Llamada" | "IVR" | "SMS"],
        influenciaMonto: inf?.monto ?? 0,
        influenciaPct: inf?.pct ?? 0,
      };
    },
  );

  // ── Gestores ──
  const agentes = computeAgentes(ing, atribs);

  // ── Temporalidad ──
  const temporalidad = computeTemporalidad(ing);

  // ── Serie diaria + blasts ──
  const diaria = computeDiaria(ing, atribs, fechaCorte);

  // ── Secuencias top ──
  const secuencias = computeSecuencias(payments, touches);

  // ── Resumen ejecutivo ──
  const espontaneo = primario.find((x) => x.canal === "Espontaneo");
  const deudasLiquidadas = ing.pagos.filter((p) => p.saldoRemanente <= 0).length;
  const damasContactadas = new Set(
    touches.filter((t) => t.efectivo).map((t) => t.numDama),
  );
  const damasCartera = new Set(ing.cartera.map((c) => c.numDama));
  let noContactadas = 0;
  for (const d of damasCartera) if (!damasContactadas.has(d)) noContactadas++;

  const resumen = {
    recuperado: totalRecuperado,
    saldoAsignado: ing.header.saldoAsignado,
    pctRecuperado: ing.header.saldoAsignado > 0 ? totalRecuperado / ing.header.saldoAsignado : 0,
    deudasLiquidadas,
    saldoPendiente: ing.header.saldoAsignado - totalRecuperado,
    pctPagosSinContacto: totalRecuperado > 0 ? (espontaneo?.monto ?? 0) / totalRecuperado : 0,
    pctEspontaneo: espontaneo?.pct ?? 0,
    pctFueraVentana: sesgo.pctFueraDeVentana,
    pctCarteraNoContactada: damasCartera.size > 0 ? noContactadas / damasCartera.size : 0,
  };

  return { canal, agentes, temporalidad, diaria, secuencias, resumen };
}

// ── Gestores ───────────────────────────────────────────────────────────────
function computeAgentes(ing: IngestResult, atribs: ReturnType<typeof attributeAll>) {
  // Recuperado atribuido por agente: pagos ganados por Llamada, agente del toque.
  const recByAgente = new Map<string, number>();
  const pagadorasByAgente = new Map<string, Set<number>>();
  for (const a of atribs) {
    if (a.canal !== "Llamada" || !a.touch) continue;
    const agente = (a.touch.meta?.agente as string) ?? null;
    if (!agente) continue;
    recByAgente.set(agente, (recByAgente.get(agente) ?? 0) + a.payment.recuperado);
    const set = pagadorasByAgente.get(agente) ?? new Set<number>();
    set.add(a.payment.numDama);
    pagadorasByAgente.set(agente, set);
  }

  // Fecha de pago por consultora, para evaluar cumplimiento de PDP.
  const pagoByDama = new Map<number, string>();
  for (const p of ing.pagos) {
    if (p.fechaPago && p.recuperado > 0) pagoByDama.set(p.numDama, p.fechaPago);
  }

  const acc = new Map<
    string,
    { gestiones: number; contactos: number; pdp: number; pdpCumplidas: number }
  >();
  for (const g of ing.gestiones) {
    if (!g.agenteNorm) continue;
    const cur = acc.get(g.agenteNorm) ?? { gestiones: 0, contactos: 0, pdp: 0, pdpCumplidas: 0 };
    cur.gestiones += 1;
    if (esContacto(g.tipoGestion)) cur.contactos += 1;
    if (g.promesaFecha) {
      cur.pdp += 1;
      const pago = pagoByDama.get(g.numDama);
      // Cumplida = pagó dentro de la fecha prometida + 3 días (§6).
      if (pago && difDias(pago, g.promesaFecha) <= 3 && difDias(pago, g.promesaFecha) >= -365) {
        cur.pdpCumplidas += 1;
      }
    }
    acc.set(g.agenteNorm, cur);
  }

  const inputs: GestorInput[] = [...acc.entries()].map(([agente, v]) => ({
    agenteId: agente,
    nombre: ing.agentes.find((a) => a.nombreNorm === agente)?.nombreDisplay ?? agente,
    gestiones: v.gestiones,
    contactosEfectivos: v.contactos,
    pdp: v.pdp,
    pdpCumplidas: v.pdpCumplidas,
    recuperadoAtribuido: recByAgente.get(agente) ?? 0,
  }));

  return clasificarEquipo(inputs);
}

// ── Temporalidad ─────────────────────────────────────────────────────────
function computeTemporalidad(ing: IngestResult) {
  // temp por consultora (última gestión conocida).
  const tempByDama = new Map<number, string>();
  for (const g of ing.gestiones) {
    if (g.temp) tempByDama.set(g.numDama, g.temp);
  }
  const acc = new Map<string, { saldo: number; recuperado: number; deudas: number }>();
  const recByDama = new Map<number, number>();
  for (const p of ing.pagos) recByDama.set(p.numDama, (recByDama.get(p.numDama) ?? 0) + p.recuperado);

  for (const c of ing.cartera) {
    const temp = tempByDama.get(c.numDama) ?? "Sin tramo";
    const cur = acc.get(temp) ?? { saldo: 0, recuperado: 0, deudas: 0 };
    cur.saldo += c.saldoCobro;
    cur.recuperado += recByDama.get(c.numDama) ?? 0;
    cur.deudas += 1;
    acc.set(temp, cur);
  }

  return [...acc.entries()]
    .map(([temp, v]) => ({
      temp,
      saldo: v.saldo,
      recuperado: v.recuperado,
      tasa: v.saldo > 0 ? v.recuperado / v.saldo : 0,
      deudas: v.deudas,
    }))
    .sort((a, b) => b.saldo - a.saldo);
}

// ── Serie diaria + detección de blast ──────────────────────────────────────
function computeDiaria(
  ing: IngestResult,
  atribs: ReturnType<typeof attributeAll>,
  fechaCorte: string | null,
) {
  const acc = new Map<string, { recuperado: number; pagos: number; sms: number }>();
  for (const p of ing.pagos) {
    if (!p.fechaPago) continue;
    const cur = acc.get(p.fechaPago) ?? { recuperado: 0, pagos: 0, sms: 0 };
    cur.recuperado += p.recuperado;
    cur.pagos += 1;
    acc.set(p.fechaPago, cur);
  }
  for (const t of ing.toques) {
    if (t.canal !== "SMS") continue;
    const cur = acc.get(t.dia) ?? { recuperado: 0, pagos: 0, sms: 0 };
    cur.sms += 1;
    acc.set(t.dia, cur);
  }

  const dias = [...acc.entries()].map(([fecha, v]) => ({ fecha, ...v }));
  const smsVals = dias.map((d) => d.sms).filter((n) => n > 0);
  const media = smsVals.length ? smsVals.reduce((s, n) => s + n, 0) / smsVals.length : 0;

  return dias
    .map((d) => ({
      fecha: d.fecha,
      recuperado: d.recuperado,
      pagos: d.pagos,
      smsEnviados: d.sms,
      // Blast = pico de SMS muy por encima de la media del período.
      esBlast: media > 0 && d.sms > media * 2.5,
      fueraVentana: fechaCorte !== null && d.fecha > fechaCorte,
    }))
    .sort((a, b) => a.fecha.localeCompare(b.fecha));
}

// ── Secuencias (cadenas de canal previas al pago) ───────────────────────────
function computeSecuencias(payments: Payment[], touches: Touch[]) {
  const efPorDama = new Map<number, Touch[]>();
  for (const t of touches) {
    if (!t.efectivo) continue;
    const arr = efPorDama.get(t.numDama) ?? [];
    arr.push(t);
    efPorDama.set(t.numDama, arr);
  }

  const acc = new Map<string, { pagos: number; recuperado: number }>();
  for (const p of payments) {
    const arr = (efPorDama.get(p.numDama) ?? [])
      .filter((t) => difDias(p.fechaPago, t.dia) >= 0 && difDias(p.fechaPago, t.dia) <= 14)
      .sort((a, b) => a.dia.localeCompare(b.dia));
    if (arr.length === 0) continue;
    // Colapsa repeticiones consecutivas del mismo canal.
    const cadena: string[] = [];
    for (const t of arr) if (cadena[cadena.length - 1] !== t.canal) cadena.push(t.canal);
    const key = cadena.join("→");
    const cur = acc.get(key) ?? { pagos: 0, recuperado: 0 };
    cur.pagos += 1;
    cur.recuperado += p.recuperado;
    acc.set(key, cur);
  }

  return [...acc.entries()]
    .map(([cadena, v]) => ({ cadena, ...v }))
    .sort((a, b) => b.pagos - a.pagos)
    .slice(0, 8);
}

function esContacto(tipo: string | null): boolean {
  return (tipo ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim() === "contacto";
}

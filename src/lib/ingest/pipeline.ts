/**
 * Orquesta la ingesta de los 6 archivos → dataset normalizado + perfilado.
 *
 * Aplica las reglas estructurales de §4 en el punto de construcción:
 *   C1 · marca `efectivo` en cada toque con el predicado de su fuente.
 *   C2 · gestiones + vicidial = un solo canal; los toques de Llamada salen del
 *        CRM (que trae el resultado/PROMESA); Vicidial solo aporta el roster de
 *        agentes y el costo del marcador. NO se emiten toques Llamada dobles.
 *   C3 · el marcador automático se contabiliza como costo, jamás como toque.
 *
 * No persiste nada: devuelve estructuras listas para `persist.ts`. Así el
 * perfilado (tasas de cruce, flags) se puede imprimir y revisar antes de
 * confirmar la campaña (§11).
 */
import { isAutoDialer, normalizeName } from "../attribution/normalize";
import {
  gestionEsEfectiva,
  ivrEsEfectivo,
  smsEsEfectivo,
} from "../attribution/predicates";
import {
  parseCartera,
  parsePagos,
  parseGestiones,
  parseVicidial,
  parseIvr,
  parseSms,
  readSheet,
} from "./parse";
import { QualityFlag, RawRow } from "./types";

export interface RawFiles {
  cartera: RawRow[];
  pagos: RawRow[];
  gestiones: RawRow[];
  vicidial: RawRow[];
  ivr: RawRow[];
  sms: RawRow[];
}

/** Toque unificado listo para persistir/atribuir. */
export interface ToqueOut {
  numDama: number;
  canal: "Llamada" | "IVR" | "SMS";
  dia: string;
  efectivo: boolean;
  meta: Record<string, unknown>;
}

/** Agente unificado CRM ↔ Vicidial. */
export interface AgenteOut {
  nombreNorm: string;
  nombreDisplay: string;
  fuentes: string[]; // {crm, vicidial}
}

export interface GestionOut {
  numDama: number;
  agenteNorm: string | null;
  fecha: string | null;
  tipoGestion: string | null;
  tipificacion: string | null;
  promesaFecha: string | null;
  montoPrometido: number | null;
  temp: string | null;
}

export interface CarteraOut {
  damaDeuda: string;
  numDama: number;
  saldoCobro: number;
  zona: string | null;
  ruta: string | null;
  fechaEntrega: string | null;
}

export interface PagoOut {
  damaDeuda: string;
  numDama: number;
  idCobrador: string | null;
  fechaPago: string | null;
  saldoRemanente: number;
  estadoProceso: string | null;
  recuperado: number;
}

export interface Profile {
  filas: Record<string, number>;
  cruces: {
    pagosEnCartera: number; // % pagos cuyo dama_deuda cruza cartera
    gestionesEnCartera: number; // % gestiones cuyo num_dama está en cartera
    ivrEnCartera: number;
    smsEnCartera: number;
  };
  fechaCorteDatos: string | null;
  fechaLiberacion: string | null;
  fechaMaxPago: string | null;
  costoMarcador: { llamadas: number; minutos: number; contactosEfectivos: number };
  agentesSoloCRM: string[];
  agentesSoloVicidial: string[];
}

export interface IngestResult {
  cartera: CarteraOut[];
  pagos: PagoOut[];
  toques: ToqueOut[];
  agentes: AgenteOut[];
  gestiones: GestionOut[];
  profile: Profile;
  flags: QualityFlag[];
  header: {
    saldoAsignado: number;
    deudas: number;
    consultoras: number;
  };
}

const pct = (num: number, den: number) => (den > 0 ? num / den : 0);
const maxISO = (a: string | null, b: string | null) =>
  !a ? b : !b ? a : a > b ? a : b;
const minISO = (a: string | null, b: string | null) =>
  !a ? b : !b ? a : a < b ? a : b;

/** Construye el dataset normalizado a partir de filas crudas ya leídas. */
export function buildIngest(files: RawFiles): IngestResult {
  const flags: QualityFlag[] = [];

  // 1) Cartera (dedup) → llave universal.
  const carteraP = parseCartera(files.cartera);
  flags.push(...carteraP.flags);
  const cartera = carteraP.data;
  const carteraKeys = new Set(cartera.map((c) => c.damaDeuda));
  const carteraDamas = new Set(cartera.map((c) => c.numDama));
  const saldoByKey = new Map(cartera.map((c) => [c.damaDeuda, c.saldoCobro]));

  // 2) Pagos filtrados a cartera + recuperado.
  const pagosP = parsePagos(files.pagos, carteraKeys);
  flags.push(...pagosP.flags);
  const pagos: PagoOut[] = pagosP.data.map((p) => {
    const saldoCobro = saldoByKey.get(p.damaDeuda) ?? 0;
    const recuperado = Math.max(0, saldoCobro - p.saldoRemanente);
    return { ...p, recuperado };
  });

  // 3) Gestiones (CRM).
  const gestionesP = parseGestiones(files.gestiones);
  flags.push(...gestionesP.flags);
  const gestiones: GestionOut[] = gestionesP.data.map((g) => ({
    numDama: g.numDama,
    agenteNorm: g.agenteNombre ? normalizeName(g.agenteNombre) : null,
    fecha: g.fecha,
    tipoGestion: g.tipoGestion,
    tipificacion: g.tipificacion,
    promesaFecha: g.promesaFecha,
    montoPrometido: g.montoPrometido,
    temp: g.temp,
  }));

  // 4) Vicidial → roster de agentes + costo del marcador (C3). No emite toques.
  const vicidialP = parseVicidial(files.vicidial);
  const agentesCRM = new Map<string, string>(); // norm → display
  for (const g of gestionesP.data) {
    if (g.agenteNombre) agentesCRM.set(normalizeName(g.agenteNombre), g.agenteNombre);
  }
  const agentesVici = new Map<string, string>();
  const costo = { llamadas: 0, minutos: 0, contactosEfectivos: 0 };
  for (const v of vicidialP.data) {
    if (isAutoDialer(v.fullName)) {
      // C3: costo de telefonía sin retorno.
      costo.llamadas += 1;
      costo.minutos += v.lengthSec / 60;
      // Un marcador que conecta con agente NO es autodialer; aquí siempre 0.
      continue;
    }
    if (v.fullName) agentesVici.set(normalizeName(v.fullName), v.fullName);
  }

  // C2: unir rosters por nombre normalizado; loguear divergencias.
  const agentes: AgenteOut[] = [];
  const todosNombres = new Set([...agentesCRM.keys(), ...agentesVici.keys()]);
  const soloCRM: string[] = [];
  const soloVici: string[] = [];
  for (const norm of todosNombres) {
    if (!norm) continue;
    const enCRM = agentesCRM.has(norm);
    const enVici = agentesVici.has(norm);
    const fuentes: string[] = [];
    if (enCRM) fuentes.push("crm");
    if (enVici) fuentes.push("vicidial");
    if (enCRM && !enVici) soloCRM.push(agentesCRM.get(norm)!);
    if (enVici && !enCRM) soloVici.push(agentesVici.get(norm)!);
    agentes.push({
      nombreNorm: norm,
      nombreDisplay: agentesCRM.get(norm) ?? agentesVici.get(norm)!,
      fuentes,
    });
  }
  if (soloCRM.length || soloVici.length) {
    flags.push({
      tipo: "roster_divergente",
      detalle: `Agentes solo en CRM: ${soloCRM.length}; solo en Vicidial: ${soloVici.length}. Revisar match de nombres (C2).`,
      severidad: "info",
    });
  }

  // 5) Toques unificados.
  const toques: ToqueOut[] = [];

  // Llamada ← Gestiones (CRM trae el resultado del contacto). C1.
  for (const g of gestionesP.data) {
    if (!g.fecha) continue;
    toques.push({
      numDama: g.numDama,
      canal: "Llamada",
      dia: g.fecha,
      efectivo: gestionEsEfectiva(g.tipoGestion),
      meta: { agente: g.agenteNombre ? normalizeName(g.agenteNombre) : null },
    });
  }

  // IVR. C1.
  const ivrP = parseIvr(files.ivr);
  flags.push(...ivrP.flags);
  for (const r of ivrP.data) {
    if (r.numDama == null || !r.fecha) continue;
    toques.push({
      numDama: r.numDama,
      canal: "IVR",
      dia: r.fecha,
      efectivo: ivrEsEfectivo(r.status),
      meta: { dtmf: r.respuestaDtmf },
    });
  }

  // SMS. C1.
  const smsP = parseSms(files.sms);
  flags.push(...smsP.flags);
  for (const r of smsP.data) {
    if (r.numDama == null || !r.fechaEnvio) continue;
    toques.push({
      numDama: r.numDama,
      canal: "SMS",
      dia: r.fechaEnvio,
      efectivo: smsEsEfectivo(r.descripcion),
      meta: { operador: r.operador },
    });
  }

  // 6) Fechas de corte / madurez.
  let fechaCorteDatos: string | null = null;
  for (const t of toques) fechaCorteDatos = maxISO(fechaCorteDatos, t.dia);
  let fechaLiberacion: string | null = null;
  for (const c of cartera) fechaLiberacion = minISO(fechaLiberacion, c.fechaEntrega);
  let fechaMaxPago: string | null = null;
  for (const p of pagos) fechaMaxPago = maxISO(fechaMaxPago, p.fechaPago);

  // 7) Perfilado (tasas de cruce).
  const gestionEnCartera = gestionesP.data.filter((g) =>
    carteraDamas.has(g.numDama),
  ).length;
  const ivrEnCartera = ivrP.data.filter(
    (r) => r.numDama != null && carteraDamas.has(r.numDama),
  ).length;
  const smsEnCartera = smsP.data.filter(
    (r) => r.numDama != null && carteraDamas.has(r.numDama),
  ).length;

  const profile: Profile = {
    filas: {
      cartera: cartera.length,
      pagos: pagos.length,
      gestiones: gestionesP.data.length,
      vicidial: vicidialP.data.length,
      ivr: ivrP.data.length,
      sms: smsP.data.length,
      toques: toques.length,
    },
    cruces: {
      pagosEnCartera: 1, // ya filtrados a cartera por construcción
      gestionesEnCartera: pct(gestionEnCartera, gestionesP.data.length),
      ivrEnCartera: pct(ivrEnCartera, ivrP.data.length),
      smsEnCartera: pct(smsEnCartera, smsP.data.length),
    },
    fechaCorteDatos,
    fechaLiberacion,
    fechaMaxPago,
    costoMarcador: costo,
    agentesSoloCRM: soloCRM,
    agentesSoloVicidial: soloVici,
  };

  // Alerta metodológica: pagos posteriores al corte de canal (§4).
  if (fechaMaxPago && fechaCorteDatos && fechaMaxPago > fechaCorteDatos) {
    flags.push({
      tipo: "sesgo_temporal",
      detalle: `Pagos hasta ${fechaMaxPago} vs. datos de canal hasta ${fechaCorteDatos}: el tramo posterior entra como espontáneo por construcción.`,
      severidad: "warn",
    });
  }

  return {
    cartera,
    pagos,
    toques,
    agentes,
    gestiones,
    profile,
    flags,
    header: {
      saldoAsignado: cartera.reduce((s, c) => s + c.saldoCobro, 0),
      deudas: cartera.length,
      consultoras: carteraDamas.size,
    },
  };
}

/** Variante que recibe buffers .xlsx y los lee antes de construir. */
export function buildIngestFromBuffers(buffers: {
  cartera: Buffer;
  pagos: Buffer;
  gestiones: Buffer;
  vicidial: Buffer;
  ivr: Buffer;
  sms: Buffer;
}): IngestResult {
  return buildIngest({
    cartera: readSheet(buffers.cartera),
    pagos: readSheet(buffers.pagos),
    gestiones: readSheet(buffers.gestiones),
    vicidial: readSheet(buffers.vicidial),
    ivr: readSheet(buffers.ivr),
    sms: readSheet(buffers.sms),
  });
}

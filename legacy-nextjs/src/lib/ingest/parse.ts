/**
 * Parseo de los 6 .xlsx (§3). Los tratamos como CRUDOS, no como verdad limpia.
 * SheetJS corre del lado servidor (nunca en el cliente). Cada parser mapea a
 * una entidad normalizada y arrastra un arreglo de QualityFlag con lo que
 * encontró sospechoso (fechas nulas, encoding roto, coacciones fallidas).
 */
import * as XLSX from "xlsx";
import {
  toISODate,
  toInt,
  toNum,
  toStr,
  tieneEncodingRoto,
} from "./coerce";
import {
  CarteraRow,
  GestionRow,
  IvrRow,
  PagoRow,
  QualityFlag,
  RawRow,
  SmsRow,
  VicidialRow,
} from "./types";
import { normalizeName } from "../attribution/normalize";

/** Lee la primera hoja de un buffer .xlsx a filas objeto. */
export function readSheet(buffer: ArrayBuffer | Buffer): RawRow[] {
  const wb = XLSX.read(buffer, { type: "buffer", cellDates: true });
  const first = wb.SheetNames[0];
  const ws = wb.Sheets[first];
  return XLSX.utils.sheet_to_json<RawRow>(ws, { defval: null, raw: true });
}

/** Busca un valor por varios nombres candidatos (case/acento-insensible). */
export function pick(row: RawRow, ...candidates: string[]): unknown {
  const keys = Object.keys(row);
  for (const cand of candidates) {
    const target = normKey(cand);
    const hit = keys.find((k) => normKey(k) === target);
    if (hit !== undefined) return row[hit];
  }
  return null;
}

function normKey(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

// ── Cartera ──────────────────────────────────────────────────────────────
export function parseCartera(rows: RawRow[]): {
  data: CarteraRow[];
  flags: QualityFlag[];
} {
  const flags: QualityFlag[] = [];
  const byKey = new Map<string, CarteraRow>();
  let encodingRoto = 0;
  let sinLlave = 0;

  for (const row of rows) {
    const numDama = toInt(pick(row, "NumDama"));
    const anio = toStr(pick(row, "AnioCampaniaSaldo"));
    let damaDeuda = toStr(pick(row, "Dama-deuda", "DamaDeuda", "Dama_deuda"));
    if (!damaDeuda && numDama != null && anio) damaDeuda = `${numDama}-${anio}`;

    if (numDama == null || !damaDeuda) {
      sinLlave++;
      continue;
    }

    const zona = toStr(pick(row, "NumeroZonaFacturacion", "zona"));
    const ruta = toStr(pick(row, "Ruta"));
    if (tieneEncodingRoto(zona) || tieneEncodingRoto(ruta)) encodingRoto++;

    const fechaEntrega = toISODate(pick(row, "FechaEntrega"));
    const rec: CarteraRow = {
      damaDeuda,
      numDama,
      saldoCobro: toNum(pick(row, "SaldoCobro")),
      zona,
      ruta,
      fechaEntrega,
    };

    // Dedup por Dama-deuda conservando la última FechaEntrega (§3).
    const prev = byKey.get(damaDeuda);
    if (!prev || (fechaEntrega ?? "") > (prev.fechaEntrega ?? "")) {
      byKey.set(damaDeuda, rec);
    }
  }

  const dupes = rows.length - byKey.size - sinLlave;
  if (dupes > 0)
    flags.push({
      tipo: "cartera_duplicados",
      detalle: `${dupes} Dama-deuda duplicadas deduplicadas por última FechaEntrega.`,
      severidad: "info",
    });
  if (sinLlave > 0)
    flags.push({
      tipo: "cartera_sin_llave",
      detalle: `${sinLlave} filas sin NumDama/Dama-deuda descartadas.`,
      severidad: "warn",
    });
  if (encodingRoto > 0)
    flags.push({
      tipo: "encoding_roto",
      detalle: `${encodingRoto} filas de Cartera con encoding roto (Ã³/Ã±) en zona/ruta.`,
      severidad: "warn",
    });

  return { data: [...byKey.values()], flags };
}

// ── Pagos ────────────────────────────────────────────────────────────────
export function parsePagos(
  rows: RawRow[],
  carteraKeys: Set<string>,
): { data: PagoRow[]; flags: QualityFlag[] } {
  const flags: QualityFlag[] = [];
  const byKey = new Map<string, PagoRow>();
  let fueraDeCartera = 0;

  for (const row of rows) {
    const numDama = toInt(pick(row, "NumDama"));
    const anio = toStr(pick(row, "AnioCampaniaSaldo"));
    let damaDeuda = toStr(pick(row, "Dama-deuda", "DamaDeuda"));
    if (!damaDeuda && numDama != null && anio) damaDeuda = `${numDama}-${anio}`;
    if (numDama == null || !damaDeuda) continue;

    // Filtra a las campañas presentes en la Cartera cargada (§3, ej. C11).
    if (!carteraKeys.has(damaDeuda)) {
      fueraDeCartera++;
      continue;
    }

    const rec: PagoRow = {
      damaDeuda,
      numDama,
      idCobrador: toStr(pick(row, "IdCobrador")),
      fechaPago: toISODate(pick(row, "FechaEntrega", "FechaPago")),
      saldoRemanente: toNum(pick(row, "SaldoCampania", "SaldoRemanente")),
      estadoProceso: toStr(pick(row, "EstadoProceso")),
    };
    // Upsert por dama_deuda conservando el pago más reciente.
    const prev = byKey.get(damaDeuda);
    if (!prev || (rec.fechaPago ?? "") >= (prev.fechaPago ?? "")) {
      byKey.set(damaDeuda, rec);
    }
  }

  if (fueraDeCartera > 0)
    flags.push({
      tipo: "pagos_fuera_de_cartera",
      detalle: `${fueraDeCartera} pagos de campañas anteriores (fuera de la Cartera cargada) filtrados.`,
      severidad: "info",
    });

  return { data: [...byKey.values()], flags };
}

// ── Gestiones (CRM) ──────────────────────────────────────────────────────
export function parseGestiones(rows: RawRow[]): {
  data: GestionRow[];
  flags: QualityFlag[];
} {
  const flags: QualityFlag[] = [];
  const data: GestionRow[] = [];
  let medicionVacia = 0;
  let sinFecha = 0;

  for (const row of rows) {
    const numDama = toInt(pick(row, "CODIGO", "NumDama"));
    if (numDama == null) continue;

    const fecha = toISODate(pick(row, "FECHA"));
    if (!fecha) sinFecha++;

    const medicion = toStr(pick(row, "MEDICION"));
    if (!medicion) medicionVacia++;

    data.push({
      numDama,
      agenteNombre: toStr(pick(row, "NOMBRE GESTOR", "NOMBREGESTOR")),
      fecha,
      tipoGestion: toStr(pick(row, "TIPO DE GESTION", "TIPODEGESTION")),
      // El header viene con typo: "TIPIFICACIlON" (sic).
      tipificacion: toStr(pick(row, "TIPIFICACION", "TIPIFICACIlON")),
      promesaFecha: toISODate(pick(row, "PROMESA", "DIA PROM")),
      montoPrometido: null, // el archivo no trae monto; se deja hook
      temp: toStr(pick(row, "temp")),
      zona: toStr(pick(row, "zona")),
      ruta: toStr(pick(row, "ruta")),
    });
  }

  if (medicionVacia > 0)
    flags.push({
      tipo: "medicion_vacia",
      detalle: `MEDICION vacía en ${medicionVacia}/${rows.length} filas (~99.97%) — inutilizable, no se muestra.`,
      severidad: "info",
    });
  if (sinFecha > 0)
    flags.push({
      tipo: "gestiones_sin_fecha",
      detalle: `${sinFecha} gestiones sin FECHA parseable.`,
      severidad: "warn",
    });

  return { data, flags };
}

// ── Vicidial ─────────────────────────────────────────────────────────────
export function parseVicidial(rows: RawRow[]): {
  data: VicidialRow[];
  flags: QualityFlag[];
} {
  const flags: QualityFlag[] = [];
  const data: VicidialRow[] = rows.map((row) => ({
    fullName: toStr(pick(row, "full_name", "fullname")),
    user: toStr(pick(row, "user")),
    callDate: toISODate(pick(row, "call_date", "calldate")),
    status: toStr(pick(row, "status_name", "status")),
    lengthSec: toNum(pick(row, "length_in_sec", "lengthinsec")),
    numDama: toInt(pick(row, "phone_number_dialed")), // sirve solo como referencia
  }));
  return { data, flags };
}

// ── IVR / Reminder ───────────────────────────────────────────────────────
export function parseIvr(rows: RawRow[]): {
  data: IvrRow[];
  flags: QualityFlag[];
} {
  const flags: QualityFlag[] = [];
  const data: IvrRow[] = [];
  let sinFecha = 0;

  for (const row of rows) {
    const fecha = toISODate(pick(row, "Fecha de la Llamada", "FechadelaLlamada"));
    if (!fecha) {
      sinFecha++;
      // Excluir de atribución pero contarlas aparte (§3).
      continue;
    }
    data.push({
      numDama: toInt(pick(row, "Nodama", "NoDama", "NumDama")),
      saldo: toNum(pick(row, "Saldo")),
      temp: toStr(pick(row, "Temp")),
      fecha,
      status: toStr(pick(row, "Status")),
      respuestaDtmf: toStr(pick(row, "Respuesta DTMF", "RespuestaDTMF")),
    });
  }

  if (sinFecha > 0)
    flags.push({
      tipo: "ivr_sin_fecha",
      detalle: `${sinFecha} llamadas IVR sin fecha parseable — excluidas de atribución, contadas aparte.`,
      severidad: "warn",
    });

  return { data, flags };
}

// ── SMS ──────────────────────────────────────────────────────────────────
export function parseSms(rows: RawRow[]): {
  data: SmsRow[];
  flags: QualityFlag[];
} {
  const flags: QualityFlag[] = [];
  const data: SmsRow[] = [];
  let damaNula = 0;

  for (const row of rows) {
    const numDama = toInt(pick(row, "Dama"));
    if (numDama == null) {
      damaNula++;
      continue; // descartar nulos (§3)
    }
    data.push({
      numDama,
      fechaEnvio: toISODate(pick(row, "Fecha Envio", "FechaEnvio")),
      descripcion: toStr(pick(row, "Descripcion")),
      costo: toNum(pick(row, "Costo")),
      operador: toStr(pick(row, "Operador")),
    });
  }

  if (damaNula > 0)
    flags.push({
      tipo: "sms_dama_nula",
      detalle: `${damaNula} SMS con Dama no coercible a entero — descartados.`,
      severidad: "info",
    });

  return { data, flags };
}

export const _internal = { normKey };

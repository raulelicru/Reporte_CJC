/**
 * Coacciones y parseo de fechas para la ingesta (§3).
 * Cada trampa documentada se maneja como REGLA, no como bug.
 */

/** Convierte a ISO `YYYY-MM-DD` o null si no es parseable. */
export function toISODate(value: unknown): string | null {
  if (value == null || value === "") return null;

  // Caso 1: entero YYYYMMDD (FechaEntrega de Cartera/Pagos).
  if (typeof value === "number" && Number.isInteger(value) && value > 19000101) {
    return fromYYYYMMDD(String(value));
  }
  if (typeof value === "string" && /^\d{8}$/.test(value.trim())) {
    return fromYYYYMMDD(value.trim());
  }

  // Caso 2: serial de Excel (número de días desde 1899-12-30).
  if (typeof value === "number" && value > 20000 && value < 60000) {
    const ms = Math.round((value - 25569) * 86400 * 1000);
    return new Date(ms).toISOString().slice(0, 10);
  }

  // Caso 3: dd/mm/YYYY [HH:MM] (IVR/Reminder).
  if (typeof value === "string") {
    const s = value.trim();
    const m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (m) {
      const [, d, mo, y] = m;
      return `${y}-${mo.padStart(2, "0")}-${d.padStart(2, "0")}`;
    }
    // Caso 4: ISO o datetime estándar (Gestiones FECHA, SMS Fecha Envio).
    const dt = new Date(s);
    if (!Number.isNaN(dt.getTime())) return dt.toISOString().slice(0, 10);
  }

  // Caso 5: Date nativo (SheetJS con cellDates).
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }

  return null;
}

function fromYYYYMMDD(s: string): string | null {
  if (!/^\d{8}$/.test(s)) return null;
  const y = s.slice(0, 4);
  const m = s.slice(4, 6);
  const d = s.slice(6, 8);
  const mo = Number(m);
  const day = Number(d);
  if (mo < 1 || mo > 12 || day < 1 || day > 31) return null;
  return `${y}-${m}-${d}`;
}

/** Coacciona a entero; null si vacío o no numérico (SMS `Dama` puede venir texto). */
export function toInt(value: unknown): number | null {
  if (value == null || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? Math.trunc(value) : null;
  const s = String(value).replace(/[^\d-]/g, "");
  if (s === "" || s === "-") return null;
  const n = parseInt(s, 10);
  return Number.isFinite(n) ? n : null;
}

/** Coacciona a número decimal; 0 por defecto. */
export function toNum(value: unknown): number {
  if (value == null || value === "") return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const s = String(value).replace(/[^\d.,-]/g, "").replace(/,/g, "");
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : 0;
}

export function toStr(value: unknown): string | null {
  if (value == null) return null;
  const s = String(value).trim();
  return s === "" ? null : s;
}

/**
 * Detecta encoding roto (mojibake `Ã³`, `Ã±`, `Â`) — se reporta como hallazgo
 * de calidad, no se esconde (§3).
 */
const MOJIBAKE = /Ã.|Â.|â€/;
export function tieneEncodingRoto(value: unknown): boolean {
  return typeof value === "string" && MOJIBAKE.test(value);
}

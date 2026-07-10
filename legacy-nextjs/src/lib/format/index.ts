/** Formateadores de cifras. Toda cifra usa tabular-nums en la UI (§9). */

export function money(n: number | null | undefined): string {
  const v = n ?? 0;
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 0,
  }).format(v);
}

export function moneyK(n: number | null | undefined): string {
  const v = n ?? 0;
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return money(v);
}

export function pct(n: number | null | undefined, digits = 1): string {
  const v = n ?? 0;
  return `${(v * 100).toFixed(digits)}%`;
}

export function num(n: number | null | undefined): string {
  return new Intl.NumberFormat("es-MX").format(n ?? 0);
}

export function delta(actual: number, previo: number | null | undefined): {
  texto: string;
  signo: "up" | "down" | "flat";
} {
  if (previo == null || previo === 0) return { texto: "—", signo: "flat" };
  const d = (actual - previo) / Math.abs(previo);
  const signo = d > 0.001 ? "up" : d < -0.001 ? "down" : "flat";
  return { texto: `${d > 0 ? "+" : ""}${(d * 100).toFixed(1)}%`, signo };
}

/** Días desde una fecha ISO hasta otra (madurez de campaña). */
export function diasEntre(desde: string | null, hasta: string | null): number | null {
  if (!desde || !hasta) return null;
  const a = Date.parse(desde);
  const b = Date.parse(hasta);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.round((b - a) / 86_400_000);
}

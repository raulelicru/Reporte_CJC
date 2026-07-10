/**
 * Normalización de nombres de agente (C2).
 * Los ~21 gestores del CRM coinciden con los agentes de Vicidial por nombre
 * normalizado: minúsculas, sin acentos, sin dobles espacios, trim.
 */
export function normalizeName(raw: string | null | undefined): string {
  if (!raw) return "";
  return raw
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // quita diacríticos combinantes
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ") // colapsa puntuación a espacio
    .replace(/\s+/g, " ")
    .trim();
}

/** Marcador automático de Vicidial (C3): costo de telefonía, no canal. */
const NOMBRES_MARCADOR = new Set([
  normalizeName("Outbound Auto Dial"),
  normalizeName("Inbound No Agent"),
]);

export function isAutoDialer(fullName: string | null | undefined): boolean {
  return NOMBRES_MARCADOR.has(normalizeName(fullName));
}

/**
 * Predicados de contacto efectivo (C1) por fuente y del marcador (C3).
 * Puros y testeables. La ingesta los usa para emitir `Touch.efectivo`.
 *
 * C1 · Contacto efectivo ≠ intento — un marcado que no conecta jamás atribuye.
 */

/** Gestiones (CRM) → efectivo si TIPO DE GESTION == 'CONTACTO'. */
export function gestionEsEfectiva(tipoGestion: string | null | undefined): boolean {
  return norm(tipoGestion) === "contacto";
}

/** IVR/Reminder → efectivo si Status == 'Contacto' (contestó o completada). */
export function ivrEsEfectivo(status: string | null | undefined): boolean {
  return norm(status) === "contacto";
}

/** SMS → efectivo si Descripcion ∈ {Exitoso, Enviado}. */
export function smsEsEfectivo(descripcion: string | null | undefined): boolean {
  const d = norm(descripcion);
  return d === "exitoso" || d === "enviado";
}

/** Estado de liquidación en Pagos: R y E ⇒ saldo remanente 0 = liquidado. */
export function esLiquidacion(estadoProceso: string | null | undefined): boolean {
  const e = norm(estadoProceso);
  return e === "r" || e === "e";
}

function norm(s: string | null | undefined): string {
  return (s ?? "")
    .toString()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

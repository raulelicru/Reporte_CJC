/**
 * CLASIFICACIÓN DE GESTORES (§6) — quién puede capacitar y quién necesita apoyo.
 *
 * Tres dimensiones, umbrales RELATIVOS a la mediana del equipo en esa campaña
 * (no fijos — el equipo evoluciona). Lenguaje de desarrollo de talento, nunca
 * acusatorio: la clasificación orienta coaching, jamás despido automático.
 *
 * Cuadrante (contacto vs. cumplimiento contra la mediana):
 *   Contacto ALTO + Cumplimiento ALTO → MENTOR
 *   Contacto ALTO + Cumplimiento BAJO → COACHING_CIERRE
 *   Contacto BAJO + Cumplimiento ALTO → SUBIR_VOLUMEN
 *   Contacto BAJO + Cumplimiento BAJO → PLAN_MEJORA
 */

export type Clasificacion =
  | "MENTOR"
  | "COACHING_CIERRE"
  | "SUBIR_VOLUMEN"
  | "PLAN_MEJORA";

/** Umbral de cumplimiento débil (~32%): compromisos poco firmes ⇒ coaching. */
export const UMBRAL_CUMPLIMIENTO_DEBIL = 0.32;

export interface GestorInput {
  agenteId: string;
  nombre: string;
  gestiones: number;
  contactosEfectivos: number;
  pdp: number; // promesas de pago registradas
  pdpCumplidas: number; // pagadas dentro de fecha prometida + 3 días
  recuperadoAtribuido: number;
}

export interface GestorClasificado extends GestorInput {
  tasaContacto: number; // Alcance
  pctCumplimiento: number; // Calidad de negociación
  rendimiento: number; // recuperado / gestión (apoyo/desempate)
  contactoAlto: boolean;
  cumplimientoAlto: boolean;
  cumplimientoDebil: boolean; // < UMBRAL_CUMPLIMIENTO_DEBIL
  clasificacion: Clasificacion;
  percentilContacto: number; // 0..1
  percentilCumplimiento: number; // 0..1
  /** Solo para PLAN_MEJORA: agenteId del mentor sugerido. */
  mentorSugerido: string | null;
}

/** Mediana de una lista numérica (0 si vacía). */
export function mediana(xs: number[]): number {
  if (xs.length === 0) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 !== 0 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

/** Percentil (rank fraccional) de `x` dentro de `xs`. 0..1. */
export function percentil(x: number, xs: number[]): number {
  if (xs.length === 0) return 0;
  const menores = xs.filter((v) => v < x).length;
  const iguales = xs.filter((v) => v === x).length;
  return (menores + iguales / 2) / xs.length;
}

function cuadrante(contactoAlto: boolean, cumplimientoAlto: boolean): Clasificacion {
  if (contactoAlto && cumplimientoAlto) return "MENTOR";
  if (contactoAlto && !cumplimientoAlto) return "COACHING_CIERRE";
  if (!contactoAlto && cumplimientoAlto) return "SUBIR_VOLUMEN";
  return "PLAN_MEJORA";
}

/**
 * Clasifica al equipo completo de una campaña.
 * Umbrales = mediana del equipo. "Alto" ⇒ ≥ mediana.
 */
export function clasificarEquipo(gestores: GestorInput[]): GestorClasificado[] {
  const enriquecidos = gestores.map((g) => {
    const tasaContacto = g.gestiones > 0 ? g.contactosEfectivos / g.gestiones : 0;
    const pctCumplimiento = g.pdp > 0 ? g.pdpCumplidas / g.pdp : 0;
    const rendimiento = g.gestiones > 0 ? g.recuperadoAtribuido / g.gestiones : 0;
    return { ...g, tasaContacto, pctCumplimiento, rendimiento };
  });

  const contactos = enriquecidos.map((g) => g.tasaContacto);
  const cumplimientos = enriquecidos.map((g) => g.pctCumplimiento);
  const medContacto = mediana(contactos);
  const medCumplimiento = mediana(cumplimientos);

  const clasificados: GestorClasificado[] = enriquecidos.map((g) => {
    const contactoAlto = g.tasaContacto >= medContacto;
    const cumplimientoAlto = g.pctCumplimiento >= medCumplimiento;
    return {
      ...g,
      contactoAlto,
      cumplimientoAlto,
      cumplimientoDebil: g.pctCumplimiento < UMBRAL_CUMPLIMIENTO_DEBIL,
      clasificacion: cuadrante(contactoAlto, cumplimientoAlto),
      percentilContacto: percentil(g.tasaContacto, contactos),
      percentilCumplimiento: percentil(g.pctCumplimiento, cumplimientos),
      mentorSugerido: null,
    };
  });

  return emparejarMentores(clasificados);
}

/**
 * Empareja cada PLAN_MEJORA con el MENTOR de mayor cumplimiento y capacidad.
 * "Capacidad" = cumplimiento alto + buena tasa de contacto; desempate por
 * volumen de gestiones (un mentor con más base ya demuestra que sostiene carga).
 */
export function emparejarMentores(
  clasificados: GestorClasificado[],
): GestorClasificado[] {
  const mentores = clasificados
    .filter((g) => g.clasificacion === "MENTOR")
    .sort(
      (a, b) =>
        b.pctCumplimiento - a.pctCumplimiento ||
        b.tasaContacto - a.tasaContacto ||
        b.gestiones - a.gestiones,
    );

  const mejorMentor = mentores[0]?.agenteId ?? null;

  return clasificados.map((g) =>
    g.clasificacion === "PLAN_MEJORA"
      ? { ...g, mentorSugerido: mejorMentor }
      : g,
  );
}

/** Etiqueta legible para la UI (desarrollo de talento, sin juicio). */
export const ETIQUETA_CLASIFICACION: Record<Clasificacion, string> = {
  MENTOR: "Mentor — puede capacitar al equipo",
  COACHING_CIERRE: "Coaching de cierre — contacta bien, promesas flojas",
  SUBIR_VOLUMEN: "Subir volumen — buen negociador, darle más base",
  PLAN_MEJORA: "Plan de mejora — acompañamiento cercano",
};

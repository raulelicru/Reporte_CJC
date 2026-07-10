/**
 * MOTOR DE ATRIBUCIÓN (§4) — el corazón del sistema.
 *
 * Todo aquí son funciones PURAS y determinísticas: mismas entradas ⇒ mismas
 * salidas, sin I/O, sin fecha "hoy", sin aleatoriedad. Así se puede testear
 * a fondo (engine.test.ts cubre C1–C4, empates, ventana de 7 días y sesgo
 * temporal). Si el dashboard rompe estas reglas, el dashboard no sirve.
 *
 * Controles antifraude codificados:
 *   C1 · Contacto efectivo ≠ intento  → solo `touch.efectivo` recibe atribución.
 *   C2 · Gestiones + Vicidial = 1 canal → la ingesta ya emite ambos como "Llamada".
 *   C3 · Marcador automático = costo   → nunca produce toques efectivos (isAutoDialer).
 *   C4 · Prohibido inflar causalidad   → pago sin toque efectivo previo = Espontáneo.
 */

import {
  Attribution,
  CanalInfluencia,
  CanalPrimario,
  CanalReal,
  Payment,
  PRIORIDAD_CANAL,
  SesgoTemporal,
  Touch,
} from "./types";

const MS_POR_DIA = 24 * 60 * 60 * 1000;
export const VENTANA_DIAS = 7;

/** Parsea un ISO `YYYY-MM-DD` a epoch UTC. Ignora hora para evitar sesgo de zona. */
export function diaUTC(iso: string): number {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

/** Diferencia en días completos entre dos ISO date (a − b). */
export function difDias(a: string, b: string): number {
  return Math.round((diaUTC(a) - diaUTC(b)) / MS_POR_DIA);
}

/**
 * MODELO PRIMARIO — último toque efectivo.
 * Asigna un pago al último canal con contacto efectivo en la ventana
 * [fechaPago − VENTANA_DIAS, fechaPago]. Empate el mismo día ⇒ prioridad
 * Llamada > IVR > SMS. Sin toque efectivo en ventana ⇒ Espontáneo (C4).
 *
 * @param touchesDeLaDama toques (de cualquier efectividad) de esa consultora.
 */
export function attributeLastTouch(
  payment: Payment,
  touchesDeLaDama: Touch[],
): { canal: Attribution["canal"]; touch: Touch | null } {
  let mejor: Touch | null = null;

  for (const t of touchesDeLaDama) {
    if (!t.efectivo) continue; // C1
    if (t.numDama !== payment.numDama) continue;

    const delta = difDias(payment.fechaPago, t.dia);
    if (delta < 0 || delta > VENTANA_DIAS) continue; // fuera de ventana

    if (mejor === null) {
      mejor = t;
      continue;
    }

    // Preferir el toque más reciente; empate exacto de día ⇒ prioridad de canal.
    if (t.dia > mejor.dia) {
      mejor = t;
    } else if (t.dia === mejor.dia && PRIORIDAD_CANAL[t.canal] > PRIORIDAD_CANAL[mejor.canal]) {
      mejor = t;
    }
  }

  if (mejor === null) return { canal: "Espontaneo", touch: null };
  return { canal: mejor.canal, touch: mejor };
}

/**
 * Atribuye TODOS los pagos (modelo primario) y marca sesgo temporal por pago.
 * `fechaCorteCanal` = última fecha con datos de canal; los pagos posteriores
 * no pueden recibir atribución por construcción (§4).
 */
export function attributeAll(
  payments: Payment[],
  touches: Touch[],
  fechaCorteCanal: string | null,
): Attribution[] {
  // Index de toques efectivos por consultora para no escanear todo por pago.
  const porDama = new Map<number, Touch[]>();
  for (const t of touches) {
    if (!t.efectivo) continue; // C1: solo efectivos entran al índice
    const arr = porDama.get(t.numDama);
    if (arr) arr.push(t);
    else porDama.set(t.numDama, [t]);
  }

  return payments.map((p) => {
    const candidatos = porDama.get(p.numDama) ?? [];
    const { canal, touch } = attributeLastTouch(p, candidatos);
    const fueraDeVentana =
      fechaCorteCanal !== null && difDias(p.fechaPago, fechaCorteCanal) > 0;
    return { payment: p, canal, touch, fueraDeVentana };
  });
}

/** Agrega el resultado del modelo primario por canal. */
export function resumenPrimario(atribs: Attribution[]): CanalPrimario[] {
  const acc = new Map<
    string,
    { monto: number; pagos: number; damas: Set<number> }
  >();
  let total = 0;

  for (const a of atribs) {
    const r = a.payment.recuperado;
    total += r;
    const cur = acc.get(a.canal) ?? { monto: 0, pagos: 0, damas: new Set() };
    cur.monto += r;
    cur.pagos += 1;
    cur.damas.add(a.payment.numDama);
    acc.set(a.canal, cur);
  }

  const canales: Attribution["canal"][] = ["Llamada", "IVR", "SMS", "Espontaneo"];
  return canales
    .filter((c) => acc.has(c))
    .map((c) => {
      const cur = acc.get(c)!;
      return {
        canal: c,
        monto: cur.monto,
        pagos: cur.pagos,
        consultoras: cur.damas.size,
        pct: total > 0 ? cur.monto / total : 0,
      };
    });
}

/**
 * MODELO SECUNDARIO — influencia (any-touch).
 * % del monto de consultoras que recibieron ≥1 contacto efectivo de cada canal.
 * Sin ventana: cuenta cualquier toque efectivo. SUMA > 100% (una dama puede
 * ser tocada por varios canales) — la UI debe declararlo.
 */
export function influenceModel(
  payments: Payment[],
  touches: Touch[],
): { canales: CanalInfluencia[]; total: number } {
  // Canales efectivos por consultora.
  const canalesPorDama = new Map<number, Set<CanalReal>>();
  for (const t of touches) {
    if (!t.efectivo) continue; // C1
    const s = canalesPorDama.get(t.numDama) ?? new Set<CanalReal>();
    s.add(t.canal);
    canalesPorDama.set(t.numDama, s);
  }

  const acc: Record<CanalReal, { monto: number; damas: Set<number> }> = {
    Llamada: { monto: 0, damas: new Set() },
    IVR: { monto: 0, damas: new Set() },
    SMS: { monto: 0, damas: new Set() },
  };
  let total = 0;

  for (const p of payments) {
    total += p.recuperado;
    const canales = canalesPorDama.get(p.numDama);
    if (!canales) continue;
    for (const c of canales) {
      acc[c].monto += p.recuperado;
      acc[c].damas.add(p.numDama);
    }
  }

  const canales = (Object.keys(acc) as CanalReal[]).map((c) => ({
    canal: c,
    monto: acc[c].monto,
    consultoras: acc[c].damas.size,
    pct: total > 0 ? acc[c].monto / total : 0,
  }));

  return { canales, total };
}

/**
 * SESGO TEMPORAL (§4) — pagos posteriores a la última fecha de datos de canal.
 * No pueden recibir atribución; entran como espontáneo por construcción.
 * Se reporta como alerta metodológica, no como hallazgo de negocio.
 */
export function sesgoTemporal(
  payments: Payment[],
  fechaCorteCanal: string | null,
): SesgoTemporal {
  let montoTotal = 0;
  let montoFuera = 0;
  let pagosFuera = 0;

  for (const p of payments) {
    montoTotal += p.recuperado;
    if (fechaCorteCanal !== null && difDias(p.fechaPago, fechaCorteCanal) > 0) {
      montoFuera += p.recuperado;
      pagosFuera += 1;
    }
  }

  return {
    fechaCorteCanal,
    montoFueraDeVentana: montoFuera,
    montoTotal,
    pctFueraDeVentana: montoTotal > 0 ? montoFuera / montoTotal : 0,
    pagosFueraDeVentana: pagosFuera,
  };
}

/**
 * Eficiencia por toque = monto atribuido al canal ÷ nº de toques efectivos
 * del canal. Métrica de apoyo (correlación, no causa).
 */
export function eficienciaPorToque(
  atribs: Attribution[],
  touches: Touch[],
): Record<CanalReal, number> {
  const montoPorCanal: Record<CanalReal, number> = { Llamada: 0, IVR: 0, SMS: 0 };
  for (const a of atribs) {
    if (a.canal !== "Espontaneo") montoPorCanal[a.canal] += a.payment.recuperado;
  }
  const toquesPorCanal: Record<CanalReal, number> = { Llamada: 0, IVR: 0, SMS: 0 };
  for (const t of touches) {
    if (t.efectivo) toquesPorCanal[t.canal] += 1;
  }
  return {
    Llamada: toquesPorCanal.Llamada > 0 ? montoPorCanal.Llamada / toquesPorCanal.Llamada : 0,
    IVR: toquesPorCanal.IVR > 0 ? montoPorCanal.IVR / toquesPorCanal.IVR : 0,
    SMS: toquesPorCanal.SMS > 0 ? montoPorCanal.SMS / toquesPorCanal.SMS : 0,
  };
}

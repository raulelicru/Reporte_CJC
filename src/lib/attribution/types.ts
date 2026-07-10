/**
 * Tipos del motor de atribución (§4).
 * El motor trabaja sobre estructuras planas y normalizadas; la ingesta
 * (parse.ts) es quien traduce los .xlsx crudos a estos shapes.
 */

/** Canales reales de recuperación + Espontáneo. El marcador automático NO es canal (C3). */
export type Canal = "Llamada" | "IVR" | "SMS" | "Espontaneo";

/** Canales que sí pueden recibir atribución (excluye Espontáneo). */
export type CanalReal = Exclude<Canal, "Espontaneo">;

/** Prioridad de desempate el mismo día (Llamada > IVR > SMS) — §4 modelo primario. */
export const PRIORIDAD_CANAL: Record<CanalReal, number> = {
  Llamada: 3,
  IVR: 2,
  SMS: 1,
};

/**
 * Un toque unificado (gestiones+vicidial → Llamada, IVR, SMS).
 * `efectivo` codifica C1: solo el toque que conectó cuenta.
 */
export interface Touch {
  numDama: number;
  canal: CanalReal;
  /** Día del toque como ISO `YYYY-MM-DD` (se ignora la hora para atribución). */
  dia: string;
  efectivo: boolean;
  meta?: Record<string, unknown>;
}

/** Un pago recuperado, ya cruzado contra cartera. */
export interface Payment {
  damaDeuda: string;
  numDama: number;
  /** Fecha de pago ISO `YYYY-MM-DD`. */
  fechaPago: string;
  /** Monto recuperado = SaldoCobro − SaldoCampania (§4). Debe ser > 0 para atribuir. */
  recuperado: number;
}

/** Resultado de atribuir un pago individual (modelo primario, último toque efectivo). */
export interface Attribution {
  payment: Payment;
  canal: Canal;
  /** El toque ganador, si lo hubo. `null` ⇒ Espontáneo. */
  touch: Touch | null;
  /** true si el pago cae fuera de la ventana de datos de canal (sesgo temporal, §4). */
  fueraDeVentana: boolean;
}

/** Agregado por canal del modelo primario. */
export interface CanalPrimario {
  canal: Canal;
  monto: number;
  pagos: number;
  consultoras: number;
  pct: number; // sobre el total recuperado
}

/** Agregado del modelo secundario (influencia any-touch). Suma > 100%. */
export interface CanalInfluencia {
  canal: CanalReal;
  monto: number; // monto de consultoras con ≥1 contacto efectivo del canal
  consultoras: number;
  pct: number; // sobre el total recuperado — puede exceder 100%
}

/** Reporte de sesgo temporal (§4). */
export interface SesgoTemporal {
  fechaCorteCanal: string | null;
  montoFueraDeVentana: number;
  montoTotal: number;
  pctFueraDeVentana: number;
  pagosFueraDeVentana: number;
}

/** Costo del marcador automático (C3) — nunca recuperación. */
export interface CostoMarcador {
  llamadas: number;
  minutos: number;
  contactosEfectivos: number; // debe ser 0 en la data real
}

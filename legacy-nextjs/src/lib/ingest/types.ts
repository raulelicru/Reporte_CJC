/** Entidades normalizadas que produce la ingesta (mapean 1:1 al esquema §5). */

export interface CarteraRow {
  damaDeuda: string;
  numDama: number;
  saldoCobro: number;
  zona: string | null;
  ruta: string | null;
  fechaEntrega: string | null;
}

export interface PagoRow {
  damaDeuda: string;
  numDama: number;
  idCobrador: string | null;
  fechaPago: string | null;
  saldoRemanente: number;
  estadoProceso: string | null;
}

export interface GestionRow {
  numDama: number;
  agenteNombre: string | null;
  fecha: string | null;
  tipoGestion: string | null;
  tipificacion: string | null;
  promesaFecha: string | null;
  montoPrometido: number | null;
  temp: string | null;
  zona: string | null;
  ruta: string | null;
}

export interface VicidialRow {
  fullName: string | null;
  user: string | null;
  callDate: string | null;
  status: string | null;
  lengthSec: number;
  numDama: number | null;
}

export interface IvrRow {
  numDama: number | null;
  saldo: number;
  temp: string | null;
  fecha: string | null;
  status: string | null; // Contacto / No contesta
  respuestaDtmf: string | null;
}

export interface SmsRow {
  numDama: number | null;
  fechaEnvio: string | null;
  descripcion: string | null; // Exitoso / Enviado / …
  costo: number;
  operador: string | null;
}

export interface QualityFlag {
  tipo: string;
  detalle: string;
  severidad: "info" | "warn" | "error";
}

/** Lector genérico de filas de una hoja (SheetJS sheet_to_json → objetos). */
export type RawRow = Record<string, unknown>;

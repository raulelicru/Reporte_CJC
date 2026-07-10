import { describe, it, expect } from "vitest";
import {
  attributeLastTouch,
  attributeAll,
  resumenPrimario,
  influenceModel,
  sesgoTemporal,
  eficienciaPorToque,
  difDias,
  VENTANA_DIAS,
} from "./engine";
import { normalizeName, isAutoDialer } from "./normalize";
import {
  gestionEsEfectiva,
  ivrEsEfectivo,
  smsEsEfectivo,
  esLiquidacion,
} from "./predicates";
import { Payment, Touch } from "./types";

// Helpers para armar fixtures legibles.
const pago = (numDama: number, fechaPago: string, recuperado = 100): Payment => ({
  damaDeuda: `${numDama}-2025C12`,
  numDama,
  fechaPago,
  recuperado,
});
const toque = (
  numDama: number,
  canal: Touch["canal"],
  dia: string,
  efectivo = true,
): Touch => ({ numDama, canal, dia, efectivo });

describe("utilidades de fecha", () => {
  it("difDias cuenta días completos en UTC", () => {
    expect(difDias("2025-06-10", "2025-06-03")).toBe(7);
    expect(difDias("2025-06-03", "2025-06-10")).toBe(-7);
    expect(difDias("2025-06-10", "2025-06-10")).toBe(0);
  });
});

describe("C1 · contacto efectivo ≠ intento", () => {
  it("gestión solo cuenta con TIPO DE GESTION = CONTACTO", () => {
    expect(gestionEsEfectiva("CONTACTO")).toBe(true);
    expect(gestionEsEfectiva("contacto")).toBe(true);
    expect(gestionEsEfectiva("NO CONTACTO")).toBe(false);
    expect(gestionEsEfectiva("")).toBe(false);
  });
  it("IVR solo cuenta con Status = Contacto", () => {
    expect(ivrEsEfectivo("Contacto")).toBe(true);
    expect(ivrEsEfectivo("No contesta")).toBe(false);
  });
  it("SMS cuenta con Exitoso o Enviado", () => {
    expect(smsEsEfectivo("Exitoso")).toBe(true);
    expect(smsEsEfectivo("Enviado")).toBe(true);
    expect(smsEsEfectivo("Fallido")).toBe(false);
  });
  it("un toque NO efectivo jamás recibe atribución", () => {
    const p = pago(1, "2025-06-10");
    const touches = [toque(1, "Llamada", "2025-06-09", false)];
    expect(attributeLastTouch(p, touches).canal).toBe("Espontaneo");
  });
  it("attributeAll ignora toques no efectivos aunque estén en ventana", () => {
    const res = attributeAll(
      [pago(1, "2025-06-10")],
      [toque(1, "IVR", "2025-06-09", false), toque(1, "SMS", "2025-06-08", true)],
      "2025-06-30",
    );
    expect(res[0].canal).toBe("SMS");
  });
});

describe("C2 · gestiones + vicidial = un solo canal (Llamada)", () => {
  it("normaliza nombres para hacer match CRM ↔ Vicidial", () => {
    expect(normalizeName("José  Pérez")).toBe("jose perez");
    expect(normalizeName("JOSE PEREZ")).toBe("jose perez");
    expect(normalizeName("  María-Núñez ")).toBe("maria nunez");
  });
  it("dos toques del mismo agente (gestión + llamada) NO se duplican en atribución", () => {
    // Ambos llegan como canal Llamada; el pago se atribuye una sola vez a Llamada.
    const res = attributeAll(
      [pago(1, "2025-06-10", 500)],
      [toque(1, "Llamada", "2025-06-09"), toque(1, "Llamada", "2025-06-08")],
      "2025-06-30",
    );
    const resumen = resumenPrimario(res);
    const llamada = resumen.find((r) => r.canal === "Llamada")!;
    expect(llamada.monto).toBe(500); // no 1000
    expect(llamada.pagos).toBe(1);
  });
});

describe("C3 · marcador automático = costo, no canal", () => {
  it("identifica Outbound Auto Dial e Inbound No Agent", () => {
    expect(isAutoDialer("Outbound Auto Dial")).toBe(true);
    expect(isAutoDialer("outbound auto dial")).toBe(true);
    expect(isAutoDialer("Inbound No Agent")).toBe(true);
    expect(isAutoDialer("Juan Pérez")).toBe(false);
  });
});

describe("C4 · prohibido inflar causalidad", () => {
  it("pago sin contacto efectivo previo es Espontáneo", () => {
    const res = attributeLastTouch(pago(1, "2025-06-10"), []);
    expect(res.canal).toBe("Espontaneo");
    expect(res.touch).toBeNull();
  });
  it("un toque efectivo DESPUÉS del pago no atribuye (no hay causa retroactiva)", () => {
    const res = attributeLastTouch(pago(1, "2025-06-10"), [
      toque(1, "Llamada", "2025-06-11"),
    ]);
    expect(res.canal).toBe("Espontaneo");
  });
});

describe("modelo primario · ventana de 7 días", () => {
  it("incluye el toque exactamente a 7 días", () => {
    const res = attributeLastTouch(pago(1, "2025-06-10"), [
      toque(1, "SMS", "2025-06-03"),
    ]);
    expect(res.canal).toBe("SMS");
  });
  it("excluye el toque a 8 días", () => {
    const res = attributeLastTouch(pago(1, "2025-06-11"), [
      toque(1, "SMS", "2025-06-03"),
    ]);
    expect(res.canal).toBe("Espontaneo");
    expect(difDias("2025-06-11", "2025-06-03")).toBe(VENTANA_DIAS + 1);
  });
  it("elige el toque más reciente dentro de la ventana", () => {
    const res = attributeLastTouch(pago(1, "2025-06-10"), [
      toque(1, "SMS", "2025-06-05"),
      toque(1, "IVR", "2025-06-09"),
    ]);
    expect(res.canal).toBe("IVR");
  });
});

describe("modelo primario · empate el mismo día → Llamada > IVR > SMS", () => {
  it("Llamada gana a IVR y SMS el mismo día", () => {
    const res = attributeLastTouch(pago(1, "2025-06-10"), [
      toque(1, "SMS", "2025-06-09"),
      toque(1, "IVR", "2025-06-09"),
      toque(1, "Llamada", "2025-06-09"),
    ]);
    expect(res.canal).toBe("Llamada");
  });
  it("IVR gana a SMS el mismo día", () => {
    const res = attributeLastTouch(pago(1, "2025-06-10"), [
      toque(1, "SMS", "2025-06-09"),
      toque(1, "IVR", "2025-06-09"),
    ]);
    expect(res.canal).toBe("IVR");
  });
  it("un toque más reciente de menor prioridad gana igual (recencia manda entre días)", () => {
    const res = attributeLastTouch(pago(1, "2025-06-10"), [
      toque(1, "Llamada", "2025-06-08"),
      toque(1, "SMS", "2025-06-09"),
    ]);
    expect(res.canal).toBe("SMS");
  });
});

describe("modelo secundario · influencia (any-touch)", () => {
  it("suma puede exceder 100% cuando una dama recibe varios canales", () => {
    const payments = [pago(1, "2025-06-10", 1000)];
    const touches = [
      toque(1, "Llamada", "2025-05-01"),
      toque(1, "SMS", "2025-05-02"),
      toque(1, "IVR", "2025-05-03"),
    ];
    const { canales, total } = influenceModel(payments, touches);
    expect(total).toBe(1000);
    const suma = canales.reduce((s, c) => s + c.pct, 0);
    expect(suma).toBeCloseTo(3.0); // 300%
    for (const c of canales) expect(c.pct).toBeCloseTo(1.0);
  });
  it("ignora toques no efectivos", () => {
    const { canales } = influenceModel(
      [pago(1, "2025-06-10", 1000)],
      [toque(1, "Llamada", "2025-05-01", false)],
    );
    expect(canales.find((c) => c.canal === "Llamada")!.monto).toBe(0);
  });
});

describe("sesgo temporal", () => {
  it("marca pagos posteriores a la fecha de corte de canal", () => {
    const payments = [
      pago(1, "2025-06-28", 100),
      pago(2, "2025-07-05", 300), // fuera de ventana (corte 30/06)
    ];
    const s = sesgoTemporal(payments, "2025-06-30");
    expect(s.montoFueraDeVentana).toBe(300);
    expect(s.montoTotal).toBe(400);
    expect(s.pagosFueraDeVentana).toBe(1);
    expect(s.pctFueraDeVentana).toBeCloseTo(0.75);
  });
  it("attributeAll fuerza espontáneo por construcción fuera de ventana", () => {
    // Pago posterior al corte: aunque hubiera un toque, no debe existir toque
    // futuro; marcamos fueraDeVentana=true para la alerta metodológica.
    const res = attributeAll(
      [pago(1, "2025-07-05", 300)],
      [toque(1, "Llamada", "2025-06-30")], // a 5 días, dentro de ventana de 7
      "2025-06-30",
    );
    expect(res[0].fueraDeVentana).toBe(true);
  });
});

describe("eficiencia por toque", () => {
  it("divide monto atribuido entre toques efectivos del canal", () => {
    const atribs = attributeAll(
      [pago(1, "2025-06-10", 300)],
      [toque(1, "Llamada", "2025-06-09"), toque(2, "Llamada", "2025-06-01")],
      "2025-06-30",
    );
    const ef = eficienciaPorToque(atribs, [
      toque(1, "Llamada", "2025-06-09"),
      toque(2, "Llamada", "2025-06-01"),
    ]);
    expect(ef.Llamada).toBe(150); // 300 / 2 toques
  });
});

describe("estados de liquidación", () => {
  it("R y E son ambos liquidación", () => {
    expect(esLiquidacion("R")).toBe(true);
    expect(esLiquidacion("E")).toBe(true);
    expect(esLiquidacion("X")).toBe(false);
  });
});

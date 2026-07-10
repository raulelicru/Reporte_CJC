import { describe, it, expect } from "vitest";
import {
  clasificarEquipo,
  emparejarMentores,
  mediana,
  percentil,
  GestorClasificado,
  GestorInput,
  UMBRAL_CUMPLIMIENTO_DEBIL,
} from "./gestores";

const g = (
  agenteId: string,
  gestiones: number,
  contactosEfectivos: number,
  pdp: number,
  pdpCumplidas: number,
  recuperadoAtribuido = 0,
): GestorInput => ({
  agenteId,
  nombre: agenteId,
  gestiones,
  contactosEfectivos,
  pdp,
  pdpCumplidas,
  recuperadoAtribuido,
});

describe("estadística de apoyo", () => {
  it("mediana impar y par", () => {
    expect(mediana([1, 2, 3])).toBe(2);
    expect(mediana([1, 2, 3, 4])).toBe(2.5);
    expect(mediana([])).toBe(0);
  });
  it("percentil ubica al valor en el equipo", () => {
    expect(percentil(3, [1, 2, 3, 4])).toBeCloseTo(0.625);
  });
});

describe("clasificación por cuadrante (§6)", () => {
  // Equipo de 4: contacto medianas y cumplimiento medianas fabricadas a mano.
  // tasaContacto = contactos/gestiones ; cumplimiento = cumplidas/pdp
  const equipo = [
    g("A", 100, 80, 20, 16), // contacto 0.80 alto, cumpl 0.80 alto  → MENTOR
    g("B", 100, 75, 20, 4), //  contacto 0.75 alto, cumpl 0.20 bajo  → COACHING
    g("C", 100, 30, 20, 18), // contacto 0.30 bajo, cumpl 0.90 alto  → SUBIR VOLUMEN
    g("D", 100, 20, 20, 2), //  contacto 0.20 bajo, cumpl 0.10 bajo  → PLAN MEJORA
  ];
  const res = clasificarEquipo(equipo);
  const byId = Object.fromEntries(res.map((r) => [r.agenteId, r]));

  it("MENTOR: contacto alto + cumplimiento alto", () => {
    expect(byId.A.clasificacion).toBe("MENTOR");
  });
  it("COACHING_CIERRE: contacto alto + cumplimiento bajo", () => {
    expect(byId.B.clasificacion).toBe("COACHING_CIERRE");
  });
  it("SUBIR_VOLUMEN: contacto bajo + cumplimiento alto", () => {
    expect(byId.C.clasificacion).toBe("SUBIR_VOLUMEN");
  });
  it("PLAN_MEJORA: contacto bajo + cumplimiento bajo", () => {
    expect(byId.D.clasificacion).toBe("PLAN_MEJORA");
  });

  it("cada PLAN_MEJORA recibe un mentor sugerido (§6)", () => {
    expect(byId.D.mentorSugerido).toBe("A");
  });

  it("marca cumplimiento débil por debajo de ~32% sin implicar despido", () => {
    expect(byId.B.cumplimientoDebil).toBe(true); // 0.20 < 0.32
    expect(byId.A.cumplimientoDebil).toBe(false); // 0.80
    expect(UMBRAL_CUMPLIMIENTO_DEBIL).toBeCloseTo(0.32);
  });

  it("umbrales son relativos a la mediana del equipo, no fijos", () => {
    // Si todos suben, la mediana sube y el cuadrante se recalcula.
    const equipoFuerte = [
      g("A", 100, 95, 20, 19),
      g("B", 100, 94, 20, 18),
      g("C", 100, 60, 20, 10),
      g("D", 100, 55, 20, 9),
    ];
    const r = clasificarEquipo(equipoFuerte);
    const map = Object.fromEntries(r.map((x) => [x.agenteId, x]));
    // C tiene 0.60 de contacto (alto en términos absolutos) pero bajo vs equipo.
    expect(map.C.contactoAlto).toBe(false);
  });

  it("sin mentores en el equipo, PLAN_MEJORA queda sin sugerencia (no revienta)", () => {
    // Se prueba emparejarMentores directo: una lista con PLAN_MEJORA y sin MENTOR.
    const base: Omit<GestorClasificado, "clasificacion" | "agenteId" | "nombre"> = {
      gestiones: 0,
      contactosEfectivos: 0,
      pdp: 0,
      pdpCumplidas: 0,
      recuperadoAtribuido: 0,
      tasaContacto: 0,
      pctCumplimiento: 0,
      rendimiento: 0,
      contactoAlto: false,
      cumplimientoAlto: false,
      cumplimientoDebil: true,
      percentilContacto: 0,
      percentilCumplimiento: 0,
      mentorSugerido: null,
    };
    const lista: GestorClasificado[] = [
      { ...base, agenteId: "X", nombre: "X", clasificacion: "PLAN_MEJORA" },
      { ...base, agenteId: "Y", nombre: "Y", clasificacion: "COACHING_CIERRE" },
    ];
    const r = emparejarMentores(lista);
    expect(r.find((x) => x.agenteId === "X")!.mentorSugerido).toBeNull();
  });
});

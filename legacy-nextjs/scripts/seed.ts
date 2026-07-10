/**
 * Seed / demostración end-to-end.
 *
 * El prompt adjuntaba 6 .xlsx reales en /data/seed. Si esos archivos existen
 * los usa; si no, GENERA una campaña sintética (dos, para poder ver la vista
 * comparativa) con los mismos shapes de §3, así el motor se puede correr y
 * revisar sin datos reales.
 *
 * Corre el pipeline + métricas e imprime el perfilado (tasas de cruce, flags,
 * costo del marcador, mezcla de canal). Si hay credenciales de Supabase en el
 * entorno, además persiste las campañas.
 *
 * Uso:  npm run seed
 */
import * as fs from "node:fs";
import * as path from "node:path";
import * as XLSX from "xlsx";
import { buildIngest, RawFiles } from "../src/lib/ingest/pipeline";
import { readSheet } from "../src/lib/ingest/parse";
import { computeMetrics } from "../src/lib/metrics/compute";

const SEED_DIR = path.join(process.cwd(), "data", "seed");
const FILE_MAP: Record<keyof RawFiles, RegExp> = {
  cartera: /cartera/i,
  pagos: /pago/i,
  gestiones: /gestion/i,
  vicidial: /vicidial/i,
  ivr: /reminder|ivr/i,
  sms: /sms/i,
};

const AGENTES = ["María Pérez", "Juan Gómez", "Ana Ruiz", "Luis Torres", "Sofía Díaz"];
const TEMPS = ["Mora 1", "Mora 2", "Mora 3", "MNI", "IM"];

/** PRNG determinístico (sin Math.random para reproducibilidad). */
function makeRng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

function synthCampaign(anio: string, seed: number): RawFiles {
  const rng = makeRng(seed);
  const N = 60; // consultoras
  const baseDay = 1; // liberación 2025-06-01
  const cartera: any[] = [];
  const pagos: any[] = [];
  const gestiones: any[] = [];
  const vicidial: any[] = [];
  const ivr: any[] = [];
  const sms: any[] = [];

  for (let i = 0; i < N; i++) {
    const numDama = 100000 + i + seed * 1000;
    const dama = `${numDama}-${anio}`;
    const saldo = Math.round(500 + rng() * 4500);
    const temp = TEMPS[Math.floor(rng() * TEMPS.length)];
    cartera.push({
      FechaEntrega: 20250601,
      NumDama: numDama,
      AnioCampaniaSaldo: anio,
      SaldoCobro: saldo,
      NumeroZonaFacturacion: `Z${(i % 5) + 1}`,
      Ruta: `R${(i % 9) + 1}`,
      "Dama-deuda": dama,
    });

    // ¿fue contactada? ~70%
    const contactada = rng() < 0.7;
    const agente = AGENTES[Math.floor(rng() * AGENTES.length)];
    let ultimoContactoDia: number | null = null;

    if (contactada) {
      const dia = baseDay + Math.floor(rng() * 25); // dentro de junio
      ultimoContactoDia = dia;
      const esContacto = rng() < 0.55;
      const fecha = `2025-06-${String(dia).padStart(2, "0")} 10:15:00`;
      const promesa = esContacto && rng() < 0.6
        ? `${String(dia + 2).padStart(2, "0")}/06/2025`
        : null;
      gestiones.push({
        FECHA: fecha,
        "NOMBRE GESTOR": agente,
        CODIGO: numDama,
        zona: `Z${(i % 5) + 1}`,
        ruta: `R${(i % 9) + 1}`,
        temp,
        "TIPO DE GESTION": esContacto ? "CONTACTO" : "NO CONTACTO",
        TELEFONO: "55" + Math.floor(rng() * 1e8),
        Estatus: "OK",
        TIPIFICACIlON: esContacto ? "PROMESA DE PAGO" : "NO CONTESTA",
        COMENTARIO: "",
        "DIA PROM": "",
        MEDICION: "",
        PROMESA: promesa,
      });
      // Vicidial: fila del agente (misma llamada) + a veces autodialer.
      vicidial.push({
        call_date: fecha,
        phone_number_dialed: numDama,
        status: esContacto ? "SALE" : "NA",
        user: "u" + (AGENTES.indexOf(agente) + 1),
        full_name: agente,
        campaign_id: anio,
        length_in_sec: Math.floor(rng() * 180),
        status_name: esContacto ? "Contacto" : "No contesta",
      });
    }

    // IVR ~50%
    if (rng() < 0.5) {
      const dia = baseDay + Math.floor(rng() * 25);
      const status = rng() < 0.4 ? "Contacto" : "No contesta";
      if (status === "Contacto") ultimoContactoDia = Math.max(ultimoContactoDia ?? 0, dia);
      ivr.push({
        Nodama: numDama,
        Saldo: saldo,
        Temp: temp,
        "Ola / Intento": 1,
        "Estado de la Llamada": status,
        "Fecha de la Llamada": `${String(dia).padStart(2, "0")}/06/2025 09:00`,
        "Estado Final": status,
        "Respuesta DTMF": rng() < 0.3 ? "1" : "",
        Status: status,
      });
    }

    // SMS ~60%
    if (rng() < 0.6) {
      const dia = baseDay + Math.floor(rng() * 25);
      const ok = rng() < 0.9;
      if (ok) ultimoContactoDia = Math.max(ultimoContactoDia ?? 0, dia);
      sms.push({
        Proyecto: "Arabela",
        "Fecha Base": "2025-06-01",
        Telefono: "55" + Math.floor(rng() * 1e8),
        Dama: numDama,
        "Fecha Envio": `2025-06-${String(dia).padStart(2, "0")} 08:00:00`,
        Costo: 0.25,
        "Mensajes Enviados": 1,
        Descripcion: ok ? "Exitoso" : "Fallido",
        Operador: "Telcel",
      });
    }

    // Pago ~45%: unos dentro de ventana, otros fuera (julio) para sesgo temporal.
    if (rng() < 0.45) {
      const fueraVentana = rng() < 0.2;
      const payDay = fueraVentana
        ? `202507${String(1 + Math.floor(rng() * 6)).padStart(2, "0")}`
        : ultimoContactoDia
          ? `202506${String(Math.min(30, ultimoContactoDia + Math.floor(rng() * 5))).padStart(2, "0")}`
          : `202506${String(10 + Math.floor(rng() * 18)).padStart(2, "0")}`;
      const liquidado = rng() < 0.6;
      pagos.push({
        IdCobrador: "C" + (1 + Math.floor(rng() * 4)),
        FechaEntrega: Number(payDay),
        NumDama: numDama,
        AnioCampaniaSaldo: anio,
        SaldoCampania: liquidado ? 0 : Math.round(saldo * (0.3 + rng() * 0.4)),
        EstadoProceso: rng() < 0.5 ? "R" : "E",
        "Dama-deuda": dama,
      });
    }
  }

  // Marcador automático (C3): muchas llamadas, 0 contactos efectivos.
  for (let k = 0; k < 300; k++) {
    vicidial.push({
      call_date: `2025-06-${String(1 + (k % 25)).padStart(2, "0")} 11:00:00`,
      phone_number_dialed: 100000 + (k % N),
      status: "NA",
      user: "VDAD",
      full_name: "Outbound Auto Dial",
      campaign_id: anio,
      length_in_sec: Math.floor(rng() * 20),
      status_name: "No contesta",
    });
  }

  // Pagos de una campaña anterior (C11) que deben filtrarse (§3).
  pagos.push({
    IdCobrador: "C1", FechaEntrega: 20250115, NumDama: 999999,
    AnioCampaniaSaldo: "2025C11", SaldoCampania: 0, EstadoProceso: "R",
    "Dama-deuda": `999999-2025C11`,
  });

  return { cartera, pagos, gestiones, vicidial, ivr, sms };
}

function writeXlsx(dir: string, name: string, rows: any[]) {
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "data");
  XLSX.writeFile(wb, path.join(dir, name));
}

/** Si /data/seed trae los 6 .xlsx reales, léelos a RawFiles. Si falta alguno, null. */
function loadRealSeed(): RawFiles | null {
  if (!fs.existsSync(SEED_DIR)) return null;
  const files = fs.readdirSync(SEED_DIR).filter((f) => f.endsWith(".xlsx"));
  const found: Partial<Record<keyof RawFiles, string>> = {};
  for (const [key, re] of Object.entries(FILE_MAP)) {
    // Ignora los .xlsx sintéticos que este mismo script escribe.
    const hit = files.find((f) => re.test(f) && !/^(Cartera|Pagos|Gestiones|Vicidial|Ivr|Sms)_2025C1[23]\.xlsx$/i.test(f));
    if (hit) found[key as keyof RawFiles] = path.join(SEED_DIR, hit);
  }
  const keys = Object.keys(FILE_MAP) as (keyof RawFiles)[];
  if (keys.every((k) => found[k])) {
    console.log("→ Usando archivos reales de /data/seed");
    return {
      cartera: readSheet(fs.readFileSync(found.cartera!)),
      pagos: readSheet(fs.readFileSync(found.pagos!)),
      gestiones: readSheet(fs.readFileSync(found.gestiones!)),
      vicidial: readSheet(fs.readFileSync(found.vicidial!)),
      ivr: readSheet(fs.readFileSync(found.ivr!)),
      sms: readSheet(fs.readFileSync(found.sms!)),
    };
  }
  return null;
}

function report(label: string, files: RawFiles) {
  console.log(`\n══════════ ${label} ══════════`);
  const ing = buildIngest(files);
  const m = computeMetrics(ing);
  console.log("Filas:", ing.profile.filas);
  console.log("Tasas de cruce:", {
    gestionesEnCartera: ing.profile.cruces.gestionesEnCartera.toFixed(2),
    ivrEnCartera: ing.profile.cruces.ivrEnCartera.toFixed(2),
    smsEnCartera: ing.profile.cruces.smsEnCartera.toFixed(2),
  });
  console.log("Corte de datos de canal:", ing.profile.fechaCorteDatos, "| máx pago:", ing.profile.fechaMaxPago);
  console.log("C3 · costo marcador:", ing.profile.costoMarcador);
  console.log("Flags de calidad:");
  for (const f of ing.flags) console.log(`  [${f.severidad}] ${f.tipo}: ${f.detalle}`);
  console.log("Recuperado total:", Math.round(m.resumen.recuperado));
  console.log("Mezcla por canal (último toque):");
  for (const c of m.canal)
    console.log(`  ${c.canal.padEnd(11)} ${Math.round(c.montoUltimoToque).toString().padStart(8)}  ${(c.pct * 100).toFixed(1)}%`);
  console.log("% espontáneo:", (m.resumen.pctEspontaneo * 100).toFixed(1) + "%",
    "| % fuera de ventana:", (m.resumen.pctFueraVentana * 100).toFixed(1) + "%",
    "| % cartera no contactada:", (m.resumen.pctCarteraNoContactada * 100).toFixed(1) + "%");
  console.log("Gestores (cuadrante):");
  for (const a of m.agentes)
    console.log(`  ${a.nombre.padEnd(14)} contacto=${(a.tasaContacto * 100).toFixed(0)}%  cumpl=${(a.pctCumplimiento * 100).toFixed(0)}%  ${a.clasificacion}${a.mentorSugerido ? " → mentor:" + a.mentorSugerido : ""}`);
  return ing;
}

async function main() {
  fs.mkdirSync(SEED_DIR, { recursive: true });

  // Si están los 6 archivos reales, perfílalos y persístelos tal cual.
  const real = loadRealSeed();
  if (real) {
    const ing = report("Campaña real (/data/seed)", real);
    if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY) {
      const { createAdminClient } = await import("../src/lib/supabase/admin");
      const { persistCampaign } = await import("../src/lib/metrics/persist");
      const anio = ing.cartera[0]?.damaDeuda.split("-")[1] ?? "REAL";
      const { campaignId } = await persistCampaign(createAdminClient(), {
        orgId: "00000000-0000-0000-0000-000000000001",
        anioCampania: anio, nombre: `Campaña ${anio}`, cargadoPor: null, ingest: ing,
      });
      console.log(`✓ Persistida campaña real ${anio} → ${campaignId}`);
    }
    return;
  }

  // Campaña 12 (madura) y 13 (para comparar).
  const c12 = synthCampaign("2025C12", 12);
  const c13 = synthCampaign("2025C13", 13);

  // Escribir .xlsx para poder probar la carga desde la UI.
  for (const [key, rows] of Object.entries(c12)) {
    writeXlsx(SEED_DIR, `${cap(key)}_2025C12.xlsx`, rows as any[]);
  }
  console.log("→ .xlsx sintéticos escritos en data/seed/ (campaña 2025C12).");

  report("Campaña 2025C12 (sintética)", c12);
  report("Campaña 2025C13 (sintética)", c13);

  // Persistir si hay credenciales.
  if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY) {
    const { createAdminClient } = await import("../src/lib/supabase/admin");
    const { persistCampaign } = await import("../src/lib/metrics/persist");
    const db = createAdminClient();
    const orgId = "00000000-0000-0000-0000-000000000001";
    for (const [anio, files] of [["2025C12", c12], ["2025C13", c13]] as const) {
      const ing = buildIngest(files);
      const { campaignId } = await persistCampaign(db, {
        orgId, anioCampania: anio, nombre: `Campaña ${anio}`, cargadoPor: null, ingest: ing,
      });
      console.log(`✓ Persistida ${anio} → ${campaignId}`);
    }
  } else {
    console.log("\n(Supabase no configurado: no se persistió. Rellena .env.local para persistir.)");
  }
}

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

"use client";

import { useMemo, useState } from "react";
import { pct, money, num } from "@/lib/format";
import { ETIQUETA_CLASIFICACION } from "@/lib/classify/gestores";

export interface AgenteVM {
  agente_id: string;
  nombre: string | null;
  gestiones: number;
  contactos_efectivos: number;
  tasa_contacto: number;
  pdp: number;
  pdp_cumplidas: number;
  pct_cumplimiento: number;
  recuperado_atribuido: number;
  clasificacion: keyof typeof ETIQUETA_CLASIFICACION;
  mentor_nombre: string | null;
}

type HistPunto = { anio: string; contacto: number; cumplimiento: number; clasificacion: string };
type Historia = Record<string, { display: string; puntos: HistPunto[] }>;

const CHIP: Record<string, string> = {
  MENTOR: "chip-mentor",
  COACHING_CIERRE: "chip-coaching",
  SUBIR_VOLUMEN: "chip-volumen",
  PLAN_MEJORA: "chip-plan",
};
const COLOR: Record<string, string> = {
  MENTOR: "#12A99A",
  COACHING_CIERRE: "#B77E17",
  SUBIR_VOLUMEN: "#2b5c9a",
  PLAN_MEJORA: "#D6486A",
};

type SortKey = keyof Pick<
  AgenteVM,
  "nombre" | "gestiones" | "tasa_contacto" | "pct_cumplimiento" | "recuperado_atribuido"
>;

export function GestoresView({
  agentes,
  historia,
}: {
  agentes: AgenteVM[];
  historia: Historia;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("recuperado_atribuido");
  const [asc, setAsc] = useState(false);
  const [sel, setSel] = useState<string | null>(agentes[0]?.agente_id ?? null);

  const rows = useMemo(() => {
    const r = [...agentes];
    r.sort((a, b) => {
      const va = a[sortKey] ?? 0;
      const vb = b[sortKey] ?? 0;
      const cmp = typeof va === "string" ? String(va).localeCompare(String(vb)) : Number(va) - Number(vb);
      return asc ? cmp : -cmp;
    });
    return r;
  }, [agentes, sortKey, asc]);

  const seleccionado = agentes.find((a) => a.agente_id === sel) ?? null;
  const histSel = seleccionado?.nombre
    ? Object.values(historia).find((h) => h.display === seleccionado.nombre)
    : undefined;

  function th(key: SortKey, label: string) {
    return (
      <th
        onClick={() => (key === sortKey ? setAsc(!asc) : (setSortKey(key), setAsc(false)))}
      >
        {label} {sortKey === key ? (asc ? "▲" : "▼") : ""}
      </th>
    );
  }

  return (
    <div className="space-y-8">
      {/* Cuadrante */}
      <div className="panel p-5">
        <div className="eyebrow mb-2">Cuadrante · contacto vs. cumplimiento (mediana del equipo)</div>
        <Quadrant agentes={agentes} sel={sel} onSelect={setSel} />
      </div>

      {/* Tabla de mando */}
      <div className="panel p-2 overflow-x-auto">
        <table className="mando">
          <thead>
            <tr>
              {th("nombre", "Gestor")}
              {th("gestiones", "Gestiones")}
              {th("tasa_contacto", "Contacto")}
              {th("pct_cumplimiento", "Cumplimiento")}
              {th("recuperado_atribuido", "Recuperado")}
              <th>Clasificación</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr
                key={a.agente_id}
                onClick={() => setSel(a.agente_id)}
                style={{ cursor: "pointer", background: a.agente_id === sel ? "#f6f4ee" : undefined }}
              >
                <td>{a.nombre ?? a.agente_id.slice(0, 8)}</td>
                <td className="num">{num(a.gestiones)}</td>
                <td className="num">{pct(a.tasa_contacto)}</td>
                <td className="num">
                  <span className={Number(a.pct_cumplimiento) < 0.32 ? "text-rose" : ""}>
                    {pct(a.pct_cumplimiento)}
                  </span>
                </td>
                <td className="num">{money(a.recuperado_atribuido)}</td>
                <td>
                  <span className={`chip ${CHIP[a.clasificacion]}`}>
                    {a.clasificacion.replace("_", " ")}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Ficha individual */}
      {seleccionado && (
        <div className="panel p-5">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <div className="eyebrow">Ficha del gestor</div>
              <h3 className="display text-lg font-semibold">
                {seleccionado.nombre ?? seleccionado.agente_id.slice(0, 8)}
              </h3>
            </div>
            <span className={`chip ${CHIP[seleccionado.clasificacion]}`}>
              {ETIQUETA_CLASIFICACION[seleccionado.clasificacion]}
            </span>
          </div>

          <div className="grid sm:grid-cols-4 gap-3 mt-4">
            <Metric label="Gestiones" value={num(seleccionado.gestiones)} />
            <Metric label="Tasa de contacto" value={pct(seleccionado.tasa_contacto)} />
            <Metric label="Cumplimiento PDP" value={pct(seleccionado.pct_cumplimiento)} />
            <Metric label="Recuperado" value={money(seleccionado.recuperado_atribuido)} />
          </div>

          {seleccionado.clasificacion === "PLAN_MEJORA" && (
            <div className="callout warn mt-4">
              <div>
                <div className="font-semibold text-sm">Emparejamiento sugerido</div>
                <div className="text-sm text-ink70 mt-0.5">
                  {seleccionado.mentor_nombre
                    ? <>Acompañar con <b>{seleccionado.mentor_nombre}</b> (mentor con mayor cumplimiento y capacidad). El objetivo es desarrollo de talento: necesita apoyo en cierre, no es un mal gestor.</>
                    : "Aún no hay un mentor identificado en el equipo para esta campaña."}
                </div>
              </div>
            </div>
          )}

          {/* Evolución campaña a campaña */}
          <div className="mt-5">
            <div className="eyebrow mb-2">Evolución campaña a campaña</div>
            {histSel && histSel.puntos.length > 1 ? (
              <Evolucion puntos={histSel.puntos} />
            ) : (
              <p className="text-sm text-ink70">
                Solo hay una campaña para este gestor. Al cargar más campañas se
                verá aquí si mejoró su contacto y su cumplimiento — ese es el punto
                de guardar la historia.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-line rounded-md p-3">
      <div className="eyebrow mb-1">{label}</div>
      <div className="num text-lg font-semibold">{value}</div>
    </div>
  );
}

function Quadrant({
  agentes,
  sel,
  onSelect,
}: {
  agentes: AgenteVM[];
  sel: string | null;
  onSelect: (id: string) => void;
}) {
  const w = 460, h = 320, pad = 34;
  const medC = median(agentes.map((a) => a.tasa_contacto));
  const medK = median(agentes.map((a) => a.pct_cumplimiento));
  const maxC = Math.max(0.001, ...agentes.map((a) => a.tasa_contacto));
  const maxK = Math.max(0.001, ...agentes.map((a) => a.pct_cumplimiento));
  const x = (v: number) => pad + (v / maxC) * (w - pad * 2);
  const y = (v: number) => h - pad - (v / maxK) * (h - pad * 2);

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={w} height={h} role="img">
        <line x1={x(medC)} y1={pad} x2={x(medC)} y2={h - pad} stroke="#E4E8EE" strokeDasharray="4 4" />
        <line x1={pad} y1={y(medK)} x2={w - pad} y2={y(medK)} stroke="#E4E8EE" strokeDasharray="4 4" />
        <text x={w - pad} y={pad - 6} textAnchor="end" fontSize="9" fill="#12A99A">Mentor ↗</text>
        <text x={pad} y={h - pad + 14} fontSize="9" fill="#D6486A">Plan de mejora ↙</text>
        <text x={pad} y={pad - 6} fontSize="9" fill="#2b5c9a">Subir volumen ↖</text>
        <text x={w - pad} y={h - pad + 14} textAnchor="end" fontSize="9" fill="#B77E17">Coaching de cierre ↘</text>
        {agentes.map((a) => (
          <circle
            key={a.agente_id}
            cx={x(a.tasa_contacto)}
            cy={y(a.pct_cumplimiento)}
            r={a.agente_id === sel ? 7 : 5}
            fill={COLOR[a.clasificacion]}
            stroke={a.agente_id === sel ? "#16202E" : "white"}
            strokeWidth={a.agente_id === sel ? 2 : 1}
            style={{ cursor: "pointer" }}
            onClick={() => onSelect(a.agente_id)}
          >
            <title>{a.nombre}</title>
          </circle>
        ))}
        <text x={w / 2} y={h - 4} textAnchor="middle" fontSize="10" fill="#5A6472">Tasa de contacto →</text>
        <text x={12} y={h / 2} fontSize="10" fill="#5A6472" transform={`rotate(-90 12 ${h / 2})`}>Cumplimiento →</text>
      </svg>
    </div>
  );
}

function Evolucion({ puntos }: { puntos: HistPunto[] }) {
  const w = Math.max(360, puntos.length * 120), h = 160, pad = 30;
  const x = (i: number) => pad + (puntos.length === 1 ? 0 : (i / (puntos.length - 1)) * (w - pad * 2));
  const y = (v: number) => h - pad - v * (h - pad * 2);
  const line = (key: "contacto" | "cumplimiento", color: string) =>
    puntos.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(p[key])}`).join(" ");
  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={w} height={h}>
        <path d={line("contacto", "#B77E17")} fill="none" stroke="#B77E17" strokeWidth="2" />
        <path d={line("cumplimiento", "#12A99A")} fill="none" stroke="#12A99A" strokeWidth="2" />
        {puntos.map((p, i) => (
          <text key={i} x={x(i)} y={h - 8} textAnchor="middle" fontSize="10" fill="#5A6472">{p.anio}</text>
        ))}
      </svg>
      <div className="flex gap-3 mt-1">
        <span className="tag"><span className="dot dot-llamada" />Contacto</span>
        <span className="tag"><span className="dot dot-sms" />Cumplimiento</span>
      </div>
    </div>
  );
}

function median(xs: number[]): number {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

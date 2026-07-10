"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import type { CampaignRow } from "@/lib/data/queries";
import { diasEntre } from "@/lib/format";

/**
 * Selector de campaña siempre visible (§8), con badge de madurez (días desde
 * liberación) y de completitud de datos. Resuelve la campaña activa desde el
 * param `c` (client-side), así el layout no necesita searchParams.
 */
export function CampaignSelector({ campaigns }: { campaigns: CampaignRow[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const c = params.get("c");
  const actual = campaigns.find((x) => x.id === c) ?? campaigns[0] ?? null;

  if (!actual) {
    return <div className="text-sm text-ink70">No hay campañas cargadas todavía.</div>;
  }

  const madurez = diasEntre(actual.fecha_liberacion, actual.fecha_corte_datos);
  const madura = madurez !== null && madurez >= 30;

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const sp = new URLSearchParams(params.toString());
    sp.set("c", e.target.value);
    router.push(`${pathname}?${sp.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <select
        value={actual.id}
        onChange={onChange}
        className="num border border-line rounded-md px-3 py-1.5 text-sm bg-white"
      >
        {campaigns.map((c) => (
          <option key={c.id} value={c.id}>
            {c.anio_campania} · {c.nombre}
          </option>
        ))}
      </select>

      <span
        className="chip"
        title="Días desde liberación hasta el corte de datos"
        style={
          madura
            ? { background: "#eafaf4", color: "#0c7a6f", borderColor: "#b8e6da" }
            : { background: "#fdf8ee", color: "#9a6a12", borderColor: "#ecd9b0" }
        }
      >
        madurez {madurez ?? "?"}d {madura ? "· madura" : "· recién liberada"}
      </span>

      {!madura && (
        <span className="text-xs text-ink70">
          Comparar contra campañas maduras puede leerse mal.
        </span>
      )}
    </div>
  );
}

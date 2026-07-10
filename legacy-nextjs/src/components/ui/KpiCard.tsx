import { delta as calcDelta } from "@/lib/format";

export function KpiCard({
  label,
  value,
  sub,
  actual,
  previo,
  invertColor = false,
}: {
  label: string;
  value: string;
  sub?: string;
  /** Para delta vs. campaña anterior. */
  actual?: number;
  previo?: number | null;
  /** true si "subir" es malo (ej. % espontáneo). */
  invertColor?: boolean;
}) {
  const d =
    actual !== undefined ? calcDelta(actual, previo) : null;
  const good =
    d && (d.signo === "up" ? !invertColor : d.signo === "down" ? invertColor : null);
  const color =
    good === null ? "text-ink70" : good ? "text-teal" : "text-rose";

  return (
    <div className="panel p-4">
      <div className="eyebrow mb-2">{label}</div>
      <div className="num text-2xl font-semibold">{value}</div>
      <div className="flex items-center gap-2 mt-1">
        {sub && <span className="text-xs text-ink70">{sub}</span>}
        {d && (
          <span className={`num text-xs font-medium ${color}`}>
            {d.signo === "up" ? "▲" : d.signo === "down" ? "▼" : ""} {d.texto}
            <span className="text-ink70 font-normal"> vs. anterior</span>
          </span>
        )}
      </div>
    </div>
  );
}

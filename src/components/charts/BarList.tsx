/** Lista de barras CSS (bar-row/bar-track/bar-fill) — motor propio, §9. */
export interface BarItem {
  label: string;
  value: number;
  /** clase de relleno, ej. 'fill-llamada' */
  fill?: string;
  /** texto a la derecha (ya formateado) */
  right: string;
}

export function BarList({ items, max }: { items: BarItem[]; max?: number }) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <div>
      {items.map((it, i) => (
        <div className="bar-row" key={i}>
          <div className="text-sm text-ink70 truncate">{it.label}</div>
          <div className="bar-track">
            <div
              className={`bar-fill ${it.fill ?? "fill-espontaneo"}`}
              style={{ width: `${Math.max(1.5, (it.value / top) * 100)}%` }}
            />
          </div>
          <div className="num text-sm font-medium text-right whitespace-nowrap">
            {it.right}
          </div>
        </div>
      ))}
    </div>
  );
}

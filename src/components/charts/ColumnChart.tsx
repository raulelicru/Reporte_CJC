/**
 * Gráfica de columnas por día en SVG inline (motor propio, §9).
 * Marca blasts de SMS y el tramo fuera de ventana con distinto trazo.
 */
export interface Column {
  label: string;
  value: number;
  highlight?: boolean; // blast
  muted?: boolean; // fuera de ventana
}

export function ColumnChart({
  data,
  height = 220,
  format = (n) => String(n),
}: {
  data: Column[];
  height?: number;
  format?: (n: number) => string;
}) {
  if (data.length === 0)
    return <div className="text-sm text-ink70">Sin datos.</div>;

  const w = Math.max(560, data.length * 26);
  const pad = { t: 12, r: 8, b: 40, l: 8 };
  const max = Math.max(1, ...data.map((d) => d.value));
  const innerH = height - pad.t - pad.b;
  const bw = (w - pad.l - pad.r) / data.length;

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={w} height={height} role="img">
        {data.map((d, i) => {
          const h = (d.value / max) * innerH;
          const x = pad.l + i * bw;
          const y = pad.t + innerH - h;
          const color = d.highlight ? "#12A99A" : d.muted ? "#c9cfd8" : "#B77E17";
          return (
            <g key={i}>
              <rect
                x={x + 2}
                y={y}
                width={Math.max(2, bw - 4)}
                height={h}
                fill={color}
                rx={2}
                opacity={d.muted ? 0.6 : 1}
              />
              {i % Math.ceil(data.length / 12) === 0 && (
                <text
                  x={x + bw / 2}
                  y={height - 22}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#5A6472"
                  transform={`rotate(-40 ${x + bw / 2} ${height - 22})`}
                >
                  {d.label.slice(5)}
                </text>
              )}
            </g>
          );
        })}
        <text x={pad.l} y={height - 6} fontSize="10" fill="#8A94A3">
          máx {format(max)}
        </text>
      </svg>
    </div>
  );
}

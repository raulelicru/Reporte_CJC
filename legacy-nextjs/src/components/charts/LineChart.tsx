/**
 * Gráfica de líneas multi-serie en SVG inline (motor propio, §9).
 * Usada en la vista comparativa entre campañas.
 */
export interface Serie {
  nombre: string;
  color: string;
  puntos: number[];
}

export function LineChart({
  labels,
  series,
  height = 240,
  format = (n) => String(n),
}: {
  labels: string[];
  series: Serie[];
  height?: number;
  format?: (n: number) => string;
}) {
  if (labels.length === 0)
    return <div className="text-sm text-ink70">Sin campañas para comparar.</div>;

  const w = Math.max(520, labels.length * 120);
  const pad = { t: 16, r: 16, b: 34, l: 48 };
  const innerW = w - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const all = series.flatMap((s) => s.puntos);
  const max = Math.max(1, ...all);
  const min = Math.min(0, ...all);
  const x = (i: number) =>
    pad.l + (labels.length === 1 ? innerW / 2 : (i / (labels.length - 1)) * innerW);
  const y = (v: number) => pad.t + innerH - ((v - min) / (max - min || 1)) * innerH;

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={w} height={height} role="img">
        {/* rejilla horizontal */}
        {[0, 0.5, 1].map((f, i) => {
          const val = min + (max - min) * f;
          const yy = y(val);
          return (
            <g key={i}>
              <line x1={pad.l} y1={yy} x2={w - pad.r} y2={yy} stroke="#E4E8EE" strokeWidth="1" />
              <text x={4} y={yy + 3} fontSize="9" fill="#8A94A3">
                {format(val)}
              </text>
            </g>
          );
        })}
        {/* series */}
        {series.map((s, si) => {
          const d = s.puntos
            .map((v, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(v)}`)
            .join(" ");
          return (
            <g key={si}>
              <path d={d} fill="none" stroke={s.color} strokeWidth="2" />
              {s.puntos.map((v, i) => (
                <circle key={i} cx={x(i)} cy={y(v)} r="3" fill={s.color} />
              ))}
            </g>
          );
        })}
        {/* etiquetas x */}
        {labels.map((l, i) => (
          <text key={i} x={x(i)} y={height - 12} textAnchor="middle" fontSize="10" fill="#5A6472">
            {l}
          </text>
        ))}
      </svg>
      <div className="flex flex-wrap gap-3 mt-2">
        {series.map((s, i) => (
          <span key={i} className="tag">
            <span className="dot" style={{ background: s.color }} />
            {s.nombre}
          </span>
        ))}
      </div>
    </div>
  );
}

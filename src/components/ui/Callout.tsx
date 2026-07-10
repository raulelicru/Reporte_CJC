import { ReactNode } from "react";

/** Callout con ícono SVG para hallazgos críticos (§9). */
export function Callout({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warn" | "crit";
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className={`callout ${tone}`}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="shrink-0 mt-0.5">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" opacity="0.5" />
        <path d="M12 8v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="12" cy="16.2" r="1" fill="currentColor" />
      </svg>
      <div>
        <div className="font-semibold text-sm">{title}</div>
        <div className="text-sm text-ink70 mt-0.5">{children}</div>
      </div>
    </div>
  );
}

/** Etiqueta metodológica recurrente: "correlación, no causa" (C4). */
export function CorrelacionNota() {
  return (
    <span className="chip" style={{ background: "#f4f2ec", color: "#5a6472" }}>
      correlación, no causa
    </span>
  );
}

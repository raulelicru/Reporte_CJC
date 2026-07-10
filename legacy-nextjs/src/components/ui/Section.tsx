import { ReactNode } from "react";

export function Section({
  eyebrow,
  title,
  desc,
  children,
  right,
}: {
  eyebrow?: string;
  title: string;
  desc?: ReactNode;
  right?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="mb-8">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
          <h2 className="display text-xl font-semibold">{title}</h2>
          {desc && <p className="text-sm text-ink70 mt-1 max-w-2xl">{desc}</p>}
        </div>
        {right && <div className="no-print">{right}</div>}
      </div>
      {children}
    </section>
  );
}

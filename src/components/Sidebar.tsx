"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

const NAV: { href: string; label: string; adminOnly?: boolean }[] = [
  { href: "/", label: "Resumen ejecutivo" },
  { href: "/canales", label: "Recuperación por canal" },
  { href: "/promesas", label: "Promesas de pago" },
  { href: "/secuencias", label: "Secuencias" },
  { href: "/gestionado", label: "Gestionado vs. espontáneo" },
  { href: "/gestores", label: "Gestores" },
  { href: "/temporalidad", label: "Temporalidad" },
  { href: "/tendencia", label: "Tendencia diaria" },
  { href: "/comparativa", label: "Comparativa entre campañas" },
  { href: "/carga", label: "Carga de datos", adminOnly: true },
  { href: "/metodologia", label: "Metodología" },
];

export function Sidebar({ rol }: { rol?: string | null }) {
  const path = usePathname();
  const params = useSearchParams();
  const c = params.get("c");
  const withC = (href: string) => (c ? `${href}?c=${c}` : href);

  return (
    <aside className="sidebar w-60 shrink-0 border-r border-line bg-panel min-h-screen p-4 flex flex-col">
      <div className="mb-6">
        <div className="display text-lg font-semibold">Arabela</div>
        <div className="eyebrow">Inteligencia de Cobranza</div>
      </div>
      <nav className="flex flex-col gap-0.5 text-sm">
        {NAV.filter((n) => !n.adminOnly || rol === "admin").map((n) => {
          const active = path === n.href;
          return (
            <Link
              key={n.href}
              href={withC(n.href)}
              className={`px-3 py-2 rounded-md transition-colors ${
                active ? "bg-[#f1efe8] font-medium text-ink" : "text-ink70 hover:bg-[#faf9f5]"
              }`}
            >
              {n.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto pt-4 text-xs text-ink70">
        <div className="mb-2">Rol: {rol ?? "—"}</div>
        <form action="/auth/signout" method="post">
          <button className="text-rose hover:underline" type="submit">
            Cerrar sesión
          </button>
        </form>
      </div>
    </aside>
  );
}

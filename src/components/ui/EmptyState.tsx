import Link from "next/link";

export function EmptyState({
  title = "Sin campaña seleccionada",
  hint,
}: {
  title?: string;
  hint?: string;
}) {
  return (
    <div className="panel p-10 text-center">
      <div className="display text-lg font-semibold mb-1">{title}</div>
      <p className="text-sm text-ink70 max-w-md mx-auto">
        {hint ??
          "Carga una campaña desde Carga de datos (rol admin) o selecciona una existente arriba. Ninguna cifra se muestra sin métricas calculadas y persistidas."}
      </p>
      <Link
        href="/carga"
        className="inline-block mt-4 text-sm text-teal hover:underline"
      >
        Ir a Carga de datos →
      </Link>
    </div>
  );
}

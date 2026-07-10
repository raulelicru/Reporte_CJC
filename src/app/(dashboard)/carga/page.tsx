import { getProfile } from "@/lib/data/queries";
import { EmptyState } from "@/components/ui/EmptyState";
import { CargaForm } from "@/components/carga/CargaForm";

export default async function CargaPage() {
  const profile = await getProfile();
  if (profile && profile.rol !== "admin")
    return (
      <EmptyState
        title="Acceso restringido"
        hint="Solo el rol admin puede cargar campañas. Pide a un administrador que suba los archivos."
      />
    );

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <div className="eyebrow">Solo admin</div>
        <h1 className="display text-2xl font-semibold">Carga de datos</h1>
        <p className="text-sm text-ink70 mt-1">
          Sube los 6 archivos de la campaña. Primero verás el perfilado y los
          flags de calidad; nada se persiste hasta que confirmas.
        </p>
      </div>
      <CargaForm />
    </div>
  );
}

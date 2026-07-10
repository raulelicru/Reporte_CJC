import { pageContext } from "@/lib/data/context";
import { getAgentes, getHistoriaGestores } from "@/lib/data/queries";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { GestoresView } from "@/components/gestores/GestoresView";

export default async function GestoresPage({
  searchParams,
}: {
  searchParams: { c?: string };
}) {
  const { actual } = await pageContext(searchParams);
  if (!actual) return <EmptyState />;
  const [agentes, historia] = await Promise.all([
    getAgentes(actual.id),
    getHistoriaGestores(),
  ]);
  if (agentes.length === 0) return <EmptyState title="Sin gestores en esta campaña" />;

  return (
    <div>
      <Section
        eyebrow="Desarrollo de talento"
        title="Gestores — quién puede capacitar y quién necesita apoyo"
        desc="Tres dimensiones con umbrales relativos a la mediana del equipo en esta campaña: alcance (contacto), calidad de negociación (cumplimiento de PDP) y rendimiento (recuperado por gestión). El lenguaje es de coaching, nunca de despido."
      />
      <GestoresView agentes={agentes as any} historia={historia} />
    </div>
  );
}

import { pageContext } from "@/lib/data/context";
import { getSecuencias } from "@/lib/data/queries";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { Callout } from "@/components/ui/Callout";
import { BarList } from "@/components/charts/BarList";
import { moneyK, num } from "@/lib/format";

export default async function SecuenciasPage({
  searchParams,
}: {
  searchParams: { c?: string };
}) {
  const { actual } = await pageContext(searchParams);
  if (!actual) return <EmptyState />;
  const seqs = await getSecuencias(actual.id);
  if (seqs.length === 0) return <EmptyState title="Sin secuencias" />;

  const items = [...seqs]
    .sort((a: any, b: any) => Number(b.pagos) - Number(a.pagos))
    .map((s: any) => ({
      label: s.cadena,
      value: Number(s.pagos),
      fill: "fill-llamada",
      right: `${num(s.pagos)} pagos · ${moneyK(s.recuperado)}`,
    }));

  return (
    <div>
      <Section
        eyebrow="Antes del pago"
        title="Top cadenas de canal previas al pago"
        desc="Cadenas de contactos efectivos en los 14 días previos al pago, colapsando repeticiones consecutivas del mismo canal."
      >
        <div className="panel p-5">
          <BarList items={items} />
        </div>
      </Section>

      <Callout tone="info" title="No hay orquestación mágica">
        Los toques sueltos ≈ las cadenas por ticket. La recuperación viene sobre
        todo de contactos individuales, no de secuencias multicanal cuidadosamente
        orquestadas. Leer estas cadenas como “embudos” sobreinterpreta el dato.
      </Callout>
    </div>
  );
}

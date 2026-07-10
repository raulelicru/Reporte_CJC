import { pageContext } from "@/lib/data/context";
import { getCanal } from "@/lib/data/queries";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { Callout, CorrelacionNota } from "@/components/ui/Callout";
import { BarList } from "@/components/charts/BarList";
import { ChannelTag, fillClass } from "@/components/ChannelTag";
import { money, moneyK, num, pct } from "@/lib/format";

export default async function CanalesPage({
  searchParams,
}: {
  searchParams: { c?: string };
}) {
  const { actual } = await pageContext(searchParams);
  if (!actual) return <EmptyState />;
  const canales = await getCanal(actual.id);
  if (canales.length === 0) return <EmptyState title="Sin métricas de canal" />;

  const primario = canales
    .map((c: any) => ({
      label: c.canal,
      value: Number(c.monto_ultimo_toque),
      fill: fillClass(c.canal),
      right: `${moneyK(c.monto_ultimo_toque)} · ${pct(c.pct)}`,
    }))
    .sort((a: any, b: any) => b.value - a.value);

  const reales = canales.filter((c: any) => c.canal !== "Espontaneo");
  const sumaInfluencia = reales.reduce((s: number, c: any) => s + Number(c.influencia_pct), 0);

  return (
    <div>
      <Section
        eyebrow="Modelo primario · último toque efectivo"
        title="Recuperación por canal"
        right={<CorrelacionNota />}
        desc="Cada pago se asigna al último canal con contacto efectivo en la ventana de 7 días. Empate el mismo día: Llamada > IVR > SMS."
      >
        <div className="panel p-5">
          <BarList items={primario} />
        </div>
      </Section>

      <Section eyebrow="Apoyo" title="Eficiencia por toque">
        <div className="grid sm:grid-cols-3 gap-3">
          {reales.map((c: any) => (
            <div key={c.canal} className="panel p-4">
              <div className="mb-1"><ChannelTag canal={c.canal} /></div>
              <div className="num text-xl font-semibold">{money(c.eficiencia_por_toque)}</div>
              <div className="text-xs text-ink70">recuperado atribuido ÷ toque efectivo</div>
            </div>
          ))}
        </div>
      </Section>

      <Section
        eyebrow="Modelo secundario · influencia (any-touch)"
        title="Influencia por canal"
        desc="% del monto de consultoras que recibieron ≥1 contacto efectivo de cada canal."
      >
        <Callout tone="warn" title={`La suma da ${pct(sumaInfluencia)} — y está bien`}>
          La influencia se cuenta por canal sin ventana, así que una misma
          consultora suma en varios canales. Por eso el total pasa de 100%. Es una
          vista de alcance, no de atribución exclusiva.
        </Callout>
        <div className="panel p-5 mt-3">
          <BarList
            items={reales.map((c: any) => ({
              label: c.canal,
              value: Number(c.influencia_pct),
              fill: fillClass(c.canal),
              right: `${pct(c.influencia_pct)} · ${num(c.consultoras ?? 0)} consultoras`,
            }))}
            max={Math.max(...reales.map((c: any) => Number(c.influencia_pct)), 1)}
          />
        </div>
      </Section>
    </div>
  );
}

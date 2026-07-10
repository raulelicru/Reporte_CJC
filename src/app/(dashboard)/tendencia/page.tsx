import { pageContext } from "@/lib/data/context";
import { getDiaria } from "@/lib/data/queries";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { CorrelacionNota } from "@/components/ui/Callout";
import { ColumnChart } from "@/components/charts/ColumnChart";
import { moneyK, num } from "@/lib/format";

export default async function TendenciaPage({
  searchParams,
}: {
  searchParams: { c?: string };
}) {
  const { actual } = await pageContext(searchParams);
  if (!actual) return <EmptyState />;
  const dias = await getDiaria(actual.id);
  if (dias.length === 0) return <EmptyState title="Sin serie diaria" />;

  const recuperado = dias.map((d: any) => ({
    label: d.fecha,
    value: Number(d.recuperado),
    muted: d.fuera_ventana,
  }));
  const sms = dias.map((d: any) => ({
    label: d.fecha,
    value: Number(d.sms_enviados),
    highlight: d.es_blast,
  }));

  const blasts = dias.filter((d: any) => d.es_blast).length;
  const fuera = dias.filter((d: any) => d.fuera_ventana).length;

  return (
    <div>
      <Section
        eyebrow="Día a día"
        title="Tendencia diaria de recuperación"
        right={<CorrelacionNota />}
        desc="Barras por día. El tramo en gris es posterior al corte de datos de canal (fuera de ventana): no puede recibir atribución."
      >
        <div className="panel p-5">
          <ColumnChart data={recuperado} format={(n) => moneyK(n)} />
          <div className="text-xs text-ink70 mt-2">
            {fuera > 0 && <>Gris = {num(fuera)} días fuera de ventana. </>}
            Recuperación diaria en pesos.
          </div>
        </div>
      </Section>

      <Section eyebrow="Envíos" title="Blasts de SMS por día">
        <div className="panel p-5">
          <ColumnChart data={sms} format={(n) => num(n)} />
          <div className="text-xs text-ink70 mt-2">
            En teal, {num(blasts)} días marcados como blast (pico &gt; 2.5× la media).
            Que un pico de SMS coincida con recuperación es correlación, no causa —
            sin grupo de control no se aísla el efecto del envío.
          </div>
        </div>
      </Section>
    </div>
  );
}

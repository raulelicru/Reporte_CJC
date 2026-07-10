import { pageContext } from "@/lib/data/context";
import { getCanal, getResumen } from "@/lib/data/queries";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { Callout } from "@/components/ui/Callout";
import { BarList } from "@/components/charts/BarList";
import { money, moneyK, pct } from "@/lib/format";

export default async function GestionadoPage({
  searchParams,
}: {
  searchParams: { c?: string };
}) {
  const { actual } = await pageContext(searchParams);
  if (!actual) return <EmptyState />;
  const [canales, r] = await Promise.all([getCanal(actual.id), getResumen(actual.id)]);
  if (canales.length === 0 || !r) return <EmptyState title="Sin métricas" />;

  const gestionado = canales
    .filter((c: any) => c.canal !== "Espontaneo")
    .reduce((s: number, c: any) => s + Number(c.monto_ultimo_toque), 0);
  const espontaneo = Number(
    canales.find((c: any) => c.canal === "Espontaneo")?.monto_ultimo_toque ?? 0,
  );
  const total = gestionado + espontaneo;

  return (
    <div>
      <Section
        eyebrow="El número incómodo"
        title="Gestionado vs. espontáneo"
        desc="Recuperado atribuible a un contacto efectivo previo (ventana 7 días) frente al que llegó sin toque previo."
      >
        <div className="panel p-5">
          <BarList
            items={[
              {
                label: "Gestionado",
                value: gestionado,
                fill: "fill-llamada",
                right: `${moneyK(gestionado)} · ${pct(total > 0 ? gestionado / total : 0)}`,
              },
              {
                label: "Espontáneo",
                value: espontaneo,
                fill: "fill-espontaneo",
                right: `${moneyK(espontaneo)} · ${pct(total > 0 ? espontaneo / total : 0)}`,
              },
            ]}
          />
        </div>
        <div className="grid sm:grid-cols-2 gap-3 mt-3">
          <div className="panel p-4">
            <div className="eyebrow mb-1">Recuperado gestionado</div>
            <div className="num text-2xl font-semibold">{money(gestionado)}</div>
          </div>
          <div className="panel p-4">
            <div className="eyebrow mb-1">Recuperado espontáneo</div>
            <div className="num text-2xl font-semibold">{money(espontaneo)}</div>
          </div>
        </div>
      </Section>

      <Callout tone="warn" title="Sesgo temporal declarado en pantalla">
        {pct(r.pct_fuera_ventana)} del recuperado ocurrió después del corte de datos
        de canal ({actual.fecha_corte_datos ?? "s/f"}). Ese tramo no puede recibir
        atribución y engrosa el “espontáneo” por construcción, no porque la gestión
        haya fallado. Sin grupo de control no se aísla el efecto del recordatorio.
      </Callout>
    </div>
  );
}

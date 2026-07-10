import { getComparativa } from "@/lib/data/queries";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { Callout } from "@/components/ui/Callout";
import { LineChart } from "@/components/charts/LineChart";
import { moneyK, pct } from "@/lib/format";

export default async function ComparativaPage() {
  const { campaigns, resumenes, canales, cumplimiento } = await getComparativa();
  if (campaigns.length === 0)
    return <EmptyState title="Sin campañas" hint="Carga al menos una campaña. Con dos o más, esta vista muestra la tendencia sin recalcular a mano." />;

  const labels = campaigns.map((c) => c.anio_campania);
  const resById = new Map(resumenes.map((r: any) => [r.campaign_id, r]));

  const recuperado = campaigns.map((c) => Number(resById.get(c.id)?.recuperado ?? 0));
  const espontaneo = campaigns.map((c) => Number(resById.get(c.id)?.pct_espontaneo ?? 0) * 100);
  const cumpl = campaigns.map((c) => Number(cumplimiento[c.id] ?? 0) * 100);

  // Mezcla de canal (%) por campaña.
  const canalPct = (canal: string) =>
    campaigns.map((c) => {
      const row = canales.find((x: any) => x.campaign_id === c.id && x.canal === canal);
      return Number(row?.pct ?? 0) * 100;
    });

  const soloUna = campaigns.length < 2;

  return (
    <div>
      <Section
        eyebrow="La vista que justifica el sistema"
        title="Comparativa entre campañas"
        desc="Campaña sobre campaña: qué se está haciendo bien y qué mal en el tiempo. Ojo con la madurez — comparar una campaña recién liberada contra una madura distorsiona la lectura."
      />

      {soloUna && (
        <Callout tone="info" title="Solo hay una campaña cargada">
          La tendencia aparece al cargar una segunda campaña. El sistema ya guarda
          la serie; no hace falta recalcular nada a mano.
        </Callout>
      )}

      <div className="grid lg:grid-cols-2 gap-4 mt-4">
        <div className="panel p-5">
          <div className="eyebrow mb-2">Recuperado por campaña</div>
          <LineChart
            labels={labels}
            series={[{ nombre: "Recuperado", color: "#12A99A", puntos: recuperado }]}
            format={(n) => moneyK(n)}
          />
        </div>
        <div className="panel p-5">
          <div className="eyebrow mb-2">Cumplimiento promedio vs. % espontáneo</div>
          <LineChart
            labels={labels}
            series={[
              { nombre: "Cumplimiento %", color: "#B77E17", puntos: cumpl },
              { nombre: "% espontáneo", color: "#8A94A3", puntos: espontaneo },
            ]}
            format={(n) => `${n.toFixed(0)}%`}
          />
        </div>
        <div className="panel p-5 lg:col-span-2">
          <div className="eyebrow mb-2">Mezcla de canal (% recuperado, último toque)</div>
          <LineChart
            labels={labels}
            series={[
              { nombre: "Llamada", color: "#B77E17", puntos: canalPct("Llamada") },
              { nombre: "IVR", color: "#D6486A", puntos: canalPct("IVR") },
              { nombre: "SMS", color: "#12A99A", puntos: canalPct("SMS") },
              { nombre: "Espontáneo", color: "#8A94A3", puntos: canalPct("Espontaneo") },
            ]}
            format={(n) => `${n.toFixed(0)}%`}
          />
        </div>
      </div>
    </div>
  );
}

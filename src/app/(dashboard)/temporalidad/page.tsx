import { pageContext } from "@/lib/data/context";
import { getTemporalidad } from "@/lib/data/queries";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { Callout } from "@/components/ui/Callout";
import { moneyK, num, pct } from "@/lib/format";

export default async function TemporalidadPage({
  searchParams,
}: {
  searchParams: { c?: string };
}) {
  const { actual } = await pageContext(searchParams);
  if (!actual) return <EmptyState />;
  const tramos = await getTemporalidad(actual.id);
  if (tramos.length === 0) return <EmptyState title="Sin tramos de morosidad" />;

  const sorted = [...tramos].sort((a: any, b: any) => Number(b.saldo) - Number(a.saldo));
  const maxSaldo = Math.max(...sorted.map((t: any) => Number(t.saldo)), 1);
  // Mayor bolsa con baja recuperación.
  const bolsa = [...sorted]
    .filter((t: any) => Number(t.tasa) < 0.2)
    .sort((a: any, b: any) => Number(b.saldo) - Number(a.saldo))[0];

  return (
    <div>
      <Section
        eyebrow="Tramos de morosidad"
        title="Saldo vs. recuperado por temporalidad"
        desc="El tramo (Mora 1–3, MNI, IM, Inactiva) se mapea por consultora desde gestiones/IVR — no viene en la cartera."
      >
        {bolsa && (
          <Callout tone="crit" title="Mayor bolsa con baja recuperación">
            <b>{bolsa.temp}</b> concentra {moneyK(bolsa.saldo)} de saldo con solo
            {" "}{pct(bolsa.tasa)} recuperado. Es la prioridad de intervención.
          </Callout>
        )}
        <div className="panel p-3 mt-3 overflow-x-auto">
          <table className="mando">
            <thead>
              <tr>
                <th>Tramo</th>
                <th>Deudas</th>
                <th>Saldo</th>
                <th>Recuperado</th>
                <th>Tasa</th>
                <th>Peso</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((t: any) => (
                <tr key={t.temp}>
                  <td>{t.temp}</td>
                  <td className="num">{num(t.deudas)}</td>
                  <td className="num">{moneyK(t.saldo)}</td>
                  <td className="num">{moneyK(t.recuperado)}</td>
                  <td className="num">
                    <span className={Number(t.tasa) < 0.2 ? "text-rose" : "text-teal"}>
                      {pct(t.tasa)}
                    </span>
                  </td>
                  <td style={{ width: 160 }}>
                    <div className="bar-track">
                      <div
                        className="bar-fill fill-ivr"
                        style={{ width: `${(Number(t.saldo) / maxSaldo) * 100}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

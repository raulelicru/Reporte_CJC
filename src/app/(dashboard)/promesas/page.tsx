import { pageContext } from "@/lib/data/context";
import { getAgentes } from "@/lib/data/queries";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { Callout } from "@/components/ui/Callout";
import { KpiCard } from "@/components/ui/KpiCard";
import { money, num, pct } from "@/lib/format";

export default async function PromesasPage({
  searchParams,
}: {
  searchParams: { c?: string };
}) {
  const { actual } = await pageContext(searchParams);
  if (!actual) return <EmptyState />;
  const agentes = await getAgentes(actual.id);
  if (agentes.length === 0) return <EmptyState title="Sin datos de promesas" />;

  const pdp = agentes.reduce((s: number, a: any) => s + Number(a.pdp), 0);
  const cumplidas = agentes.reduce((s: number, a: any) => s + Number(a.pdp_cumplidas), 0);
  const recuperado = agentes.reduce((s: number, a: any) => s + Number(a.recuperado_atribuido), 0);
  const tasa = pdp > 0 ? cumplidas / pdp : 0;

  return (
    <div>
      <Section
        eyebrow="Compromisos de pago"
        title="Promesas de pago (PDP)"
        desc="Cumplida = pago dentro de la fecha prometida + 3 días. El monto prometido es aspiracional, no cobrado."
      >
        <div className="grid sm:grid-cols-3 gap-3">
          <KpiCard label="Promesas registradas" value={num(pdp)} />
          <KpiCard label="Promesas cumplidas" value={num(cumplidas)} />
          <KpiCard label="Tasa de cumplimiento" value={pct(tasa)} />
        </div>
      </Section>

      <Section eyebrow="Brecha" title="Prometido vs. recuperado real">
        <Callout tone="warn" title="El prometido es aspiracional">
          El archivo de gestiones no trae monto prometido por promesa (campo
          ausente en la fuente, §3), así que la brecha se lee en tasa de
          cumplimiento, no en pesos. Se deja el hook para cuando el monto llegue.
          Recuperado atribuido a Llamada en esta campaña: <b>{money(recuperado)}</b>.
        </Callout>
      </Section>

      <Section eyebrow="Detalle por gestor" title="Cumplimiento de promesas">
        <div className="panel p-2 overflow-x-auto">
          <table className="mando">
            <thead>
              <tr>
                <th>Gestor</th>
                <th>PDP</th>
                <th>Cumplidas</th>
                <th>% cumplimiento</th>
              </tr>
            </thead>
            <tbody>
              {[...agentes]
                .sort((a: any, b: any) => Number(b.pct_cumplimiento) - Number(a.pct_cumplimiento))
                .map((a: any) => (
                  <tr key={a.agente_id}>
                    <td>{a.nombre ?? a.agente_id.slice(0, 8)}</td>
                    <td className="num">{num(a.pdp)}</td>
                    <td className="num">{num(a.pdp_cumplidas)}</td>
                    <td className="num">
                      <span className={Number(a.pct_cumplimiento) < 0.32 ? "text-rose" : ""}>
                        {pct(a.pct_cumplimiento)}
                      </span>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-ink70 mt-2">
          En rojo, cumplimiento por debajo de ~32%: compromisos poco firmes ⇒
          coaching de cierre, nunca despido automático.
        </p>
      </Section>
    </div>
  );
}

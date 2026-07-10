import { pageContext } from "@/lib/data/context";
import {
  getResumen,
  getResumenPrevio,
  getCostoMarcador,
  getCanal,
  getCampaigns,
} from "@/lib/data/queries";
import { KpiCard } from "@/components/ui/KpiCard";
import { Callout } from "@/components/ui/Callout";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/ui/EmptyState";
import { money, moneyK, num, pct } from "@/lib/format";

export default async function ResumenPage({
  searchParams,
}: {
  searchParams: { c?: string };
}) {
  const { actual } = await pageContext(searchParams);
  if (!actual) return <EmptyState />;

  const [r, campaigns, costo, canales] = await Promise.all([
    getResumen(actual.id),
    getCampaigns(),
    getCostoMarcador(actual.id),
    getCanal(actual.id),
  ]);
  const previo = await getResumenPrevio(campaigns, actual);
  if (!r) return <EmptyState title="Métricas no calculadas" hint="Vuelve a cargar esta campaña para materializar sus métricas." />;

  return (
    <div>
      <div className="mb-6">
        <div className="eyebrow">Campaña {actual.anio_campania}</div>
        <h1 className="display text-2xl font-semibold">Resumen ejecutivo</h1>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-8">
        <KpiCard
          label="Recuperado"
          value={money(r.recuperado)}
          actual={r.recuperado}
          previo={previo?.recuperado}
        />
        <KpiCard
          label="% del saldo asignado"
          value={pct(r.pct_recuperado)}
          sub={`de ${moneyK(r.saldo_asignado)}`}
          actual={r.pct_recuperado}
          previo={previo?.pct_recuperado}
        />
        <KpiCard
          label="Deudas liquidadas"
          value={num(r.deudas_liquidadas)}
          actual={r.deudas_liquidadas}
          previo={previo?.deudas_liquidadas}
        />
        <KpiCard
          label="Saldo pendiente"
          value={money(r.saldo_pendiente)}
          actual={r.saldo_pendiente}
          previo={previo?.saldo_pendiente}
          invertColor
        />
        <KpiCard
          label="% pagos sin contacto"
          value={pct(r.pct_pagos_sin_contacto)}
          sub="espontáneos"
          actual={r.pct_pagos_sin_contacto}
          previo={previo?.pct_pagos_sin_contacto}
          invertColor
        />
        <KpiCard
          label="% cartera nunca contactada"
          value={pct(r.pct_cartera_no_contactada)}
          actual={r.pct_cartera_no_contactada}
          previo={previo?.pct_cartera_no_contactada}
          invertColor
        />
      </div>

      <Section
        eyebrow="Lo que cambia la lectura"
        title="Tres hallazgos que hay que decir antes que cualquier número"
      >
        <div className="grid md:grid-cols-3 gap-3">
          <Callout tone="crit" title="El marcador automático = 0 contactos">
            {costo
              ? `${num(costo.llamadas)} llamadas y ${num(Math.round(costo.minutos))} min del marcador automático, ${num(costo.contactos_efectivos)} contactos efectivos. Es costo de telefonía, no un canal de recuperación.`
              : "El marcador automático (Outbound Auto Dial) se contabiliza como costo, nunca como recuperación."}
          </Callout>
          <Callout tone="warn" title="Gestiones y Vicidial = un solo canal">
            El marcador conecta la llamada; el CRM captura resultado y promesa.
            Se fusionan en <b>Llamada</b> para no duplicar la recuperación.
          </Callout>
          <Callout tone="warn" title="% de cartera nunca contactada">
            {pct(r.pct_cartera_no_contactada)} de las consultoras no recibió ni un
            contacto efectivo. Ese saldo no tuvo oportunidad de gestión.
          </Callout>
        </div>
      </Section>

      {r.pct_fuera_ventana > 0.01 && (
        <Callout tone="warn" title="Sesgo temporal declarado">
          {pct(r.pct_fuera_ventana)} del recuperado ocurrió después de la última
          fecha con datos de canal ({actual.fecha_corte_datos ?? "s/f"}). Ese tramo
          entra como espontáneo por construcción — es una limitación metodológica,
          no un hallazgo de negocio.
        </Callout>
      )}

      <Section eyebrow="Mezcla" title="Recuperado por canal (último toque efectivo)" >
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {canales.map((c: any) => (
            <div key={c.canal} className="panel p-4">
              <div className="eyebrow mb-1">{c.canal}</div>
              <div className="num text-xl font-semibold">{moneyK(c.monto_ultimo_toque)}</div>
              <div className="text-xs text-ink70 num">{pct(c.pct)} · {num(c.pagos)} pagos</div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

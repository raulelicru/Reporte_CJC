import { Section } from "@/components/ui/Section";

export default function MetodologiaPage() {
  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <div className="eyebrow">Siempre accesible</div>
        <h1 className="display text-2xl font-semibold">Metodología</h1>
        <p className="text-sm text-ink70 mt-1">
          Cómo se lee cada número de esta plataforma. Si algo aquí contradice la
          intuición de “cómo se hace un dashboard”, gana esta página: la lógica de
          atribución se validó sobre 1.5M de registros reales.
        </p>
      </div>

      <Section eyebrow="C1" title="Contacto efectivo ≠ intento">
        <p className="text-sm text-ink70">
          Solo cuenta como toque el que conectó. Gestiones con{" "}
          <code>TIPO DE GESTION = CONTACTO</code>; IVR con <code>Status = Contacto</code>;
          SMS con <code>Descripcion ∈ {"{Exitoso, Enviado}"}</code>. Un marcado que
          no conecta nunca recibe atribución.
        </p>
      </Section>

      <Section eyebrow="C2" title="Gestiones y Vicidial = un solo canal">
        <p className="text-sm text-ink70">
          Los gestores del CRM coinciden por nombre normalizado (minúsculas, sin
          acentos, trim) con los agentes de Vicidial. El marcador conecta la
          llamada; el CRM captura resultado y promesa. Se fusionan en{" "}
          <b>Llamada</b> para no duplicar la recuperación.
        </p>
      </Section>

      <Section eyebrow="C3" title="El marcador automático es costo, no canal">
        <p className="text-sm text-ink70">
          <code>full_name ∈ {"{Outbound Auto Dial, Inbound No Agent}"}</code> se
          contabiliza como costo de telefonía (llamadas, minutos), con cero
          contactos efectivos. Nunca aparece como recuperación.
        </p>
      </Section>

      <Section eyebrow="C4" title="Prohibido inflar causalidad">
        <p className="text-sm text-ink70">
          Un pago sin contacto efectivo previo es <b>Espontáneo</b>, jamás
          atribuible al canal que lo marcó y no conectó. Toda métrica de canal es{" "}
          <b>correlación, no causa</b>: sin grupo de control no se aísla el efecto
          del recordatorio.
        </p>
      </Section>

      <Section eyebrow="Modelo" title="Atribución: último toque efectivo">
        <ul className="text-sm text-ink70 list-disc pl-5 space-y-1">
          <li>Cada pago se asigna al último canal con contacto efectivo en o antes de la fecha de pago.</li>
          <li>Ventana de 7 días. Empate el mismo día: Llamada &gt; IVR &gt; SMS.</li>
          <li>Sin toque en la ventana ⇒ Espontáneo.</li>
          <li>Modelo secundario (influencia any-touch): % del monto de consultoras con ≥1 contacto efectivo de cada canal. Suma más de 100% y se reporta aparte.</li>
        </ul>
      </Section>

      <Section eyebrow="Límite" title="Sesgo temporal">
        <p className="text-sm text-ink70">
          Si los pagos se extienden más allá de la última fecha de datos de canal,
          ese tramo no puede recibir atribución y entra como espontáneo por
          construcción. Se muestra como alerta metodológica, no como hallazgo de
          negocio.
        </p>
      </Section>

      <Section eyebrow="Monto" title="Recuperado">
        <p className="text-sm text-ink70">
          <code>Recuperado = SaldoCobro (cartera) − SaldoCampania (remanente)</code>{" "}
          por <code>Dama-deuda</code>, solo para llaves que cruzan con la cartera
          cargada.
        </p>
      </Section>

      <Section eyebrow="Fuentes" title="Campos no usables / trampas de ingesta">
        <ul className="text-sm text-ink70 list-disc pl-5 space-y-1">
          <li><code>FechaEntrega</code> entero <code>YYYYMMDD</code>, parseado explícito.</li>
          <li>Pagos incluye campañas anteriores (ej. C11): se filtra a la cartera cargada.</li>
          <li><code>EstadoProceso</code> R y E, ambos con remanente 0 = liquidación (catálogo abierto).</li>
          <li>Cartera dedup por <code>Dama-deuda</code> conservando la última <code>FechaEntrega</code>.</li>
          <li><code>MEDICION</code> ~99.97% vacía → inutilizable, no se muestra.</li>
          <li>IVR sin fecha parseable → excluidas de atribución, contadas aparte.</li>
          <li>SMS <code>Dama</code> texto → coacción a int, nulos descartados.</li>
          <li>Encoding roto (<code>Ã³</code>/<code>Ã±</code>) se reporta como flag de calidad.</li>
          <li><b>Camino de Crecimiento</b> (Bronce/Plata/Oro/Diamante) NO existe en las fuentes; hook dejado en el modelo.</li>
        </ul>
      </Section>

      <Section eyebrow="Clasificación" title="Gestores">
        <p className="text-sm text-ink70">
          Umbrales relativos a la mediana del equipo en cada campaña. Cuadrante
          contacto × cumplimiento: Mentor, Coaching de cierre, Subir volumen, Plan
          de mejora. Cumplimiento &lt; ~32% ⇒ coaching, nunca despido automático. A
          cada plan de mejora se le sugiere un mentor. Lenguaje de desarrollo de
          talento.
        </p>
      </Section>
    </div>
  );
}

/** Tag de canal con punto de color (§9). */
const MAP: Record<string, { cls: string; label: string }> = {
  Llamada: { cls: "dot-llamada", label: "Llamada" },
  IVR: { cls: "dot-ivr", label: "IVR" },
  SMS: { cls: "dot-sms", label: "SMS" },
  Espontaneo: { cls: "dot-espontaneo", label: "Espontáneo" },
};

export function ChannelTag({ canal }: { canal: string }) {
  const m = MAP[canal] ?? { cls: "dot-espontaneo", label: canal };
  return (
    <span className="tag">
      <span className={`dot ${m.cls}`} />
      {m.label}
    </span>
  );
}

export function fillClass(canal: string): string {
  return (
    {
      Llamada: "fill-llamada",
      IVR: "fill-ivr",
      SMS: "fill-sms",
      Espontaneo: "fill-espontaneo",
    }[canal] ?? "fill-espontaneo"
  );
}

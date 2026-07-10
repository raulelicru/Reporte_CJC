"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { pct, num } from "@/lib/format";

const CAMPOS = [
  { key: "cartera", label: "Cartera_Campaña_*.xlsx" },
  { key: "pagos", label: "Pago_Campaña_*.xlsx" },
  { key: "gestiones", label: "Gestiones_*.xlsx" },
  { key: "vicidial", label: "Base_Vicidial_*.xlsx" },
  { key: "ivr", label: "Base_Reminder_*.xlsx (IVR)" },
  { key: "sms", label: "Base_SMS_*.xlsx" },
];

export function CargaForm() {
  const router = useRouter();
  const [anio, setAnio] = useState("");
  const [nombre, setNombre] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<any>(null);

  function buildForm(commit: boolean, formEl: HTMLFormElement): FormData {
    const fd = new FormData(formEl);
    fd.set("anio", anio);
    fd.set("nombre", nombre);
    fd.set("commit", String(commit));
    return fd;
  }

  async function send(commit: boolean, formEl: HTMLFormElement) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/ingest", { method: "POST", body: buildForm(commit, formEl) });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Error desconocido");
        return;
      }
      if (commit) {
        router.push(`/?c=${json.campaignId}`);
        router.refresh();
      } else {
        setPreview(json);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send(false, e.currentTarget);
      }}
      className="space-y-4"
    >
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="eyebrow block mb-1">AnioCampaniaSaldo</label>
          <input
            required
            value={anio}
            onChange={(e) => setAnio(e.target.value)}
            placeholder="2025C12"
            className="num w-full border border-line rounded-md px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="eyebrow block mb-1">Nombre</label>
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Campaña 12 · 2025"
            className="w-full border border-line rounded-md px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div className="panel p-4 space-y-3">
        {CAMPOS.map((c) => (
          <div key={c.key} className="flex items-center justify-between gap-3">
            <label className="text-sm">{c.label}</label>
            <input
              type="file"
              name={c.key}
              accept=".xlsx"
              required
              className="text-xs"
            />
          </div>
        ))}
      </div>

      {error && <div className="callout crit text-sm">{error}</div>}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy}
          className="border border-line rounded-md px-4 py-2 text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Perfilando…" : "1 · Perfilar (sin guardar)"}
        </button>
        {preview && (
          <button
            type="button"
            disabled={busy}
            onClick={(e) => send(true, e.currentTarget.form!)}
            className="bg-ink text-white rounded-md px-4 py-2 text-sm font-medium disabled:opacity-60"
          >
            {busy ? "Guardando…" : "2 · Confirmar y calcular métricas"}
          </button>
        )}
      </div>

      {preview && <Perfilado data={preview} />}
    </form>
  );
}

function Perfilado({ data }: { data: any }) {
  const p = data.profile;
  const cm = p.costoMarcador;
  return (
    <div className="space-y-4 mt-4">
      <div className="panel p-4">
        <div className="eyebrow mb-2">Filas por archivo</div>
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-3 text-sm">
          {Object.entries(p.filas).map(([k, v]) => (
            <div key={k}>
              <div className="text-ink70">{k}</div>
              <div className="num font-semibold">{num(v as number)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel p-4">
        <div className="eyebrow mb-2">Tasas de cruce</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <Cross label="Gestiones en cartera" v={p.cruces.gestionesEnCartera} />
          <Cross label="IVR en cartera" v={p.cruces.ivrEnCartera} />
          <Cross label="SMS en cartera" v={p.cruces.smsEnCartera} />
          <div>
            <div className="text-ink70">Corte de datos</div>
            <div className="num font-semibold">{p.fechaCorteDatos ?? "s/f"}</div>
          </div>
        </div>
      </div>

      <div className="callout crit">
        <div>
          <div className="font-semibold text-sm">C3 · Marcador automático (costo, no canal)</div>
          <div className="text-sm text-ink70 num">
            {num(cm.llamadas)} llamadas · {num(Math.round(cm.minutos))} min ·{" "}
            {num(cm.contactosEfectivos)} contactos efectivos
          </div>
        </div>
      </div>

      {p.agentesSoloCRM?.length + p.agentesSoloVicidial?.length > 0 && (
        <div className="callout warn text-sm">
          C2 · Nombres solo en CRM: {p.agentesSoloCRM.length}; solo en Vicidial:{" "}
          {p.agentesSoloVicidial.length}. Revisar el match antes de confiar en la
          atribución por gestor.
        </div>
      )}

      <div className="panel p-4">
        <div className="eyebrow mb-2">Flags de calidad ({data.flags.length})</div>
        <ul className="space-y-1 text-sm">
          {data.flags.map((f: any, i: number) => (
            <li key={i} className="flex gap-2">
              <span
                className="chip"
                style={{
                  background:
                    f.severidad === "error" ? "#fdf1f4" : f.severidad === "warn" ? "#fdf8ee" : "#f4f2ec",
                }}
              >
                {f.severidad}
              </span>
              <span className="text-ink70">{f.detalle}</span>
            </li>
          ))}
          {data.flags.length === 0 && <li className="text-ink70">Sin flags.</li>}
        </ul>
      </div>
    </div>
  );
}

function Cross({ label, v }: { label: string; v: number }) {
  return (
    <div>
      <div className="text-ink70">{label}</div>
      <div className={`num font-semibold ${v < 0.5 ? "text-rose" : ""}`}>{pct(v)}</div>
    </div>
  );
}

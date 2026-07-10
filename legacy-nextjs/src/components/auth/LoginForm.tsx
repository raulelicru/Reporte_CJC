"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

/** Formulario de login (cliente). Envuelto en Suspense por useSearchParams. */
export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const redirect = params.get("redirect") || "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.push(redirect);
    router.refresh();
  }

  async function onGoogle() {
    const supabase = createClient();
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="display text-2xl font-semibold">Arabela</div>
          <div className="eyebrow mt-1">Inteligencia de Cobranza</div>
        </div>
        <form onSubmit={onSubmit} className="panel p-6 space-y-4">
          <div>
            <label className="eyebrow block mb-1">Correo</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-line rounded-md px-3 py-2 text-sm"
              placeholder="tu@correo.com"
            />
          </div>
          <div>
            <label className="eyebrow block mb-1">Contraseña</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-line rounded-md px-3 py-2 text-sm"
            />
          </div>
          {error && <div className="text-sm text-rose">{error}</div>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-ink text-white rounded-md py-2 text-sm font-medium disabled:opacity-60"
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
          <button
            type="button"
            onClick={onGoogle}
            className="w-full border border-line rounded-md py-2 text-sm font-medium text-ink70 hover:bg-[#faf9f5]"
          >
            Continuar con Google
          </button>
        </form>
        <p className="text-xs text-ink70 text-center mt-4">
          Acceso restringido. Sin sesión no se entra a ninguna vista.
        </p>
      </div>
    </div>
  );
}

# Arabela · Plataforma de Inteligencia de Cobranza (Streamlit)

App **Streamlit + Python** que ingiere los 6 archivos de una campaña de cobranza
Arabela, ejecuta un **motor de atribución con controles antifraude**, persiste en
**Neon (Postgres)** para **comparar campaña contra campaña** y guardar un
**snapshot por día**, y **clasifica a cada gestor** en un cuadrante de desarrollo
de talento. Protegida con login propio por rol (contraseña con hash bcrypt).

La audiencia son gerentes y supervisores de cobranza: leen números, no código.

> **Modo demo:** sin base configurada, entra en *modo demo* desde el login y
> explora toda la app con campañas sintéticas (varios snapshots diarios), misma
> lógica que la producción.

---

## Cómo correr en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -q                        # 42 tests (motor de atribución + clasificación + smoke UI)
python scripts/seed.py           # perfila una campaña de ejemplo (persiste si hay credenciales)
streamlit run streamlit_app.py   # http://localhost:8501
```

En el login pulsa **“Entrar en modo demo”** para ver el dashboard sin backend.

---

## Conectar Neon (Postgres)

1. Crea un proyecto en [neon.tech](https://neon.tech).
2. **Aplica el esquema**: abre `db/schema.sql`, cópialo y pégalo en el
   **SQL Editor** de Neon → **Run** (crea tablas, tabla `usuarios` para el login
   y la organización por defecto; es idempotente).
3. Copia la **cadena de conexión** de Neon (Dashboard → *Connect* → *Connection
   string*, preferentemente la **pooled** con `?sslmode=require`).
4. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` (o pégalo
   en Streamlit Cloud → *Manage app → Settings → Secrets*) con una sola llave:

| Secret | Uso |
|---|---|
| `DATABASE_URL` | cadena de conexión de Neon (usada por lecturas, ingesta y login) |

   (`scripts/seed.py` lee la misma llave desde `.env` / variables de entorno.)
5. **Primer administrador:** al entrar por primera vez con la base vacía, la
   pantalla de login muestra el alta del **primer admin** (correo + contraseña).
   No hace falta SQL manual. Usuarios adicionales se dan de alta con
   `cobranza.db.create_user(...)` o insertando en `usuarios`.

`DATABASE_URL` solo se usa del lado servidor (`cobranza/db.py`); Streamlit corre
en servidor, nunca se expone al navegador.

---

## Arquitectura

```
streamlit_app.py        entrada: auth-gate + navegación (§8) + selector de campaña
app_pages/              11 páginas (§8), cada una con render()
cobranza/
  attribution.py        MOTOR PURO — C1–C4, último toque, influencia, sesgo temporal
  normalize.py          normalización de nombres (C2) + marcador (C3)
  predicates.py         contacto efectivo por fuente (C1)
  classify.py           cuadrante de gestores + emparejamiento mentor↔aprendiz (§6)
  ingest.py             parseo de los 6 xlsx (pandas) + trampas §3 + perfilado + flags
  metrics.py            métricas derivadas (§5) desde el motor
  db.py                 Supabase: auth, lecturas RLS, persistencia idempotente
  demo.py               generador sintético + store en memoria (modo demo)
  charts.py             motor de gráficas propio: barras HTML/CSS + SVG inline
  theme.py / format.py / ui.py   identidad §9 + helpers de render
supabase/migrations/    esquema + RLS + bootstrap (compartido, §5)
scripts/seed.py         demostración end-to-end / seed
tests/                  pytest: motor, clasificación y smoke de cada página
legacy-nextjs/          versión previa Next.js/React (preservada, no activa)
```

---

## El motor de atribución (el corazón) — testeado con pytest

`cobranza/attribution.py` + `predicates.py` + `normalize.py`: funciones **puras**.
Los cuatro controles antifraude (§4):

- **C1 · Contacto efectivo ≠ intento** — solo el toque que conectó atribuye
  (gestión `CONTACTO`, IVR `Contacto`, SMS `Exitoso/Enviado`).
- **C2 · Gestiones + Vicidial = un solo canal** — match por nombre normalizado;
  los toques de `Llamada` salen del CRM, Vicidial solo aporta roster y costo. No
  se duplica la recuperación.
- **C3 · El marcador automático es costo, no canal** — `Outbound Auto Dial` /
  `Inbound No Agent` → llamadas y minutos, **0 contactos efectivos**.
- **C4 · Prohibido inflar causalidad** — pago sin contacto efectivo previo =
  **Espontáneo**. Toda métrica de canal es *correlación, no causa*.

**Modelo primario**: último toque efectivo, ventana de 7 días, empate el mismo
día → `Llamada > IVR > SMS`. **Secundario**: influencia any-touch (suma > 100%).
**Sesgo temporal**: pagos posteriores al corte de datos de canal entran como
espontáneo por construcción — alerta metodológica.

```bash
pytest -q   # cubre C1–C4, empates, ventana 7d, sesgo temporal, clasificación y UI
```

---

## Clasificación de gestores (§6)

Umbrales **relativos a la mediana del equipo** en la campaña. Cuadrante contacto
× cumplimiento: 🟢 Mentor · 🟡 Coaching de cierre · 🔵 Subir volumen · 🔴 Plan de
mejora. A cada *plan de mejora* se le sugiere un mentor. Cumplimiento < ~32% ⇒
coaching, nunca despido. La ficha muestra la evolución campaña a campaña.

---

## Criterios de aceptación (§10)

1. **Carga los 6 archivos → Resumen ejecutivo poblado**: *Carga de datos* (admin),
   perfila y confirma.
2. **Marcador automático = 0 contactos, como costo**: callout en Resumen y perfilado.
3. **Gestiones y Vicidial = un solo canal**: probado en `tests/test_attribution.py`.
4. **Cada gestor en su cuadrante + mentor sugerido**: página *Gestores*.
5. **Segunda campaña → vista comparativa**: página *Comparativa*.
6. **Sin sesión no entro a nada**: `streamlit_app.py` corta con el login.

---

## Supuestos (no especificados en el prompt)

- **No se adjuntaron los 6 `.xlsx` reales.** `scripts/seed.py` genera una campaña
  sintética (dos, para la comparativa); si dejas los archivos reales en
  `data/seed/`, los detecta y los usa.
- **`fecha_liberacion`** ≈ mínima `FechaEntrega` de la cartera; **`fecha_corte_datos`**
  = máxima fecha con datos de canal. La madurez es su diferencia.
- **Monto prometido por PDP** no viene en la fuente → la brecha se lee en tasa de
  cumplimiento; hook dejado.
- **Cumplimiento de PDP**: pago dentro de `promesa_fecha + 3 días`.
- **`temp` (tramo)** desde la última gestión conocida por consultora.
- **Blast de SMS** = día con envíos > 2.5× la media del período.
- **`R`/`E`** tratados igual (liquidación) pero guardados por si el negocio los
  distingue.
- **Camino de Crecimiento** (Bronce/Plata/Oro/Diamante) **no existe** en las
  fuentes: hook `cartera.camino_crecimiento` nullable, sin inventar el corte.
- **MXN** como moneda; organización única por defecto (multi-tenant vía `org_id`).

---

## Recomendación — la siguiente métrica de alto valor

**Latencia de gestión (tiempo-a-contacto y tiempo-a-pago por consultora).** Hoy
el modelo sabe *si* hubo contacto efectivo y *a qué canal* atribuir, pero no *qué
tan rápido* se llegó a la consultora desde la liberación, ni cuánto tardó el pago
tras el contacto. Esa latencia es accionable (prioriza la cola de marcado),
causalmente más limpia que la mezcla de canal, y explota la serie de tiempo que
ya persistimos. Es la palanca operativa que hoy no está en el modelo.

# Arabela · Plataforma de Inteligencia de Cobranza

Aplicación web de producción que ingiere los 6 archivos de una campaña de
cobranza Arabela, ejecuta un **motor de atribución con controles antifraude**,
persiste todo en Supabase para **comparar campaña contra campaña**, y **clasifica
a cada gestor** en un cuadrante de desarrollo de talento. Protegida con login y
control de acceso por rol.

La audiencia son gerentes y supervisores de cobranza: leen números, no código.

---

## Stack

- **Next.js 14 (App Router) + TypeScript**
- **Supabase**: Postgres (datos + métricas derivadas), Auth (login), Row Level
  Security, Storage (crudos subidos)
- **Tailwind CSS** + componentes propios; **gráficas en SVG inline y barras CSS**
  (motor de render propio, sin Chart.js/D3)
- **xlsx (SheetJS)** para parseo del lado servidor
- **Vitest** para el motor de atribución

---

## Cómo correr en local

```bash
npm install
cp .env.example .env.local        # rellena las llaves de Supabase (ver abajo)
npm run test                      # motor de atribución (33 tests)
npm run seed                      # perfila y (si hay credenciales) persiste una campaña de ejemplo
npm run dev                       # http://localhost:3000
```

Sin `.env.local`, la app arranca igual y las vistas muestran su estado vacío
(ninguna cifra se inventa). Con credenciales, el login y la persistencia
funcionan.

---

## Conectar Supabase

1. Crea un proyecto en [supabase.com](https://supabase.com).
2. **Aplica las migraciones** de `supabase/migrations/` en orden (SQL Editor o
   `supabase db push`):
   - `0001_schema.sql` — esquema (§5)
   - `0002_rls.sql` — Row Level Security
   - `0003_bootstrap.sql` — organización por defecto + alta automática de perfiles
3. **Crea el bucket de Storage** `raw-campaigns` (privado) para auditoría de los
   `.xlsx` crudos. Si no existe, la ingesta no se bloquea: lo reporta como flag.
4. Copia las llaves a `.env.local`:

| Variable | Dónde | Uso |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Project Settings → API | cliente y servidor |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Project Settings → API | cliente (RLS la protege) |
| `SUPABASE_SERVICE_ROLE_KEY` | Project Settings → API | **solo servidor** — ingesta/recálculo |
| `SUPABASE_STORAGE_BUCKET` | tú lo defines | bucket de crudos (`raw-campaigns`) |

5. Registra un usuario (login → o crea uno en Auth) y **promuévelo a admin** una vez:

```sql
update profiles set rol = 'admin'
where user_id = (select id from auth.users where email = 'tu@correo.com');
```

El service-role key **nunca** llega al cliente: solo lo usa `src/lib/supabase/admin.ts`
en Route Handlers y en el seed.

---

## Migraciones SQL

En `supabase/migrations/`. Modelan la **serie de tiempo por campaña** (§5):
`campaigns`, `cartera`, `pagos`, `toques` (unificado), `agentes`, `gestiones`,
`costo_marcador`, y las tablas derivadas materializadas (`metrics_canal`,
`metrics_agente`, `metrics_temporalidad`, `metrics_diaria`, `metrics_secuencia`,
`metrics_resumen`), más `quality_flags` e `ingest_audit`. **RLS activo en todas**:
un usuario solo ve las campañas de su organización.

---

## El motor de atribución (el corazón)

`src/lib/attribution/` — funciones **puras y testeadas**. Los cuatro controles
antifraude (§4):

- **C1 · Contacto efectivo ≠ intento** (`predicates.ts`): solo el toque que
  conectó cuenta. Gestiones `CONTACTO`, IVR `Contacto`, SMS `Exitoso/Enviado`.
- **C2 · Gestiones + Vicidial = un solo canal** (`normalize.ts`, `pipeline.ts`):
  match por nombre normalizado; los toques de `Llamada` salen del CRM, Vicidial
  solo aporta roster y costo. No se duplica la recuperación.
- **C3 · El marcador automático es costo, no canal** (`isAutoDialer`): `Outbound
  Auto Dial` / `Inbound No Agent` → llamadas y minutos, **0 contactos efectivos**.
- **C4 · Prohibido inflar causalidad** (`engine.ts`): pago sin contacto efectivo
  previo = **Espontáneo**. Toda métrica de canal es *correlación, no causa*.

**Modelo primario**: último toque efectivo, ventana de 7 días, empate el mismo
día → `Llamada > IVR > SMS`. **Modelo secundario**: influencia any-touch (suma
> 100%, declarado en la UI). **Sesgo temporal**: los pagos posteriores al corte
de datos de canal entran como espontáneo por construcción — se muestra como
alerta metodológica.

```bash
npm run test   # cubre C1–C4, empates, ventana de 7 días, sesgo temporal
```

---

## Ingesta idempotente

`src/lib/ingest/` + `POST /api/ingest` (solo admin). Recargar una campaña
**reemplaza** sus filas (no duplica). Maneja como reglas todas las trampas de §3
(fechas `YYYYMMDD` y `dd/mm/YYYY`, dedup de cartera, filtro de campañas
anteriores en pagos, coacción de `Dama` en SMS, IVR sin fecha, encoding roto,
`MEDICION` inutilizable). Antes de confirmar, muestra **perfilado + quality_flags**.

---

## Clasificación de gestores (§6)

`src/lib/classify/gestores.ts`. Umbrales **relativos a la mediana del equipo** en
la campaña. Cuadrante contacto × cumplimiento:

| | Cumplimiento alto | Cumplimiento bajo |
|---|---|---|
| **Contacto alto** | 🟢 Mentor | 🟡 Coaching de cierre |
| **Contacto bajo** | 🔵 Subir volumen | 🔴 Plan de mejora |

A cada *plan de mejora* se le sugiere un mentor. La ficha muestra la evolución
campaña a campaña. Lenguaje de desarrollo de talento, nunca de despido.

---

## Criterios de aceptación (§10) — cómo verificarlos

1. **Carga los 6 archivos → Resumen ejecutivo poblado en <60s**: `/carga` (admin),
   perfila y confirma; te redirige al resumen.
2. **Marcador automático = 0 contactos, como costo**: callout en el Resumen y en
   el perfilado de carga.
3. **Gestiones y Vicidial = un solo canal**: probado en `engine.test.ts`
   (`C2 · … NO se duplican en atribución`).
4. **Cada gestor en su cuadrante + mentor sugerido**: `/gestores`.
5. **Segunda campaña → vista comparativa**: `/comparativa`.
6. **Sin sesión no entro a nada**: `middleware.ts` redirige a `/login`.

---

## Supuestos que tomé (no especificados en el prompt)

- **No se adjuntaron los 6 `.xlsx` reales.** El seed (`scripts/seed.ts`) genera
  una campaña sintética (dos, para la comparativa) con los shapes de §3 y corre
  el pipeline completo, imprimiendo el perfilado. Si dejas los archivos reales en
  `data/seed/`, el seed los detecta y los usa en vez de los sintéticos.
- **`fecha_liberacion`** se aproxima como la **mínima `FechaEntrega`** de la
  cartera (la fecha real de liberación no viene en ninguna fuente); **`fecha_corte_datos`**
  = máxima fecha con datos de canal. La madurez es su diferencia en días.
- **Monto prometido por PDP**: el archivo de gestiones no lo trae, así que la
  brecha prometido↔recuperado se lee en tasa de cumplimiento, no en pesos. Hook
  dejado en `gestiones.monto_prometido`.
- **Cumplimiento de PDP**: pago dentro de `promesa_fecha + 3 días` (§6).
- **`temp` (tramo)**: se toma de la última gestión conocida por consultora (no
  viene en cartera, §2).
- **Blast de SMS**: día con envíos > 2.5× la media del período.
- **Estados `R`/`E`**: se tratan igual (liquidación) pero se guarda la columna
  por si el negocio los distingue después.
- **Camino de Crecimiento** (Bronce/Plata/Oro/Diamante): **no existe** en las
  fuentes; se dejó `cartera.camino_crecimiento` nullable como hook, sin inventar
  el corte.
- **MXN** como moneda de despliegue.
- **Organización única por defecto** (multi-tenant listo vía `org_id`); el trigger
  `handle_new_user` da de alta a cada usuario como `supervisor`.

---

## Estructura

```
src/lib/attribution/   motor puro + tests (C1–C4)
src/lib/classify/      cuadrante de gestores + tests
src/lib/ingest/        parseo de los 6 xlsx + pipeline de unificación
src/lib/metrics/       cálculo y persistencia de métricas derivadas
src/lib/supabase/      clients (server, browser, admin) + RLS helpers
src/lib/data/          capa de lectura RLS-scoped para la UI
src/app/(dashboard)/   11 páginas (§8)
src/components/         componentes propios + motor de gráficas SVG/CSS
supabase/migrations/   esquema + RLS + bootstrap
scripts/seed.ts        demostración end-to-end / seed
```

---

## Recomendación — la siguiente métrica de alto valor

Ver el cierre de este README abajo. **Tiempo-a-contacto y tiempo-a-pago por
consultora** (latencia de gestión): hoy el modelo sabe *si* hubo contacto
efectivo y *a qué canal* atribuir, pero no *qué tan rápido* se llegó a la
consultora desde la liberación, ni cuánto tardó el pago tras el contacto. Esa
latencia es accionable (prioriza la cola de marcado), es causalmente más limpia
que la mezcla de canal, y explota la serie de tiempo que ya persistimos. Es la
palanca operativa que hoy no está en el modelo.

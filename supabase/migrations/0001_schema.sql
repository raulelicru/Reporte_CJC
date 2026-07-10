-- ─────────────────────────────────────────────────────────────────────────
-- ARABELA · Plataforma de Inteligencia de Cobranza
-- Migración 0001 · Esquema base (§5)
--
-- Diseñado para SERIE DE TIEMPO por campaña: el valor del sistema es comparar
-- campaña contra campaña. La llave universal de negocio es `dama_deuda`
-- (NumDama + AnioCampaniaSaldo). Idempotencia: recargar una campaña reemplaza
-- sus filas (upsert / delete+insert por campaign_id), nunca duplica.
-- ─────────────────────────────────────────────────────────────────────────

create extension if not exists "pgcrypto";

-- ── Organizaciones y perfiles (multi-tenant + RBAC) ──────────────────────
create table if not exists organizations (
  id          uuid primary key default gen_random_uuid(),
  nombre      text not null,
  created_at  timestamptz not null default now()
);

-- Rol del usuario. Leído por RLS y por la UI.
do $$ begin
  create type user_rol as enum ('admin', 'gerente', 'supervisor');
exception when duplicate_object then null; end $$;

create table if not exists profiles (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  org_id      uuid not null references organizations(id) on delete restrict,
  rol         user_rol not null default 'supervisor',
  equipo      text,                       -- nombre del equipo que supervisa (rol supervisor)
  nombre      text,
  created_at  timestamptz not null default now()
);

-- ── Campañas (cabecera de cada carga) ────────────────────────────────────
create table if not exists campaigns (
  id                 uuid primary key default gen_random_uuid(),
  org_id             uuid not null references organizations(id) on delete cascade,
  anio_campania      text not null,       -- AnioCampaniaSaldo, ej. '2025C12'
  nombre             text not null,
  fecha_liberacion   date,                -- para calcular madurez
  fecha_corte_datos  date,                -- última fecha con datos de canal
  saldo_asignado     numeric(16,2) not null default 0,
  deudas             integer not null default 0,
  consultoras        integer not null default 0,
  cargado_por        uuid references auth.users(id),
  created_at         timestamptz not null default now(),
  unique (org_id, anio_campania)
);

-- ── Cartera (deuda asignada) ─────────────────────────────────────────────
create table if not exists cartera (
  dama_deuda     text not null,
  campaign_id    uuid not null references campaigns(id) on delete cascade,
  num_dama       bigint not null,
  saldo_cobro    numeric(16,2) not null default 0,
  zona           text,
  ruta           text,
  fecha_entrega  date,
  primary key (campaign_id, dama_deuda)
);
create index if not exists idx_cartera_num_dama on cartera(campaign_id, num_dama);

-- ── Pagos (remanente y recuperado) ───────────────────────────────────────
create table if not exists pagos (
  dama_deuda      text not null,
  campaign_id     uuid not null references campaigns(id) on delete cascade,
  num_dama        bigint not null,
  id_cobrador     text,
  fecha_pago      date,
  saldo_remanente numeric(16,2) not null default 0,
  estado_proceso  text,                   -- R / E (ambos = liquidación); catálogo abierto
  recuperado      numeric(16,2) not null default 0,
  primary key (campaign_id, dama_deuda)
);
create index if not exists idx_pagos_num_dama on pagos(campaign_id, num_dama);
create index if not exists idx_pagos_fecha on pagos(campaign_id, fecha_pago);

-- ── Agentes (unificación CRM ↔ Vicidial por nombre normalizado, C2) ──────
create table if not exists agentes (
  id             uuid primary key default gen_random_uuid(),
  campaign_id    uuid not null references campaigns(id) on delete cascade,
  nombre_norm    text not null,
  nombre_display text not null,
  activo         boolean not null default true,
  -- fuentes donde aparece el nombre: {crm, vicidial}
  fuentes        text[] not null default '{}',
  unique (campaign_id, nombre_norm)
);

-- ── Toques unificados (gestiones + ivr + sms) ────────────────────────────
create table if not exists toques (
  id           bigint generated always as identity primary key,
  campaign_id  uuid not null references campaigns(id) on delete cascade,
  num_dama     bigint not null,
  canal        text not null check (canal in ('Llamada','IVR','SMS')),
  dia          date not null,
  efectivo     boolean not null default false,   -- C1
  meta         jsonb not null default '{}'
);
create index if not exists idx_toques_dama on toques(campaign_id, num_dama);
create index if not exists idx_toques_efectivo on toques(campaign_id, canal, efectivo);

-- ── Gestiones (detalle CRM, para PDP y ficha del gestor) ─────────────────
create table if not exists gestiones (
  id             bigint generated always as identity primary key,
  campaign_id    uuid not null references campaigns(id) on delete cascade,
  agente_id      uuid references agentes(id) on delete set null,
  num_dama       bigint not null,
  fecha          timestamptz,
  tipo_gestion   text,                    -- CONTACTO / NO CONTACTO
  tipificacion   text,
  promesa_fecha  date,
  monto_prometido numeric(16,2),
  temp           text,                    -- tramo de morosidad mapeado
  meta           jsonb not null default '{}'
);
create index if not exists idx_gestiones_agente on gestiones(campaign_id, agente_id);
create index if not exists idx_gestiones_dama on gestiones(campaign_id, num_dama);

-- ── Costo del marcador automático (C3) — nunca recuperación ──────────────
create table if not exists costo_marcador (
  campaign_id         uuid primary key references campaigns(id) on delete cascade,
  llamadas            bigint not null default 0,
  minutos             numeric(16,2) not null default 0,
  contactos_efectivos bigint not null default 0
);

-- ── Tablas derivadas (materializadas al cerrar la ingesta) ───────────────
create table if not exists metrics_canal (
  campaign_id          uuid not null references campaigns(id) on delete cascade,
  canal                text not null,     -- Llamada/IVR/SMS/Espontaneo
  monto_ultimo_toque   numeric(16,2) not null default 0,
  pagos                integer not null default 0,
  consultoras          integer not null default 0,
  pct                  numeric(8,5) not null default 0,
  eficiencia_por_toque numeric(16,4) not null default 0,
  influencia_monto     numeric(16,2) not null default 0,
  influencia_pct       numeric(8,5) not null default 0,
  primary key (campaign_id, canal)
);

do $$ begin
  create type clasificacion_gestor as enum
    ('MENTOR','COACHING_CIERRE','SUBIR_VOLUMEN','PLAN_MEJORA');
exception when duplicate_object then null; end $$;

create table if not exists metrics_agente (
  campaign_id           uuid not null references campaigns(id) on delete cascade,
  agente_id             uuid not null references agentes(id) on delete cascade,
  gestiones             integer not null default 0,
  contactos_efectivos   integer not null default 0,
  tasa_contacto         numeric(8,5) not null default 0,
  pdp                   integer not null default 0,
  pdp_cumplidas         integer not null default 0,
  pct_cumplimiento      numeric(8,5) not null default 0,
  recuperado_atribuido  numeric(16,2) not null default 0,
  pagadoras             integer not null default 0,
  clasificacion         clasificacion_gestor,
  percentil_contacto    numeric(8,5) not null default 0,
  percentil_cumplimiento numeric(8,5) not null default 0,
  mentor_sugerido       uuid references agentes(id) on delete set null,
  primary key (campaign_id, agente_id)
);

create table if not exists metrics_temporalidad (
  campaign_id  uuid not null references campaigns(id) on delete cascade,
  temp         text not null,
  saldo        numeric(16,2) not null default 0,
  recuperado   numeric(16,2) not null default 0,
  tasa         numeric(8,5) not null default 0,
  deudas       integer not null default 0,
  primary key (campaign_id, temp)
);

create table if not exists metrics_diaria (
  campaign_id   uuid not null references campaigns(id) on delete cascade,
  fecha         date not null,
  recuperado    numeric(16,2) not null default 0,
  pagos         integer not null default 0,
  sms_enviados  integer not null default 0,
  es_blast      boolean not null default false,
  fuera_ventana boolean not null default false,
  primary key (campaign_id, fecha)
);

-- Secuencias de canal previas al pago (top cadenas, §8 pág. 4)
create table if not exists metrics_secuencia (
  campaign_id  uuid not null references campaigns(id) on delete cascade,
  cadena       text not null,             -- ej. 'SMS→IVR→Llamada'
  pagos        integer not null default 0,
  recuperado   numeric(16,2) not null default 0,
  primary key (campaign_id, cadena)
);

-- Resumen ejecutivo materializado (KPIs de una campaña)
create table if not exists metrics_resumen (
  campaign_id            uuid primary key references campaigns(id) on delete cascade,
  recuperado             numeric(16,2) not null default 0,
  saldo_asignado         numeric(16,2) not null default 0,
  pct_recuperado         numeric(8,5) not null default 0,
  deudas_liquidadas      integer not null default 0,
  saldo_pendiente        numeric(16,2) not null default 0,
  pct_pagos_sin_contacto numeric(8,5) not null default 0,
  pct_espontaneo         numeric(8,5) not null default 0,
  pct_fuera_ventana      numeric(8,5) not null default 0,
  pct_cartera_no_contactada numeric(8,5) not null default 0,
  computed_at            timestamptz not null default now()
);

-- Flags de calidad de datos (encoding roto, cruces bajos, fechas nulas, …)
create table if not exists quality_flags (
  id           bigint generated always as identity primary key,
  campaign_id  uuid not null references campaigns(id) on delete cascade,
  tipo         text not null,
  detalle      text not null,
  severidad    text not null default 'info' check (severidad in ('info','warn','error'))
);
create index if not exists idx_quality_campaign on quality_flags(campaign_id);

-- ── Auditoría mínima: quién cargó qué campaña y cuándo, con hash del archivo ──
create table if not exists ingest_audit (
  id           bigint generated always as identity primary key,
  campaign_id  uuid references campaigns(id) on delete set null,
  org_id       uuid references organizations(id) on delete cascade,
  user_id      uuid references auth.users(id),
  archivo      text not null,
  sha256       text not null,
  storage_path text,
  filas        integer,
  created_at   timestamptz not null default now()
);

-- Hook para futuro "Camino de Crecimiento" (Bronce/Plata/Oro/Diamante).
-- NO existe en las fuentes actuales (§3). Se deja la columna nullable lista.
alter table cartera add column if not exists camino_crecimiento text;

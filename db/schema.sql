-- ═══════════════════════════════════════════════════════════════════════════
-- ARABELA · Esquema para Neon (Postgres puro)
--
-- Versión sin Auth/RLS de Supabase: el login vive en la tabla `usuarios`
-- (contraseña con hash bcrypt) y el aislamiento por organización se aplica en
-- la capa de app. Pega TODO esto en el SQL Editor de Neon → Run. Idempotente.
-- ═══════════════════════════════════════════════════════════════════════════

create extension if not exists "pgcrypto";

-- ── Roles ──
do $$ begin
  create type user_rol as enum ('admin', 'gerente', 'supervisor');
exception when duplicate_object then null; end $$;

do $$ begin
  create type clasificacion_gestor as enum
    ('MENTOR','COACHING_CIERRE','SUBIR_VOLUMEN','PLAN_MEJORA');
exception when duplicate_object then null; end $$;

-- ── Organizaciones y usuarios (login propio) ──
create table if not exists organizations (
  id          uuid primary key default gen_random_uuid(),
  nombre      text not null,
  created_at  timestamptz not null default now()
);

create table if not exists usuarios (
  id            uuid primary key default gen_random_uuid(),
  email         text unique not null,
  password_hash text not null,
  rol           user_rol not null default 'supervisor',
  org_id        uuid not null references organizations(id) on delete restrict,
  nombre        text,
  equipo        text,
  created_at    timestamptz not null default now()
);

-- ── Campañas (con snapshot diario) ──
create table if not exists campaigns (
  id                 uuid primary key default gen_random_uuid(),
  org_id             uuid not null references organizations(id) on delete cascade,
  anio_campania      text not null,
  nombre             text not null,
  fecha_snapshot     date not null default current_date,
  fecha_liberacion   date,
  fecha_corte_datos  date,
  saldo_asignado     numeric(16,2) not null default 0,
  deudas             integer not null default 0,
  consultoras        integer not null default 0,
  cargado_por        uuid references usuarios(id) on delete set null,
  created_at         timestamptz not null default now(),
  unique (org_id, anio_campania, fecha_snapshot)
);
create index if not exists idx_campaigns_snapshot
  on campaigns (org_id, anio_campania, fecha_snapshot desc);

create table if not exists cartera (
  dama_deuda     text not null,
  campaign_id    uuid not null references campaigns(id) on delete cascade,
  num_dama       bigint not null,
  saldo_cobro    numeric(16,2) not null default 0,
  zona           text,
  ruta           text,
  fecha_entrega  date,
  camino_crecimiento text,
  primary key (campaign_id, dama_deuda)
);
create index if not exists idx_cartera_num_dama on cartera(campaign_id, num_dama);

create table if not exists pagos (
  dama_deuda      text not null,
  campaign_id     uuid not null references campaigns(id) on delete cascade,
  num_dama        bigint not null,
  id_cobrador     text,
  fecha_pago      date,
  saldo_remanente numeric(16,2) not null default 0,
  estado_proceso  text,
  recuperado      numeric(16,2) not null default 0,
  primary key (campaign_id, dama_deuda)
);
create index if not exists idx_pagos_num_dama on pagos(campaign_id, num_dama);
create index if not exists idx_pagos_fecha on pagos(campaign_id, fecha_pago);

create table if not exists agentes (
  id             uuid primary key default gen_random_uuid(),
  campaign_id    uuid not null references campaigns(id) on delete cascade,
  nombre_norm    text not null,
  nombre_display text not null,
  activo         boolean not null default true,
  fuentes        text[] not null default '{}',
  unique (campaign_id, nombre_norm)
);

create table if not exists toques (
  id           bigint generated always as identity primary key,
  campaign_id  uuid not null references campaigns(id) on delete cascade,
  num_dama     bigint not null,
  canal        text not null check (canal in ('Llamada','IVR','SMS')),
  dia          date not null,
  efectivo     boolean not null default false,
  meta         jsonb not null default '{}'
);
create index if not exists idx_toques_dama on toques(campaign_id, num_dama);
create index if not exists idx_toques_efectivo on toques(campaign_id, canal, efectivo);

create table if not exists gestiones (
  id             bigint generated always as identity primary key,
  campaign_id    uuid not null references campaigns(id) on delete cascade,
  agente_id      uuid references agentes(id) on delete set null,
  num_dama       bigint not null,
  fecha          timestamptz,
  tipo_gestion   text,
  tipificacion   text,
  promesa_fecha  date,
  monto_prometido numeric(16,2),
  temp           text,
  meta           jsonb not null default '{}'
);
create index if not exists idx_gestiones_agente on gestiones(campaign_id, agente_id);
create index if not exists idx_gestiones_dama on gestiones(campaign_id, num_dama);

create table if not exists costo_marcador (
  campaign_id         uuid primary key references campaigns(id) on delete cascade,
  llamadas            bigint not null default 0,
  minutos             numeric(16,2) not null default 0,
  contactos_efectivos bigint not null default 0
);

-- ── Métricas derivadas (materializadas por snapshot) ──
create table if not exists metrics_canal (
  campaign_id          uuid not null references campaigns(id) on delete cascade,
  canal                text not null,
  monto_ultimo_toque   numeric(16,2) not null default 0,
  pagos                integer not null default 0,
  consultoras          integer not null default 0,
  pct                  numeric(8,5) not null default 0,
  eficiencia_por_toque numeric(16,4) not null default 0,
  influencia_monto     numeric(16,2) not null default 0,
  influencia_pct       numeric(8,5) not null default 0,
  primary key (campaign_id, canal)
);

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

create table if not exists metrics_secuencia (
  campaign_id  uuid not null references campaigns(id) on delete cascade,
  cadena       text not null,
  pagos        integer not null default 0,
  recuperado   numeric(16,2) not null default 0,
  primary key (campaign_id, cadena)
);

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

create table if not exists quality_flags (
  id           bigint generated always as identity primary key,
  campaign_id  uuid not null references campaigns(id) on delete cascade,
  tipo         text not null,
  detalle      text not null,
  severidad    text not null default 'info' check (severidad in ('info','warn','error'))
);
create index if not exists idx_quality_campaign on quality_flags(campaign_id);

create table if not exists ingest_audit (
  id           bigint generated always as identity primary key,
  campaign_id  uuid references campaigns(id) on delete set null,
  org_id       uuid references organizations(id) on delete cascade,
  user_id      uuid references usuarios(id) on delete set null,
  archivo      text not null,
  sha256       text not null,
  filas        integer,
  created_at   timestamptz not null default now()
);

-- ── Organización por defecto ──
insert into organizations (id, nombre)
values ('00000000-0000-0000-0000-000000000001', 'Arabela · Cobranza')
on conflict (id) do nothing;

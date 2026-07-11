-- ═══════════════════════════════════════════════════════════════════
-- ARABELA · Esquema completo (migraciones 0001–0004 consolidadas)
-- Pega TODO esto en Supabase → SQL Editor → Run, en el proyecto nuevo.
-- Es idempotente: se puede correr de nuevo sin romper nada.
-- ═══════════════════════════════════════════════════════════════════

-- ┌──────────────────────────────────────────────────────────────────
-- │ 0001_schema.sql
-- └──────────────────────────────────────────────────────────────────
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


-- ┌──────────────────────────────────────────────────────────────────
-- │ 0002_rls.sql
-- └──────────────────────────────────────────────────────────────────
-- ─────────────────────────────────────────────────────────────────────────
-- Migración 0002 · Row Level Security (§5, §7)
--
-- Regla base: un usuario solo ve las campañas de SU organización.
--   admin      → carga y ve todo lo de su org.
--   gerente    → ve todo lo de su org, NO carga.
--   supervisor → ve su equipo (filtrado por equipo en la capa de app; RLS
--                garantiza el aislamiento por organización).
--
-- El service-role key (ingesta / recálculo) bypassa RLS por diseño: corre
-- solo en el servidor. Estas políticas gobiernan el acceso del cliente.
-- ─────────────────────────────────────────────────────────────────────────

-- Helpers de identidad del usuario autenticado.
create or replace function auth_org_id() returns uuid
language sql stable security definer set search_path = public as $$
  select org_id from profiles where user_id = auth.uid()
$$;

create or replace function auth_rol() returns user_rol
language sql stable security definer set search_path = public as $$
  select rol from profiles where user_id = auth.uid()
$$;

-- Activa RLS en todas las tablas de datos.
alter table organizations       enable row level security;
alter table profiles            enable row level security;
alter table campaigns           enable row level security;
alter table cartera             enable row level security;
alter table pagos               enable row level security;
alter table agentes             enable row level security;
alter table toques              enable row level security;
alter table gestiones           enable row level security;
alter table costo_marcador      enable row level security;
alter table metrics_canal       enable row level security;
alter table metrics_agente      enable row level security;
alter table metrics_temporalidad enable row level security;
alter table metrics_diaria      enable row level security;
alter table metrics_secuencia   enable row level security;
alter table metrics_resumen     enable row level security;
alter table quality_flags       enable row level security;
alter table ingest_audit        enable row level security;

-- ── organizations ──
drop policy if exists org_select on organizations;
create policy org_select on organizations for select
  using (id = auth_org_id());

-- ── profiles ──
drop policy if exists profiles_self on profiles;
create policy profiles_self on profiles for select
  using (user_id = auth.uid() or org_id = auth_org_id());

-- ── campaigns ──
drop policy if exists campaigns_select on campaigns;
create policy campaigns_select on campaigns for select
  using (org_id = auth_org_id());

drop policy if exists campaigns_insert on campaigns;
create policy campaigns_insert on campaigns for insert
  with check (org_id = auth_org_id() and auth_rol() = 'admin');

drop policy if exists campaigns_update on campaigns;
create policy campaigns_update on campaigns for update
  using (org_id = auth_org_id() and auth_rol() = 'admin');

-- ── Política reutilizable para tablas hijas: visibles si su campaña es de mi org.
-- (Se declara una por tabla porque Postgres no permite políticas parametrizadas.)
do $$
declare t text;
begin
  foreach t in array array[
    'cartera','pagos','agentes','toques','gestiones','costo_marcador',
    'metrics_canal','metrics_agente','metrics_temporalidad','metrics_diaria',
    'metrics_secuencia','metrics_resumen','quality_flags'
  ] loop
    execute format('drop policy if exists %I_select on %I;', t, t);
    execute format($f$
      create policy %I_select on %I for select
      using (exists (
        select 1 from campaigns c
        where c.id = %I.campaign_id and c.org_id = auth_org_id()
      ));
    $f$, t, t, t);
  end loop;
end $$;

-- ── ingest_audit ──
drop policy if exists audit_select on ingest_audit;
create policy audit_select on ingest_audit for select
  using (org_id = auth_org_id());


-- ┌──────────────────────────────────────────────────────────────────
-- │ 0003_bootstrap.sql
-- └──────────────────────────────────────────────────────────────────
-- ─────────────────────────────────────────────────────────────────────────
-- Migración 0003 · Bootstrap (organización por defecto + alta de perfiles)
--
-- Al registrar un usuario en Supabase Auth se crea automáticamente su fila en
-- `profiles`, ligada a la organización por defecto y con rol 'supervisor'.
-- Un admin puede promover roles después. Ajusta el nombre de la organización
-- a tu operación real.
-- ─────────────────────────────────────────────────────────────────────────

insert into organizations (id, nombre)
values ('00000000-0000-0000-0000-000000000001', 'Arabela · Cobranza')
on conflict (id) do nothing;

-- Trigger: cada usuario nuevo obtiene un profile en la org por defecto.
create or replace function handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (user_id, org_id, rol, nombre)
  values (
    new.id,
    '00000000-0000-0000-0000-000000000001',
    'supervisor',
    coalesce(new.raw_user_meta_data->>'nombre', new.email)
  )
  on conflict (user_id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- Para promover al primer admin manualmente (ejecutar una vez con tu email):
--   update profiles set rol = 'admin'
--   where user_id = (select id from auth.users where email = 'tu@correo.com');


-- ┌──────────────────────────────────────────────────────────────────
-- │ 0004_snapshots.sql
-- └──────────────────────────────────────────────────────────────────
-- ─────────────────────────────────────────────────────────────────────────
-- Migración 0004 · Snapshots diarios
--
-- Los 6 archivos se cargan TODOS LOS DÍAS. Cada carga es una foto (snapshot)
-- de la campaña conforme madura. Antes la llave única era (org, anio_campania),
-- así que recargar sobrescribía; ahora se añade `fecha_snapshot` a la llave para
-- que las cargas diarias se ACUMULEN y se pueda revisar la info de días pasados.
--
-- Recargar el MISMO día la misma campaña sigue siendo idempotente (reemplaza esa
-- foto). Cada snapshot es un campaign_id propio, así que todas las tablas de
-- métricas (que cuelgan de campaign_id) ya quedan versionadas por día sin más.
-- ─────────────────────────────────────────────────────────────────────────

alter table campaigns
  add column if not exists fecha_snapshot date not null default current_date;

-- Reemplaza la llave única (org, anio_campania) por (org, anio_campania, fecha_snapshot).
alter table campaigns drop constraint if exists campaigns_org_id_anio_campania_key;
alter table campaigns drop constraint if exists campaigns_org_anio_snapshot_key;
alter table campaigns
  add constraint campaigns_org_anio_snapshot_key
  unique (org_id, anio_campania, fecha_snapshot);

create index if not exists idx_campaigns_snapshot
  on campaigns (org_id, anio_campania, fecha_snapshot desc);



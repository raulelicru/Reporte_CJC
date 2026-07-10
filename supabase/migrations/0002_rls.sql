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

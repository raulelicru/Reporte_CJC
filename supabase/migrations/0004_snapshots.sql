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

-- Migración 0005 · Multi-marca + analítica de estrategia
-- Correr en Neon (SQL Editor) sobre una base que ya tiene db/schema.sql.
-- Idempotente.

alter table campaigns add column if not exists brand text not null default 'arabela';

create table if not exists analytics_estrategia (
  campaign_id  uuid primary key references campaigns(id) on delete cascade,
  payload      jsonb not null default '{}',
  computed_at  timestamptz not null default now()
);

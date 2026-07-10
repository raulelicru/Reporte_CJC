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

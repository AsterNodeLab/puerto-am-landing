-- Puerto A&M | Memoria del chat en Supabase
-- Ejecutar en el SQL Editor del proyecto de Supabase.

create table if not exists public.pa_memoria (
  id bigint generated always as identity primary key,
  cliente_id text not null,
  rol text not null check (rol in ('user', 'asistente')),
  mensaje text not null,
  modo text,
  creado timestamptz not null default now()
);

create index if not exists pa_memoria_cliente_creado_idx
  on public.pa_memoria (cliente_id, creado desc);

create table if not exists public.pa_clientes (
  cliente_id text primary key,
  contexto jsonb not null default '{}'::jsonb,
  actualizado timestamptz not null default now()
);

-- Seguridad: el backend usa la clave service_role, que sortea RLS.
-- NO se crean políticas para anon/public: nadie puede leer las conversaciones
-- desde el navegador ni con la clave publishable.
alter table public.pa_memoria enable row level security;
alter table public.pa_clientes enable row level security;

-- Opcional: si quieres limpiar memoria antigua después de 30 días.
-- create or replace function public.pa_limpiar_memoria() returns void language sql as $$
--   delete from public.pa_memoria where creado < now() - interval '30 days';
-- $$;

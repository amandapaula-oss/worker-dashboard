-- Migration: cria tabelas app_users + app_login_history
-- Como rodar: cole esse SQL no editor do Supabase (SQL Editor) e execute.
-- Idempotente — pode rodar mais de uma vez sem quebrar.

-- ===== Usuarios =====
create table if not exists app_users (
  username             text primary key,
  name                 text not null,
  email                text,
  hashed_password      text not null,
  bus                  text[] not null default '{}',
  is_super_admin       boolean not null default false,
  must_change_password boolean not null default false,
  created_at           timestamptz not null default now(),
  last_login_at        timestamptz
);

-- Colunas opcionais adicionadas em deploys posteriores (idempotente)
alter table app_users add column if not exists email text;
alter table app_users add column if not exists must_change_password boolean not null default false;
alter table app_users add column if not exists visible_cards text[];
-- visible_cards: lista de cards da home aos quais o usuario tem acesso (ex: ['nova_base','bus','budget']).
-- NULL ou vazio = usa default por role (admin ve todos; diretor BU ve so 'bus').

-- ===== Historico de login =====
create table if not exists app_login_history (
  id          bigserial primary key,
  username    text not null,
  login_at    timestamptz not null default now(),
  ip          text,
  user_agent  text,
  success     boolean not null default true
);

create index if not exists app_login_history_username_idx on app_login_history (username);
create index if not exists app_login_history_login_at_idx on app_login_history (login_at desc);

-- ===== Seed dos usuarios atuais (idempotente — nao sobrescreve hash existente) =====
insert into app_users (username, name, hashed_password, bus, is_super_admin)
values
  ('amanda',   'Amanda', '$2b$12$mfHiyBw/auw.B745JxG2eO5Qlw/urUAOOVwi5x2koGXqWhUDhZv/a', '{}', true),
  ('paola',    'Paola',  '$2b$12$RWwqeh1tC5HC9flxYsR3s.a8RyTyCuDcsksRvtnI9K4DbwbKIR5KC', '{}', false),
  ('yuri',     'Yuri',   '$2b$12$lafxeoNomlDKRwz5seUPUe72xx06URZiuxTx2vbhJ6pFVy1HQpuhG', '{}', false),
  ('amisrael', 'Israel', '$2b$12$Uxf53rbxFSof7w.wszVac.HmMOLoK17EfmisNDHc9NaxVHoaCbgO.', '{}', false)
on conflict (username) do nothing;

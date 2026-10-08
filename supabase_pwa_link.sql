-- Profile linking for the PWA. Run in Supabase SQL Editor AFTER supabase_schema.sql and supabase_pwa_migration.sql.

-- PWA-only users have no Telegram account and may have no phone.
alter table public.users alter column telegram_id drop not null;
alter table public.users alter column phone drop not null;

-- One-time codes issued by the Telegram bot (/link). Only the bot (postgres role) writes here.
create table if not exists public.link_codes (
  code varchar(12) primary key,
  user_id integer not null references public.users(id) on delete cascade,
  expires_at timestamp not null,
  used boolean not null default false
);
alter table public.link_codes enable row level security;

-- Link the logged-in Supabase account to an existing bot profile by one-time code.
create or replace function public.link_telegram_account(p_code text)
returns integer
language plpgsql security definer set search_path = public as $$
declare
  v_user integer;
  v_code text := upper(trim(p_code));
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  if exists (select 1 from public.users where auth_id = auth.uid()) then
    raise exception 'account already linked';
  end if;
  select lc.user_id into v_user from public.link_codes lc
   where lc.code = v_code and not lc.used and lc.expires_at > (now() at time zone 'utc')
   for update;
  if v_user is null then raise exception 'invalid or expired code'; end if;
  update public.users set auth_id = auth.uid() where id = v_user and auth_id is null;
  if not found then raise exception 'profile already linked to another account'; end if;
  update public.link_codes set used = true where code = v_code;
  return v_user;
end $$;

-- Create a new profile for a PWA-only user.
create or replace function public.create_pwa_profile(p_name text, p_phone text, p_role userrole)
returns integer
language plpgsql security definer set search_path = public as $$
declare v_id integer;
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  if exists (select 1 from public.users where auth_id = auth.uid()) then
    raise exception 'profile already exists';
  end if;
  if length(trim(coalesce(p_name, ''))) < 2 then raise exception 'name too short'; end if;
  insert into public.users (auth_id, name, phone, role, lang, notifications)
  values (auth.uid(), trim(p_name), nullif(trim(coalesce(p_phone, '')), ''), p_role, 'ru', true)
  returning id into v_id;
  return v_id;
end $$;

-- Join an object by invite code (workers are added as members; foremen only open their own object).
create or replace function public.join_site(p_invite text)
returns integer
language plpgsql security definer set search_path = public as $$
declare
  v_uid integer;
  v_role userrole;
  v_site_id integer;
  v_foreman integer;
begin
  select u.id, u.role into v_uid, v_role from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  select s.id, s.foreman_id into v_site_id, v_foreman from public.sites s where s.invite_code = trim(p_invite);
  if v_site_id is null then raise exception 'site not found'; end if;
  if v_role = 'worker' then
    insert into public.site_members (site_id, worker_id) values (v_site_id, v_uid)
    on conflict (site_id, worker_id) do nothing;
  elsif v_foreman <> v_uid then
    raise exception 'foreman cannot join another foreman site';
  end if;
  return v_site_id;
end $$;

revoke all on function public.link_telegram_account(text) from public, anon;
revoke all on function public.create_pwa_profile(text, text, userrole) from public, anon;
revoke all on function public.join_site(text) from public, anon;
grant execute on function public.link_telegram_account(text) to authenticated;
grant execute on function public.create_pwa_profile(text, text, userrole) to authenticated;
grant execute on function public.join_site(text) to authenticated;

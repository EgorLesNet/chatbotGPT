-- Lifetime free-site quota: deleting a site does NOT give an unsubscribed foreman a new free slot.
-- Run in Supabase SQL Editor after supabase_pwa_tribute.sql.

create table if not exists public.foreman_site_quota (
  user_id integer primary key references public.users(id) on delete cascade,
  created integer not null default 0
);
alter table public.foreman_site_quota enable row level security;

-- Everything a foreman has created so far counts as used.
insert into public.foreman_site_quota (user_id, created)
select s.foreman_id, count(*)
from public.sites s
where s.foreman_id is not null
group by s.foreman_id
on conflict (user_id) do nothing;

-- Without an active subscription a foreman can create sites only while fewer than 3 were EVER created.
-- With an active subscription the limit does not apply. Every created site is counted either way.
create or replace function public.enforce_site_limit()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  v_created integer;
begin
  perform pg_advisory_xact_lock(hashtext('site_quota_' || new.foreman_id::text));

  insert into public.foreman_site_quota (user_id, created)
  values (new.foreman_id, 0)
  on conflict (user_id) do nothing;

  select q.created into v_created
  from public.foreman_site_quota q where q.user_id = new.foreman_id;

  if not exists (
    select 1 from public.foreman_access a
    where a.user_id = new.foreman_id and a.paid_until > (now() at time zone 'utc')
  ) and v_created >= 3 then
    raise exception 'payment required';
  end if;

  update public.foreman_site_quota set created = created + 1 where user_id = new.foreman_id;
  return new;
end $$;

drop trigger if exists trg_sites_limit on public.sites;
create trigger trg_sites_limit before insert on public.sites
  for each row execute function public.enforce_site_limit();

-- 'sites' = free slots used for life (drives the paywall); 'sites_active' = sites that exist now.
create or replace function public.billing_status()
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_uid integer;
  v_active integer;
  v_created integer;
  v_until timestamp;
  v_linked boolean;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  select count(*) into v_active from public.sites s where s.foreman_id = v_uid;
  select coalesce(q.created, 0) into v_created from public.foreman_site_quota q where q.user_id = v_uid;
  v_created := greatest(coalesce(v_created, 0), v_active);
  select a.paid_until into v_until from public.foreman_access a where a.user_id = v_uid;
  select (u.telegram_id is not null) into v_linked from public.users u where u.id = v_uid;
  return jsonb_build_object(
    'sites', v_created,
    'sites_active', v_active,
    'free_limit', 3,
    'price', 500,
    'period_days', 30,
    'paid_until', v_until,
    'telegram_linked', coalesce(v_linked, false),
    'unlocked', coalesce(v_until > (now() at time zone 'utc'), false)
  );
end $$;

notify pgrst, 'reload schema';

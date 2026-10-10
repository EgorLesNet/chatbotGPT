-- Paywall (3 free sites, then 500 RUB), site finance + estimate, read-only client link.
-- Run in Supabase SQL Editor after supabase_pwa_chat.sql.

-- ---------- Paywall ----------
create table if not exists public.foreman_access (
  user_id integer primary key references public.users(id) on delete cascade,
  unlocked_at timestamp not null default (now() at time zone 'utc')
);
alter table public.foreman_access enable row level security;

create table if not exists public.payments (
  id serial primary key,
  user_id integer not null references public.users(id) on delete cascade,
  external_id text not null unique,
  amount numeric(12,2) not null default 500,
  status varchar(12) not null default 'pending',
  created_at timestamp not null default (now() at time zone 'utc'),
  paid_at timestamp
);
alter table public.payments enable row level security;

-- Hard limit for every way of creating a site (PWA and Telegram bot): the 4th site needs payment.
create or replace function public.enforce_site_limit()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  v_count integer;
begin
  if exists (select 1 from public.foreman_access a where a.user_id = new.foreman_id) then
    return new;
  end if;
  select count(*) into v_count from public.sites s where s.foreman_id = new.foreman_id;
  if v_count >= 3 then
    raise exception 'payment required';
  end if;
  return new;
end $$;

drop trigger if exists trg_sites_limit on public.sites;
create trigger trg_sites_limit before insert on public.sites
  for each row execute function public.enforce_site_limit();

create or replace function public.billing_status()
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_uid integer;
  v_n integer;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  select count(*) into v_n from public.sites s where s.foreman_id = v_uid;
  return jsonb_build_object(
    'sites', v_n,
    'free_limit', 3,
    'price', 500,
    'unlocked', exists (select 1 from public.foreman_access a where a.user_id = v_uid)
  );
end $$;

create or replace function public.register_payment(p_external_id text)
returns void
language plpgsql security definer set search_path = public as $$
begin
  insert into public.payments (user_id, external_id)
  select u.id, p_external_id from public.users u where u.auth_id = auth.uid()
  on conflict (external_id) do nothing;
end $$;

create or replace function public.my_pending_payment()
returns text
language sql stable security definer set search_path = public as $$
  select p.external_id
  from public.payments p join public.users u on u.id = p.user_id
  where u.auth_id = auth.uid() and p.status = 'pending'
  order by p.id desc limit 1
$$;

-- Called only by the server with the service role key after the payment was verified at YooKassa.
create or replace function public.confirm_payment(p_external_id text, p_user integer, p_amount numeric)
returns void
language plpgsql security definer set search_path = public as $$
begin
  insert into public.payments (user_id, external_id, amount, status, paid_at)
  values (p_user, p_external_id, p_amount, 'paid', now() at time zone 'utc')
  on conflict (external_id) do update
    set status = 'paid', paid_at = coalesce(public.payments.paid_at, now() at time zone 'utc');
  insert into public.foreman_access (user_id) values (p_user) on conflict do nothing;
end $$;

-- ---------- Finance ----------
create table if not exists public.site_finance (
  id serial primary key,
  site_id integer not null references public.sites(id) on delete cascade,
  kind varchar(10) not null check (kind in ('advance', 'expense', 'salary')),
  amount numeric(12,2) not null check (amount > 0),
  title varchar(200) not null default '',
  worker_id integer references public.users(id) on delete set null,
  happened_on date not null default current_date,
  created_by integer references public.users(id) on delete set null,
  created_at timestamp not null default (now() at time zone 'utc')
);
create index if not exists ix_site_finance_site on public.site_finance (site_id, happened_on desc);
alter table public.site_finance enable row level security;

create table if not exists public.site_estimate_items (
  id serial primary key,
  site_id integer not null references public.sites(id) on delete cascade,
  title varchar(200) not null,
  qty numeric(12,3) not null default 1 check (qty > 0),
  unit varchar(20) not null default '',
  price numeric(12,2) not null default 0 check (price >= 0)
);
create index if not exists ix_site_estimate_site on public.site_estimate_items (site_id);
alter table public.site_estimate_items enable row level security;

create or replace function public.is_site_foreman(p_site integer)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.sites s join public.users u on u.id = s.foreman_id
    where s.id = p_site and u.auth_id = auth.uid()
  )
$$;

create or replace function public.add_finance_entry(
  p_site integer, p_kind text, p_amount numeric, p_title text,
  p_worker integer default null, p_date date default null)
returns integer
language plpgsql security definer set search_path = public as $$
declare
  v_uid integer;
  v_id integer;
  v_title text := trim(coalesce(p_title, ''));
begin
  if not public.is_site_foreman(p_site) then raise exception 'forbidden'; end if;
  select u.id into v_uid from public.users u where u.auth_id = auth.uid();
  if p_kind not in ('advance', 'expense', 'salary') then raise exception 'bad kind'; end if;
  if p_amount is null or p_amount <= 0 or p_amount > 1000000000 then raise exception 'bad amount'; end if;
  if length(v_title) > 200 then raise exception 'value too long'; end if;
  if p_kind = 'salary' then
    if p_worker is null or not exists (
      select 1 from public.site_members m where m.site_id = p_site and m.worker_id = p_worker
    ) then raise exception 'worker not in site'; end if;
  else
    p_worker := null;
    if v_title = '' then raise exception 'title required'; end if;
  end if;
  insert into public.site_finance (site_id, kind, amount, title, worker_id, happened_on, created_by)
  values (p_site, p_kind, p_amount, v_title, p_worker, coalesce(p_date, current_date), v_uid)
  returning id into v_id;
  return v_id;
end $$;

create or replace function public.delete_finance_entry(p_id integer)
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_site integer;
begin
  select f.site_id into v_site from public.site_finance f where f.id = p_id;
  if v_site is null then raise exception 'not found'; end if;
  if not public.is_site_foreman(v_site) then raise exception 'forbidden'; end if;
  delete from public.site_finance where id = p_id;
end $$;

create or replace function public.add_estimate_item(
  p_site integer, p_title text, p_qty numeric, p_unit text, p_price numeric)
returns integer
language plpgsql security definer set search_path = public as $$
declare
  v_id integer;
  v_title text := trim(coalesce(p_title, ''));
begin
  if not public.is_site_foreman(p_site) then raise exception 'forbidden'; end if;
  if length(v_title) < 2 then raise exception 'title required'; end if;
  if length(v_title) > 200 or length(coalesce(p_unit, '')) > 20 then raise exception 'value too long'; end if;
  if p_qty is null or p_qty <= 0 or p_price is null or p_price < 0 or p_qty > 1000000 or p_price > 1000000000 then
    raise exception 'bad amount';
  end if;
  insert into public.site_estimate_items (site_id, title, qty, unit, price)
  values (p_site, v_title, p_qty, trim(coalesce(p_unit, '')), p_price)
  returning id into v_id;
  return v_id;
end $$;

create or replace function public.delete_estimate_item(p_id integer)
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_site integer;
begin
  select e.site_id into v_site from public.site_estimate_items e where e.id = p_id;
  if v_site is null then raise exception 'not found'; end if;
  if not public.is_site_foreman(v_site) then raise exception 'forbidden'; end if;
  delete from public.site_estimate_items where id = p_id;
end $$;

create or replace function public.finance_overview(p_site integer)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
begin
  if not public.is_site_foreman(p_site) then raise exception 'forbidden'; end if;
  return jsonb_build_object(
    'advance', coalesce((select sum(f.amount) from public.site_finance f where f.site_id = p_site and f.kind = 'advance'), 0),
    'expense', coalesce((select sum(f.amount) from public.site_finance f where f.site_id = p_site and f.kind = 'expense'), 0),
    'salary',  coalesce((select sum(f.amount) from public.site_finance f where f.site_id = p_site and f.kind = 'salary'), 0),
    'estimate_total', coalesce((select sum(e.qty * e.price) from public.site_estimate_items e where e.site_id = p_site), 0),
    'entries', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', f.id, 'kind', f.kind, 'amount', f.amount, 'title', f.title,
        'worker', w.name, 'date', f.happened_on) order by f.happened_on desc, f.id desc)
      from public.site_finance f left join public.users w on w.id = f.worker_id
      where f.site_id = p_site), '[]'::jsonb),
    'estimate_items', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', e.id, 'title', e.title, 'qty', e.qty, 'unit', e.unit, 'price', e.price) order by e.id)
      from public.site_estimate_items e where e.site_id = p_site), '[]'::jsonb),
    'workers', coalesce((
      select jsonb_agg(jsonb_build_object('id', u.id, 'name', u.name) order by u.name)
      from public.site_members m join public.users u on u.id = m.worker_id
      where m.site_id = p_site), '[]'::jsonb)
  );
end $$;

-- ---------- Read-only client link ----------
alter table public.sites add column if not exists share_token varchar(32) unique;

create or replace function public.enable_client_link(p_site integer)
returns text
language plpgsql security definer set search_path = public as $$
declare
  v_token text;
begin
  if not public.is_site_foreman(p_site) then raise exception 'forbidden'; end if;
  update public.sites
     set share_token = coalesce(share_token, replace(gen_random_uuid()::text, '-', ''))
   where id = p_site
  returning share_token into v_token;
  return v_token;
end $$;

create or replace function public.disable_client_link(p_site integer)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_site_foreman(p_site) then raise exception 'forbidden'; end if;
  update public.sites set share_token = null where id = p_site;
end $$;

-- Public (anon) read-only view: site name, task titles/statuses and the estimate. No finance, no people, no photos.
create or replace function public.get_client_view(p_token text)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_site public.sites%rowtype;
begin
  if p_token is null or length(p_token) < 20 then return null; end if;
  select * into v_site from public.sites s where s.share_token = p_token;
  if not found then return null; end if;
  return jsonb_build_object(
    'name', v_site.name,
    'address', v_site.address,
    'tasks', coalesce((
      select jsonb_agg(jsonb_build_object('title', t.title, 'status', t.status) order by t.id)
      from public.tasks t where t.site_id = v_site.id), '[]'::jsonb),
    'estimate_items', coalesce((
      select jsonb_agg(jsonb_build_object(
        'title', e.title, 'qty', e.qty, 'unit', e.unit, 'price', e.price) order by e.id)
      from public.site_estimate_items e where e.site_id = v_site.id), '[]'::jsonb),
    'estimate_total', coalesce((
      select sum(e.qty * e.price) from public.site_estimate_items e where e.site_id = v_site.id), 0)
  );
end $$;

-- ---------- Grants ----------
revoke all on function public.billing_status() from public, anon;
revoke all on function public.register_payment(text) from public, anon;
revoke all on function public.my_pending_payment() from public, anon;
revoke all on function public.confirm_payment(text, integer, numeric) from public, anon, authenticated;
revoke all on function public.is_site_foreman(integer) from public, anon;
revoke all on function public.add_finance_entry(integer, text, numeric, text, integer, date) from public, anon;
revoke all on function public.delete_finance_entry(integer) from public, anon;
revoke all on function public.add_estimate_item(integer, text, numeric, text, numeric) from public, anon;
revoke all on function public.delete_estimate_item(integer) from public, anon;
revoke all on function public.finance_overview(integer) from public, anon;
revoke all on function public.enable_client_link(integer) from public, anon;
revoke all on function public.disable_client_link(integer) from public, anon;
revoke all on function public.get_client_view(text) from public;

grant execute on function public.billing_status() to authenticated;
grant execute on function public.register_payment(text) to authenticated;
grant execute on function public.my_pending_payment() to authenticated;
grant execute on function public.confirm_payment(text, integer, numeric) to service_role;
grant execute on function public.is_site_foreman(integer) to authenticated;
grant execute on function public.add_finance_entry(integer, text, numeric, text, integer, date) to authenticated;
grant execute on function public.delete_finance_entry(integer) to authenticated;
grant execute on function public.add_estimate_item(integer, text, numeric, text, numeric) to authenticated;
grant execute on function public.delete_estimate_item(integer) to authenticated;
grant execute on function public.finance_overview(integer) to authenticated;
grant execute on function public.enable_client_link(integer) to authenticated;
grant execute on function public.disable_client_link(integer) to authenticated;
grant execute on function public.get_client_view(text) to anon, authenticated;

notify pgrst, 'reload schema';

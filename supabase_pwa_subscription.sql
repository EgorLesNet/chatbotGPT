-- Switch the paywall from one-time payment to a monthly subscription (500 RUB / 30 days).
-- Run in Supabase SQL Editor after supabase_pwa_business.sql.

alter table public.foreman_access add column if not exists paid_until timestamp;

-- Anyone unlocked under the old one-time model gets one month from the moment they paid.
update public.foreman_access set paid_until = unlocked_at + interval '30 days' where paid_until is null;

-- A site can be created while the foreman has an active subscription or fewer than 3 sites.
create or replace function public.enforce_site_limit()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  v_count integer;
begin
  if exists (
    select 1 from public.foreman_access a
    where a.user_id = new.foreman_id and a.paid_until > (now() at time zone 'utc')
  ) then
    return new;
  end if;
  select count(*) into v_count from public.sites s where s.foreman_id = new.foreman_id;
  if v_count >= 3 then
    raise exception 'payment required';
  end if;
  return new;
end $$;

create or replace function public.billing_status()
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_uid integer;
  v_n integer;
  v_until timestamp;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  select count(*) into v_n from public.sites s where s.foreman_id = v_uid;
  select a.paid_until into v_until from public.foreman_access a where a.user_id = v_uid;
  return jsonb_build_object(
    'sites', v_n,
    'free_limit', 3,
    'price', 500,
    'period_days', 30,
    'paid_until', v_until,
    'unlocked', coalesce(v_until > (now() at time zone 'utc'), false)
  );
end $$;

-- Each paid payment adds 30 days on top of the current end date (or from now if expired). Idempotent per payment.
create or replace function public.confirm_payment(p_external_id text, p_user integer, p_amount numeric)
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_status text;
  v_now timestamp := now() at time zone 'utc';
begin
  perform pg_advisory_xact_lock(hashtext(p_external_id));
  select p.status into v_status from public.payments p where p.external_id = p_external_id;
  if v_status = 'paid' then return; end if;

  insert into public.payments (user_id, external_id, amount, status, paid_at)
  values (p_user, p_external_id, p_amount, 'paid', v_now)
  on conflict (external_id) do update set status = 'paid', paid_at = v_now;

  insert into public.foreman_access (user_id, paid_until)
  values (p_user, v_now + interval '30 days')
  on conflict (user_id) do update
    set paid_until = greatest(coalesce(public.foreman_access.paid_until, v_now), v_now) + interval '30 days';
end $$;

revoke all on function public.confirm_payment(text, integer, numeric) from public, anon, authenticated;
grant execute on function public.confirm_payment(text, integer, numeric) to service_role;

notify pgrst, 'reload schema';

-- Tribute subscription billing. Run after supabase_pwa_subscription.sql.
-- Foreman is matched to a Tribute payer by Telegram ID: users.telegram_id must equal payload.telegram_user_id.

create table if not exists public.tribute_events (
  event_key text primary key,
  name text not null,
  telegram_user_id bigint not null,
  user_id integer,
  expires_at timestamptz,
  payload jsonb,
  created_at timestamptz not null default now()
);
alter table public.tribute_events enable row level security;

-- Called only by the webhook with the service role key. Idempotent per event.
create or replace function public.apply_tribute_event(
  p_key text, p_name text, p_tg bigint, p_expires timestamptz, p_payload jsonb
) returns text
language plpgsql security definer set search_path = public as $$
declare
  v_uid integer;
  v_until timestamp := p_expires at time zone 'utc';
begin
  perform pg_advisory_xact_lock(hashtext(p_key));
  if exists (select 1 from public.tribute_events e where e.event_key = p_key) then
    return 'duplicate';
  end if;

  select u.id into v_uid from public.users u where u.telegram_id = p_tg limit 1;

  insert into public.tribute_events (event_key, name, telegram_user_id, user_id, expires_at, payload)
  values (p_key, p_name, p_tg, v_uid, p_expires, p_payload);

  if v_uid is null then
    return 'unmatched';
  end if;

  insert into public.foreman_access (user_id, paid_until)
  values (v_uid, v_until)
  on conflict (user_id) do update
    set paid_until = greatest(coalesce(public.foreman_access.paid_until, v_until), v_until);
  return 'applied';
end $$;

revoke all on function public.apply_tribute_event(text, text, bigint, timestamptz, jsonb) from public, anon, authenticated;
grant execute on function public.apply_tribute_event(text, text, bigint, timestamptz, jsonb) to service_role;

-- If a foreman paid before linking Telegram, attach the stored payments when they open the billing page.
create or replace function public.claim_tribute()
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_uid integer;
  v_tg bigint;
  v_until timestamptz;
begin
  select u.id, u.telegram_id into v_uid, v_tg from public.users u where u.auth_id = auth.uid();
  if v_uid is null or v_tg is null then return; end if;

  select max(e.expires_at) into v_until
  from public.tribute_events e
  where e.telegram_user_id = v_tg and e.user_id is null;

  if v_until is not null then
    update public.tribute_events set user_id = v_uid where telegram_user_id = v_tg and user_id is null;
    insert into public.foreman_access (user_id, paid_until)
    values (v_uid, v_until at time zone 'utc')
    on conflict (user_id) do update
      set paid_until = greatest(coalesce(public.foreman_access.paid_until, v_until at time zone 'utc'), v_until at time zone 'utc');
  end if;
end $$;

grant execute on function public.claim_tribute() to authenticated;

create or replace function public.billing_status()
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_uid integer;
  v_n integer;
  v_until timestamp;
  v_linked boolean;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  select count(*) into v_n from public.sites s where s.foreman_id = v_uid;
  select a.paid_until into v_until from public.foreman_access a where a.user_id = v_uid;
  select (u.telegram_id is not null) into v_linked from public.users u where u.id = v_uid;
  return jsonb_build_object(
    'sites', v_n,
    'free_limit', 3,
    'price', 500,
    'period_days', 30,
    'paid_until', v_until,
    'telegram_linked', coalesce(v_linked, false),
    'unlocked', coalesce(v_until > (now() at time zone 'utc'), false)
  );
end $$;

notify pgrst, 'reload schema';

-- Site chat + Telegram connect for the PWA.
-- Run in Supabase SQL Editor AFTER supabase_pwa_profile.sql (uses users.avatar_path).
-- The existing `messages` table is shared with the Telegram bot, so both sides see the same chat.

alter table public.messages add column if not exists task_id integer references public.tasks(id) on delete set null;
alter table public.messages add column if not exists kind varchar(10) not null default 'message';

do $$ begin
  alter table public.messages add constraint messages_kind_check check (kind in ('message', 'buy', 'problem'));
exception when duplicate_object then null; end $$;

create index if not exists ix_messages_site_id_id on public.messages (site_id, id desc);

-- One-time codes to attach a Telegram account to a PWA profile (written by the web app, consumed by the bot).
create table if not exists public.tg_connect_codes (
  code varchar(12) primary key,
  user_id integer not null references public.users(id) on delete cascade,
  expires_at timestamp not null
);
alter table public.tg_connect_codes enable row level security;

-- True if the current user is the foreman of the site or one of its workers.
create or replace function public.chat_can_access(p_site integer)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.users u
    where u.auth_id = auth.uid()
      and (
        exists (select 1 from public.sites s where s.id = p_site and s.foreman_id = u.id)
        or exists (select 1 from public.site_members m where m.site_id = p_site and m.worker_id = u.id)
      )
  )
$$;

-- Without p_after: the latest p_limit messages. With p_after: only newer ones. Always oldest first.
create or replace function public.get_chat(p_site integer, p_after integer default null, p_limit integer default 100)
returns table (
  id integer, user_id integer, author_name text, avatar_path text, body text,
  kind text, task_id integer, task_title text, has_photo boolean, sent_at timestamp
)
language sql stable security definer set search_path = public as $$
  select * from (
    select m.id, m.user_id, u.name::text as author_name, u.avatar_path::text as avatar_path,
           m.text::text as body, m.kind::text as kind, m.task_id, t.title::text as task_title,
           (m.photo_id is not null) as has_photo, m.sent_at
    from public.messages m
    join public.users u on u.id = m.user_id
    left join public.tasks t on t.id = m.task_id
    where m.site_id = p_site
      and public.chat_can_access(p_site)
      and (p_after is null or m.id > p_after)
    order by (case when p_after is null then -m.id else m.id end)
    limit least(greatest(coalesce(p_limit, 100), 1), 200)
  ) s
  order by s.id
$$;

create or replace function public.send_chat_message(p_site integer, p_text text, p_kind text default 'message', p_task integer default null)
returns integer
language plpgsql security definer set search_path = public as $$
declare
  v_uid integer;
  v_id integer;
  v_text text := trim(coalesce(p_text, ''));
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  if not public.chat_can_access(p_site) then raise exception 'forbidden'; end if;
  if v_text = '' then raise exception 'message required'; end if;
  if length(v_text) > 2000 then raise exception 'message too long'; end if;
  if p_kind not in ('message', 'buy', 'problem') then raise exception 'bad kind'; end if;
  if p_task is not null and not exists (select 1 from public.tasks t where t.id = p_task and t.site_id = p_site) then
    raise exception 'task not in site';
  end if;
  insert into public.messages (site_id, user_id, text, kind, task_id)
  values (p_site, v_uid, v_text, p_kind, p_task)
  returning id into v_id;
  return v_id;
end $$;

-- Telegram recipients for a message: other participants of the site who connected Telegram and kept notifications on.
-- Only the author of the message can call it for that message.
create or replace function public.chat_notify_targets(p_message integer)
returns table (chat_id bigint, site_name text, author text, body text, kind text, task_title text)
language sql stable security definer set search_path = public as $$
  select r.telegram_id, s.name::text, au.name::text, m.text::text, m.kind::text, t.title::text
  from public.messages m
  join public.sites s on s.id = m.site_id
  join public.users au on au.id = m.user_id
  left join public.tasks t on t.id = m.task_id
  join public.users r
    on r.telegram_id is not null
   and r.notifications
   and r.id <> m.user_id
   and (r.id = s.foreman_id or exists (
         select 1 from public.site_members sm where sm.site_id = m.site_id and sm.worker_id = r.id))
  where m.id = p_message and au.auth_id = auth.uid()
$$;

create or replace function public.set_notifications(p_on boolean)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  update public.users set notifications = coalesce(p_on, true) where auth_id = auth.uid();
end $$;

create or replace function public.create_telegram_connect_code()
returns text
language plpgsql security definer set search_path = public as $$
declare
  v_uid integer;
  v_tg bigint;
  v_code text;
begin
  select u.id, u.telegram_id into v_uid, v_tg from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  if v_tg is not null then raise exception 'telegram already connected'; end if;
  delete from public.tg_connect_codes where user_id = v_uid or expires_at < (now() at time zone 'utc');
  v_code := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 10));
  insert into public.tg_connect_codes (code, user_id, expires_at)
  values (v_code, v_uid, (now() at time zone 'utc') + interval '15 minutes');
  return v_code;
end $$;

revoke all on function public.chat_can_access(integer) from public, anon;
revoke all on function public.get_chat(integer, integer, integer) from public, anon;
revoke all on function public.send_chat_message(integer, text, text, integer) from public, anon;
revoke all on function public.chat_notify_targets(integer) from public, anon;
revoke all on function public.set_notifications(boolean) from public, anon;
revoke all on function public.create_telegram_connect_code() from public, anon;
grant execute on function public.chat_can_access(integer) to authenticated;
grant execute on function public.get_chat(integer, integer, integer) to authenticated;
grant execute on function public.send_chat_message(integer, text, text, integer) to authenticated;
grant execute on function public.chat_notify_targets(integer) to authenticated;
grant execute on function public.set_notifications(boolean) to authenticated;
grant execute on function public.create_telegram_connect_code() to authenticated;

notify pgrst, 'reload schema';

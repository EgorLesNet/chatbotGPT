-- PWA migration for the existing bot schema.
-- Run in Supabase SQL Editor AFTER supabase_schema.sql.

alter table public.users
  add column if not exists auth_id uuid unique references auth.users(id) on delete set null;

create index if not exists ix_users_auth_id on public.users(auth_id);

-- Object media and task-report media are stored here.
insert into storage.buckets (id, name, public)
values ('construction-media', 'construction-media', false)
on conflict (id) do nothing;

-- RLS policies for PWA. The Telegram bot uses the database connection directly.
-- A user has access only after their Supabase account is linked to users.auth_id.
create or replace function public.current_app_user_id()
returns integer
language sql stable security definer set search_path = public
as $$
  select id from public.users where auth_id = auth.uid()
$$;

create or replace function public.current_app_role()
returns userrole
language sql stable security definer set search_path = public
as $$
  select role from public.users where auth_id = auth.uid()
$$;

create policy "users read own profile" on public.users
for select to authenticated using (auth_id = auth.uid());

create policy "sites read as participant" on public.sites
for select to authenticated using (
  foreman_id = public.current_app_user_id()
  or exists (select 1 from public.site_members sm where sm.site_id = sites.id and sm.worker_id = public.current_app_user_id())
);

create policy "tasks read on accessible site" on public.tasks
for select to authenticated using (
  exists (
    select 1 from public.sites s
    where s.id = tasks.site_id and (
      s.foreman_id = public.current_app_user_id()
      or exists (select 1 from public.site_members sm where sm.site_id = s.id and sm.worker_id = public.current_app_user_id())
    )
  )
);

create policy "messages read on accessible site" on public.messages
for select to authenticated using (
  exists (
    select 1 from public.sites s
    where s.id = messages.site_id and (
      s.foreman_id = public.current_app_user_id()
      or exists (select 1 from public.site_members sm where sm.site_id = s.id and sm.worker_id = public.current_app_user_id())
    )
  )
);

-- Storage access is limited to logged-in users. Object-specific checks are added with upload screens.
create policy "authenticated read construction media" on storage.objects
for select to authenticated using (bucket_id = 'construction-media');

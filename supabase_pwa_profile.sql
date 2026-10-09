-- Profile editing + avatars for the PWA. Run in Supabase SQL Editor AFTER supabase_pwa_photos.sql.

alter table public.users add column if not exists avatar_path text;

-- Public bucket for avatars (max 2 MB, images only)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('avatars', 'avatars', true, 2097152, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
  set public = true,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

create or replace function public.my_user_id()
returns integer
language sql stable security definer set search_path = public as $$
  select id from public.users where auth_id = auth.uid()
$$;

revoke all on function public.my_user_id() from public, anon;
grant execute on function public.my_user_id() to authenticated;

-- Everyone can view avatars by public URL; only the owner can write to their own folder
drop policy if exists "avatars upload own" on storage.objects;
drop policy if exists "avatars read own" on storage.objects;
drop policy if exists "avatars delete own" on storage.objects;

create policy "avatars upload own" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = public.my_user_id()::text);

create policy "avatars read own" on storage.objects
  for select to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = public.my_user_id()::text);

create policy "avatars delete own" on storage.objects
  for delete to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = public.my_user_id()::text);

-- Change own name and role. The role is locked while it would orphan existing data.
create or replace function public.update_my_profile(p_name text, p_role userrole)
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_uid integer;
  v_role userrole;
  v_name text := trim(coalesce(p_name, ''));
begin
  select u.id, u.role into v_uid, v_role from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  if length(v_name) < 2 then raise exception 'name too short'; end if;
  if length(v_name) > 100 then raise exception 'name too long'; end if;

  if p_role is distinct from v_role then
    if v_role = 'foreman' and exists (select 1 from public.sites s where s.foreman_id = v_uid) then
      raise exception 'role locked foreman';
    end if;
    if v_role = 'worker' and (
      exists (select 1 from public.site_members m where m.worker_id = v_uid)
      or exists (select 1 from public.tasks t where t.taken_by_id = v_uid)
    ) then
      raise exception 'role locked worker';
    end if;
  end if;

  update public.users set name = v_name, role = p_role where id = v_uid;
end $$;

-- Set or clear own avatar (path must be inside own folder)
create or replace function public.set_avatar(p_path text)
returns void
language plpgsql security definer set search_path = public as $$
declare v_uid integer;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'profile required'; end if;
  if p_path is not null and (p_path not like v_uid::text || '/%' or p_path like '%..%') then
    raise exception 'bad avatar path';
  end if;
  update public.users set avatar_path = p_path where id = v_uid;
end $$;

revoke all on function public.update_my_profile(text, userrole) from public, anon;
revoke all on function public.set_avatar(text) from public, anon;
grant execute on function public.update_my_profile(text, userrole) to authenticated;
grant execute on function public.set_avatar(text) to authenticated;

notify pgrst, 'reload schema';

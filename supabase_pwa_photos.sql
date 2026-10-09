-- Task photos for the PWA. Run in Supabase SQL Editor AFTER supabase_pwa_manage.sql.

-- Private bucket for report photos (max 5 MB, images only)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('task-photos', 'task-photos', false, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- Only the worker who holds an in-progress task may upload photos for it
create or replace function public.can_upload_task_photo(p_task_id integer)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1
    from public.tasks t
    join public.users u on u.id = t.taken_by_id
    where t.id = p_task_id and u.auth_id = auth.uid() and t.status = 'in_progress'
  )
$$;

revoke all on function public.can_upload_task_photo(integer) from public, anon;
grant execute on function public.can_upload_task_photo(integer) to authenticated;

drop policy if exists "task photos upload" on storage.objects;
drop policy if exists "task photos read" on storage.objects;

create policy "task photos upload" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'task-photos'
    and case when (storage.foldername(name))[1] ~ '^[0-9]+$'
      then public.can_upload_task_photo(((storage.foldername(name))[1])::integer)
      else false end
  );

create policy "task photos read" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'task-photos'
    and case when (storage.foldername(name))[1] ~ '^[0-9]+$'
      then public.has_task_access(((storage.foldername(name))[1])::integer)
      else false end
  );

-- submit_task now requires a comment and 1-10 uploaded photos
drop function if exists public.submit_task(integer, text);

create or replace function public.submit_task(p_task_id integer, p_comment text, p_photos text[])
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_uid integer; v_taken integer; v_status taskstatus;
  v_photos text[] := coalesce(p_photos, '{}'::text[]);
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid() and u.role = 'worker';
  if v_uid is null then raise exception 'forbidden'; end if;

  select t.taken_by_id, t.status into v_taken, v_status from public.tasks t where t.id = p_task_id for update;
  if not found then raise exception 'not found'; end if;
  if v_taken is distinct from v_uid then raise exception 'forbidden'; end if;
  if v_status <> 'in_progress' then raise exception 'wrong status'; end if;

  if length(trim(coalesce(p_comment, ''))) < 1 then raise exception 'comment required'; end if;
  if coalesce(cardinality(v_photos), 0) < 1 then raise exception 'photo required'; end if;
  if cardinality(v_photos) > 10 then raise exception 'too many photos'; end if;
  if exists (
    select 1 from unnest(v_photos) as p
    where p not like p_task_id::text || '/%' or p like '%..%'
  ) then
    raise exception 'bad photo path';
  end if;
  if (select count(*) from storage.objects o where o.bucket_id = 'task-photos' and o.name = any(v_photos))
     <> cardinality(v_photos) then
    raise exception 'photo not found';
  end if;

  insert into public.task_reports (task_id, worker_id, comment, photos_json)
  values (p_task_id, v_uid, trim(p_comment), to_json(v_photos)::text);
  update public.tasks set status = 'review' where id = p_task_id;
end $$;

revoke all on function public.submit_task(integer, text, text[]) from public, anon;
grant execute on function public.submit_task(integer, text, text[]) to authenticated;

notify pgrst, 'reload schema';

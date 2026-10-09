-- Management functions for the PWA. Run in Supabase SQL Editor AFTER supabase_pwa_tasks.sql.

create or replace function public.require_foreman_of_site(p_site_id integer)
returns integer
language plpgsql security definer set search_path = public as $$
declare v_uid integer;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid() and u.role = 'foreman';
  if v_uid is null or not exists (select 1 from public.sites s where s.id = p_site_id and s.foreman_id = v_uid) then
    raise exception 'forbidden';
  end if;
  return v_uid;
end $$;

create or replace function public.update_site(p_site_id integer, p_name text, p_address text)
returns void
language plpgsql security definer set search_path = public as $$
begin
  perform public.require_foreman_of_site(p_site_id);
  if length(trim(coalesce(p_name, ''))) < 2 then raise exception 'name required'; end if;
  update public.sites
     set name = left(trim(p_name), 200), address = left(trim(coalesce(p_address, '')), 300)
   where id = p_site_id;
end $$;

create or replace function public.regenerate_invite(p_site_id integer)
returns text
language plpgsql security definer set search_path = public as $$
declare v_code text;
begin
  perform public.require_foreman_of_site(p_site_id);
  v_code := substr(md5(random()::text || clock_timestamp()::text || p_site_id::text), 1, 12);
  update public.sites set invite_code = v_code where id = p_site_id;
  return v_code;
end $$;

create or replace function public.delete_site(p_site_id integer)
returns void
language plpgsql security definer set search_path = public as $$
begin
  perform public.require_foreman_of_site(p_site_id);
  delete from public.sites where id = p_site_id;
end $$;

create or replace function public.remove_member(p_site_id integer, p_worker_id integer)
returns void
language plpgsql security definer set search_path = public as $$
begin
  perform public.require_foreman_of_site(p_site_id);
  update public.tasks
     set status = 'open', taken_by_id = null
   where site_id = p_site_id and taken_by_id = p_worker_id and status = 'in_progress';
  delete from public.site_members where site_id = p_site_id and worker_id = p_worker_id;
end $$;

create or replace function public.update_task(p_task_id integer, p_title text, p_description text)
returns void
language plpgsql security definer set search_path = public as $$
declare v_site integer;
begin
  select t.site_id into v_site from public.tasks t where t.id = p_task_id;
  if v_site is null then raise exception 'not found'; end if;
  perform public.require_foreman_of_site(v_site);
  if length(trim(coalesce(p_title, ''))) < 2 then raise exception 'title required'; end if;
  update public.tasks
     set title = left(trim(p_title), 200), description = trim(coalesce(p_description, ''))
   where id = p_task_id;
end $$;

create or replace function public.assign_task(p_task_id integer, p_worker_id integer)
returns void
language plpgsql security definer set search_path = public as $$
declare v_site integer; v_status taskstatus;
begin
  select t.site_id, t.status into v_site, v_status from public.tasks t where t.id = p_task_id for update;
  if v_site is null then raise exception 'not found'; end if;
  perform public.require_foreman_of_site(v_site);
  if v_status not in ('open', 'in_progress') then raise exception 'wrong status'; end if;
  if not exists (select 1 from public.site_members sm where sm.site_id = v_site and sm.worker_id = p_worker_id) then
    raise exception 'worker not in site';
  end if;
  update public.tasks set taken_by_id = p_worker_id, status = 'in_progress' where id = p_task_id;
end $$;

-- Foreman releases any in-progress task; a worker can release only his own.
create or replace function public.release_task(p_task_id integer)
returns void
language plpgsql security definer set search_path = public as $$
declare v_uid integer; v_site integer; v_taken integer; v_status taskstatus;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid();
  if v_uid is null then raise exception 'forbidden'; end if;
  select t.site_id, t.taken_by_id, t.status into v_site, v_taken, v_status
    from public.tasks t where t.id = p_task_id for update;
  if v_site is null then raise exception 'not found'; end if;
  if v_status <> 'in_progress' then raise exception 'wrong status'; end if;
  if not (
    coalesce(v_taken = v_uid, false)
    or exists (select 1 from public.sites s where s.id = v_site and s.foreman_id = v_uid)
  ) then
    raise exception 'forbidden';
  end if;
  update public.tasks set status = 'open', taken_by_id = null where id = p_task_id;
end $$;

create or replace function public.reopen_task(p_task_id integer)
returns void
language plpgsql security definer set search_path = public as $$
declare v_site integer; v_status taskstatus;
begin
  select t.site_id, t.status into v_site, v_status from public.tasks t where t.id = p_task_id for update;
  if v_site is null then raise exception 'not found'; end if;
  perform public.require_foreman_of_site(v_site);
  if v_status <> 'done' then raise exception 'wrong status'; end if;
  update public.tasks set status = 'in_progress' where id = p_task_id;
end $$;

revoke all on function public.require_foreman_of_site(integer) from public, anon, authenticated;
revoke all on function public.update_site(integer, text, text) from public, anon;
revoke all on function public.regenerate_invite(integer) from public, anon;
revoke all on function public.delete_site(integer) from public, anon;
revoke all on function public.remove_member(integer, integer) from public, anon;
revoke all on function public.update_task(integer, text, text) from public, anon;
revoke all on function public.assign_task(integer, integer) from public, anon;
revoke all on function public.release_task(integer) from public, anon;
revoke all on function public.reopen_task(integer) from public, anon;

grant execute on function public.update_site(integer, text, text) to authenticated;
grant execute on function public.regenerate_invite(integer) to authenticated;
grant execute on function public.delete_site(integer) to authenticated;
grant execute on function public.remove_member(integer, integer) to authenticated;
grant execute on function public.update_task(integer, text, text) to authenticated;
grant execute on function public.assign_task(integer, integer) to authenticated;
grant execute on function public.release_task(integer) to authenticated;
grant execute on function public.reopen_task(integer) to authenticated;

notify pgrst, 'reload schema';

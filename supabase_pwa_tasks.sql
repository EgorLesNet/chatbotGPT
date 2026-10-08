-- Sites and tasks for the PWA. Run in Supabase SQL Editor AFTER supabase_pwa_link.sql.

-- 1) Access helpers (security definer: they bypass RLS, so policies do not recurse)
create or replace function public.has_site_access(p_site_id integer)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.sites s
    where s.id = p_site_id and s.foreman_id = public.current_app_user_id()
  ) or exists (
    select 1 from public.site_members sm
    where sm.site_id = p_site_id and sm.worker_id = public.current_app_user_id()
  )
$$;

create or replace function public.has_task_access(p_task_id integer)
returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select public.has_site_access(t.site_id) from public.tasks t where t.id = p_task_id), false)
$$;

create or replace function public.shares_site_with(p_user_id integer)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.sites s
    where public.has_site_access(s.id)
      and (
        s.foreman_id = p_user_id
        or exists (select 1 from public.site_members sm where sm.site_id = s.id and sm.worker_id = p_user_id)
      )
  )
$$;

-- 2) Replace earlier read policies (they queried RLS-protected tables, so workers saw nothing)
drop policy if exists "sites read as participant" on public.sites;
drop policy if exists "tasks read on accessible site" on public.tasks;
drop policy if exists "messages read on accessible site" on public.messages;
drop policy if exists "site_members read as participant" on public.site_members;
drop policy if exists "task_reports read as participant" on public.task_reports;
drop policy if exists "task_reviews read as participant" on public.task_reviews;
drop policy if exists "users read colleagues" on public.users;

create policy "sites read as participant" on public.sites
  for select to authenticated using (public.has_site_access(id));
create policy "tasks read on accessible site" on public.tasks
  for select to authenticated using (public.has_site_access(site_id));
create policy "messages read on accessible site" on public.messages
  for select to authenticated using (public.has_site_access(site_id));
create policy "site_members read as participant" on public.site_members
  for select to authenticated using (public.has_site_access(site_id));
create policy "task_reports read as participant" on public.task_reports
  for select to authenticated using (public.has_task_access(task_id));
create policy "task_reviews read as participant" on public.task_reviews
  for select to authenticated using (public.has_task_access(task_id));
create policy "users read colleagues" on public.users
  for select to authenticated using (public.shares_site_with(id));

-- 3) Write operations (all checks are done on the server side)
create or replace function public.create_site(p_name text, p_address text)
returns integer
language plpgsql security definer set search_path = public as $$
declare v_uid integer; v_id integer;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid() and u.role = 'foreman';
  if v_uid is null then raise exception 'forbidden'; end if;
  if length(trim(coalesce(p_name, ''))) < 2 then raise exception 'name required'; end if;
  insert into public.sites (name, address, foreman_id, invite_code)
  values (
    trim(p_name), trim(coalesce(p_address, '')), v_uid,
    substr(md5(random()::text || clock_timestamp()::text || v_uid::text), 1, 12)
  )
  returning id into v_id;
  return v_id;
end $$;

create or replace function public.create_task(p_site_id integer, p_title text, p_description text)
returns integer
language plpgsql security definer set search_path = public as $$
declare v_uid integer; v_id integer;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid() and u.role = 'foreman';
  if v_uid is null then raise exception 'forbidden'; end if;
  if not exists (select 1 from public.sites s where s.id = p_site_id and s.foreman_id = v_uid) then
    raise exception 'forbidden';
  end if;
  if length(trim(coalesce(p_title, ''))) < 2 then raise exception 'title required'; end if;
  insert into public.tasks (site_id, title, description, status, created_by)
  values (p_site_id, trim(p_title), trim(coalesce(p_description, '')), 'open', v_uid)
  returning id into v_id;
  return v_id;
end $$;

create or replace function public.take_task(p_task_id integer)
returns void
language plpgsql security definer set search_path = public as $$
declare v_uid integer; v_site integer; v_status taskstatus;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid() and u.role = 'worker';
  if v_uid is null then raise exception 'forbidden'; end if;
  select t.site_id, t.status into v_site, v_status from public.tasks t where t.id = p_task_id for update;
  if v_site is null then raise exception 'not found'; end if;
  if not exists (select 1 from public.site_members sm where sm.site_id = v_site and sm.worker_id = v_uid) then
    raise exception 'forbidden';
  end if;
  if v_status <> 'open' then raise exception 'wrong status'; end if;
  update public.tasks set status = 'in_progress', taken_by_id = v_uid where id = p_task_id;
end $$;

create or replace function public.submit_task(p_task_id integer, p_comment text)
returns void
language plpgsql security definer set search_path = public as $$
declare v_uid integer; v_taken integer; v_status taskstatus;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid() and u.role = 'worker';
  if v_uid is null then raise exception 'forbidden'; end if;
  select t.taken_by_id, t.status into v_taken, v_status from public.tasks t where t.id = p_task_id for update;
  if not found then raise exception 'not found'; end if;
  if v_taken is distinct from v_uid then raise exception 'forbidden'; end if;
  if v_status <> 'in_progress' then raise exception 'wrong status'; end if;
  insert into public.task_reports (task_id, worker_id, comment, photos_json)
  values (p_task_id, v_uid, trim(coalesce(p_comment, '')), '[]');
  update public.tasks set status = 'review' where id = p_task_id;
end $$;

create or replace function public.review_task(p_task_id integer, p_accept boolean, p_comment text)
returns void
language plpgsql security definer set search_path = public as $$
declare v_uid integer; v_site integer; v_status taskstatus;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid() and u.role = 'foreman';
  if v_uid is null then raise exception 'forbidden'; end if;
  select t.site_id, t.status into v_site, v_status from public.tasks t where t.id = p_task_id for update;
  if v_site is null then raise exception 'not found'; end if;
  if not exists (select 1 from public.sites s where s.id = v_site and s.foreman_id = v_uid) then
    raise exception 'forbidden';
  end if;
  if v_status <> 'review' then raise exception 'wrong status'; end if;
  insert into public.task_reviews (task_id, foreman_id, comment)
  values (p_task_id, v_uid, trim(coalesce(p_comment, '')));
  update public.tasks
     set status = (case when p_accept then 'done' else 'in_progress' end)::taskstatus
   where id = p_task_id;
end $$;

create or replace function public.delete_task(p_task_id integer)
returns void
language plpgsql security definer set search_path = public as $$
declare v_uid integer; v_site integer;
begin
  select u.id into v_uid from public.users u where u.auth_id = auth.uid() and u.role = 'foreman';
  if v_uid is null then raise exception 'forbidden'; end if;
  select t.site_id into v_site from public.tasks t where t.id = p_task_id;
  if v_site is null then raise exception 'not found'; end if;
  if not exists (select 1 from public.sites s where s.id = v_site and s.foreman_id = v_uid) then
    raise exception 'forbidden';
  end if;
  delete from public.tasks where id = p_task_id;
end $$;

-- 4) Permissions
revoke all on function public.has_site_access(integer) from public, anon;
revoke all on function public.has_task_access(integer) from public, anon;
revoke all on function public.shares_site_with(integer) from public, anon;
revoke all on function public.create_site(text, text) from public, anon;
revoke all on function public.create_task(integer, text, text) from public, anon;
revoke all on function public.take_task(integer) from public, anon;
revoke all on function public.submit_task(integer, text) from public, anon;
revoke all on function public.review_task(integer, boolean, text) from public, anon;
revoke all on function public.delete_task(integer) from public, anon;

grant execute on function public.has_site_access(integer) to authenticated;
grant execute on function public.has_task_access(integer) to authenticated;
grant execute on function public.shares_site_with(integer) to authenticated;
grant execute on function public.create_site(text, text) to authenticated;
grant execute on function public.create_task(integer, text, text) to authenticated;
grant execute on function public.take_task(integer) to authenticated;
grant execute on function public.submit_task(integer, text) to authenticated;
grant execute on function public.review_task(integer, boolean, text) to authenticated;
grant execute on function public.delete_task(integer) to authenticated;

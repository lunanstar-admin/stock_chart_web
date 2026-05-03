-- 관리자가 게시된 블로그 글에 가하는 액션(숨김/표시/삭제) 큐
--
-- 적용 위치: Supabase Studio → SQL Editor

create table if not exists public.blog_admin_actions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  action      text not null check (action in ('delete', 'hide', 'unhide')),
  target_slug text not null,
  status      text not null default 'pending',  -- pending | processing | done | failed
  error       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists idx_blog_admin_actions_status_created
  on public.blog_admin_actions (status, created_at);

alter table public.blog_admin_actions enable row level security;

-- 관리자만 모든 작업 가능
drop policy if exists baa_admin_insert on public.blog_admin_actions;
create policy baa_admin_insert
  on public.blog_admin_actions for insert
  to authenticated
  with check (
    auth.uid() in (select user_id from public.admins)
    and user_id = auth.uid()
  );

drop policy if exists baa_admin_select on public.blog_admin_actions;
create policy baa_admin_select
  on public.blog_admin_actions for select
  to authenticated
  using (auth.uid() in (select user_id from public.admins));

drop policy if exists baa_admin_update on public.blog_admin_actions;
create policy baa_admin_update
  on public.blog_admin_actions for update
  to authenticated
  using (auth.uid() in (select user_id from public.admins))
  with check (auth.uid() in (select user_id from public.admins));

drop policy if exists baa_admin_delete on public.blog_admin_actions;
create policy baa_admin_delete
  on public.blog_admin_actions for delete
  to authenticated
  using (auth.uid() in (select user_id from public.admins));

-- updated_at 자동 트리거 (set_updated_at 함수는 기존 마이그레이션에서 정의됨)
drop trigger if exists trg_blog_admin_actions_updated_at on public.blog_admin_actions;
create trigger trg_blog_admin_actions_updated_at
  before update on public.blog_admin_actions
  for each row execute function public.set_updated_at();

-- 배치(service_role) 가 status 등 갱신할 수 있도록
grant select, update on public.blog_admin_actions to service_role;

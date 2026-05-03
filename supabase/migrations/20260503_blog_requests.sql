-- 관리자가 입력한 종목+주제로 블로그 글을 자동 생성하는 큐 테이블.
-- 1회성 RPM/RPD 만 빼고 모두 멱등 (여러 번 실행해도 안전).
--
-- 적용 위치: Supabase Studio → SQL Editor

-- ─────────────────────────────────────────────
-- 1) 관리자 화이트리스트
-- ─────────────────────────────────────────────
create table if not exists public.admins (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  added_at   timestamptz not null default now(),
  note       text  -- 예: "main admin (kakao 닉네임 lunanstar)"
);

alter table public.admins enable row level security;

-- 본인이 admin 인지 self-check 만 허용 (다른 admin 정보는 노출하지 않음)
drop policy if exists admins_self_check on public.admins;
create policy admins_self_check
  on public.admins for select
  to authenticated
  using (user_id = auth.uid());


-- ─────────────────────────────────────────────
-- 2) 블로그 요청 큐
-- ─────────────────────────────────────────────
create table if not exists public.blog_requests (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  user_label  text,                                          -- 표시용 (카카오 닉네임 등)
  stock_code  text not null,
  stock_name  text not null,
  topic       text not null,                                 -- 자유 텍스트 (예: "AI 데이터센터 전력 인프라 수출 호조")
  notes       text,                                          -- 추가 메모 (선택)
  tone        text not null default 'analysis',              -- analysis | brief | explainer
  due_at      timestamptz not null default now(),            -- 예약 발행 시각
  status      text not null default 'pending',               -- pending | processing | done | failed
  result_slug text,                                          -- 발행 시 글 슬러그
  error       text,                                          -- 실패 시 에러 메시지
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists idx_blog_requests_status_due
  on public.blog_requests (status, due_at);
create index if not exists idx_blog_requests_user
  on public.blog_requests (user_id, created_at desc);

alter table public.blog_requests enable row level security;

-- ───── INSERT 정책 — 관리자만
drop policy if exists blog_requests_admin_insert on public.blog_requests;
create policy blog_requests_admin_insert
  on public.blog_requests for insert
  to authenticated
  with check (
    auth.uid() in (select user_id from public.admins)
    and user_id = auth.uid()
  );

-- ───── SELECT 정책 — 본인 요청 또는 관리자 전체 조회
drop policy if exists blog_requests_self_or_admin_select on public.blog_requests;
create policy blog_requests_self_or_admin_select
  on public.blog_requests for select
  to authenticated
  using (
    user_id = auth.uid()
    or auth.uid() in (select user_id from public.admins)
  );

-- ───── UPDATE 정책 — 본인 요청 (예약 시각 변경 등) 또는 관리자
drop policy if exists blog_requests_self_or_admin_update on public.blog_requests;
create policy blog_requests_self_or_admin_update
  on public.blog_requests for update
  to authenticated
  using (
    user_id = auth.uid()
    or auth.uid() in (select user_id from public.admins)
  )
  with check (
    user_id = auth.uid()
    or auth.uid() in (select user_id from public.admins)
  );

-- ───── DELETE 정책 — 본인 요청 또는 관리자
drop policy if exists blog_requests_self_or_admin_delete on public.blog_requests;
create policy blog_requests_self_or_admin_delete
  on public.blog_requests for delete
  to authenticated
  using (
    user_id = auth.uid()
    or auth.uid() in (select user_id from public.admins)
  );


-- ─────────────────────────────────────────────
-- 3) updated_at 자동 갱신 트리거
-- ─────────────────────────────────────────────
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_blog_requests_updated_at on public.blog_requests;
create trigger trg_blog_requests_updated_at
  before update on public.blog_requests
  for each row execute function public.set_updated_at();


-- ─────────────────────────────────────────────
-- 4) 처리 후 service_role (배치) 가 직접 SELECT/UPDATE 하기 위한 grant
--    service role 키는 GitHub Actions secret 으로만 보관.
-- ─────────────────────────────────────────────
grant select, update on public.blog_requests to service_role;
grant select on public.admins to service_role;


-- ─────────────────────────────────────────────
-- 5) 본인을 admin 으로 등록하기 (1회성, 수동 실행)
-- ─────────────────────────────────────────────
-- 절차:
--   1) secomdal.com 에서 카카오 로그인
--   2) /admin/blog-request 페이지에서 "내 UUID 보기" 버튼 클릭하여 UUID 복사
--   3) 아래 INSERT 의 'PASTE_YOUR_UUID' 부분을 복사한 UUID 로 교체 후 실행
--
-- insert into public.admins (user_id, note)
-- values ('PASTE_YOUR_UUID', 'main admin')
-- on conflict (user_id) do nothing;

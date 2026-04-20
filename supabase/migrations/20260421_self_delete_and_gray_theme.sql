-- Self-service account deletion + theme constraint finalization.
--
-- 실행 위치: Supabase Studio → SQL editor (또는 psql 직접 연결).
-- 대상 프로젝트: auth.js 가 참조하는 프로젝트 (axbbjjpxspvvxbxvuzsz)
--
-- 이 마이그레이션은 두 가지를 처리한다:
--   (A) 'gold' 테마를 'gray' 로 대체 (이전 마이그레이션 20260420 이 이미 적용됐든 안 됐든 안전)
--   (B) 로그인한 사용자가 스스로 계정을 삭제할 수 있는 RPC 를 추가
--
-- 멱등하게 설계되어 여러 번 실행해도 안전.


-- ============================================================
-- (A) 테마 제약조건 확정: 'gold' → 'gray'
-- ============================================================

-- 1) 혹시 아직 theme 컬럼이 없다면 생성 (20260420 미적용 대비)
alter table public.members
  add column if not exists theme text;

-- 2) 기존 제약조건 제거 — 이름 유/무 무관 (members_theme_check 가 있었을 수도 없었을 수도 있음)
alter table public.members
  drop constraint if exists members_theme_check;

-- 3) 기존에 'gold' 로 저장된 데이터 → 'gray' 로 자동 이전
update public.members
  set theme = 'gray', updated_at = now()
  where theme = 'gold';

-- 4) 새 CHECK 추가 — dark/light/sweet/gray 만 허용
alter table public.members
  add constraint members_theme_check
  check (theme is null or theme in ('dark', 'light', 'sweet', 'gray'));


-- ============================================================
-- (B) 회원 탈퇴용 RPC: delete_current_user()
-- ============================================================
--
-- 전제:
--   - public.members.id references auth.users(id) on delete cascade (이미 세팅됨)
--   - public.watchlist.user_id references auth.users(id) on delete cascade
--     (아래 step 3 에서 혹시 누락된 경우 보정)
-- 따라서 auth.users 레코드만 지우면 연관 데이터(members, watchlist)는 자동 제거됨.
--
-- 호출 방법 (클라이언트):
--   const { error } = await sb.rpc('delete_current_user')

-- 1) RPC 함수 정의
create or replace function public.delete_current_user()
returns void
language plpgsql
security definer                  -- owner 권한(postgres) 으로 auth 스키마 접근
set search_path = public, auth
as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'not authenticated'
      using errcode = '28000', hint = 'login required';
  end if;
  -- auth.users 삭제 → on delete cascade 로 public.members, public.watchlist 자동 정리
  delete from auth.users where id = uid;
end;
$$;

-- 2) authenticated 롤에 실행 권한 부여 (anon 은 제외)
revoke all on function public.delete_current_user() from public;
grant execute on function public.delete_current_user() to authenticated;

-- 3) watchlist 외래키가 cascade 가 아니면 보정 — 이미 cascade 면 no-op 에 가까움
--    주의: 테이블/제약 이름이 환경에 따라 다를 수 있으니 실패해도 무시.
do $$
begin
  if exists (
    select 1 from pg_constraint
    where conname = 'watchlist_user_id_fkey'
      and confdeltype <> 'c'    -- 'c' = CASCADE
  ) then
    alter table public.watchlist
      drop constraint watchlist_user_id_fkey;
    alter table public.watchlist
      add constraint watchlist_user_id_fkey
      foreign key (user_id) references auth.users(id) on delete cascade;
  end if;
exception when others then
  -- 외래키 이름이 다를 수 있음 — 조용히 넘어감
  raise notice 'watchlist cascade fix skipped: %', sqlerrm;
end $$;

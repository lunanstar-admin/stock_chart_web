-- 관리자가 회원 가입 추세를 볼 수 있는 SECURITY DEFINER 함수.
-- 개인정보(이메일/닉네임 등)는 노출하지 않음 — 가입 시각만 반환.
--
-- 적용 위치: Supabase Studio → SQL Editor

create or replace function public.admin_member_signups()
returns table (created_at timestamptz)
language sql
security definer  -- auth.users 테이블에 접근하기 위해 함수 소유자 권한으로 실행
set search_path = public, auth
as $$
  -- 호출자가 admin 인지 확인 — admin 이 아니면 빈 결과
  select u.created_at
  from auth.users u
  where exists (
    select 1 from public.admins a where a.user_id = auth.uid()
  )
  order by u.created_at desc
$$;

-- authenticated 사용자가 호출 가능 (내부에서 admin 체크)
revoke all on function public.admin_member_signups() from public;
grant execute on function public.admin_member_signups() to authenticated;


-- 누적 회원수 (현재 시점의 단일 값)
create or replace function public.admin_member_count()
returns integer
language sql
security definer
set search_path = public, auth
as $$
  select case
    when exists (select 1 from public.admins where user_id = auth.uid())
    then (select count(*)::int from auth.users)
    else 0
  end
$$;

revoke all on function public.admin_member_count() from public;
grant execute on function public.admin_member_count() to authenticated;

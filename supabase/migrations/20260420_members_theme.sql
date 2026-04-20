-- Adds per-user theme preference to public.members.
-- Applied against the live Supabase project referenced by web/assets/auth.js.
--
-- 실행 위치: Supabase Studio → SQL editor (또는 psql 직접 연결).
-- 멱등하게 만들어져 여러 번 실행해도 안전.

-- 1) 컬럼 추가 (이미 있으면 no-op).
alter table public.members
  add column if not exists theme text;

-- 2) 허용 값 제약. 클라이언트는 dark/light/sweet/gold 만 저장.
do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'members_theme_check'
  ) then
    alter table public.members
      add constraint members_theme_check
      check (theme is null or theme in ('dark', 'light', 'sweet', 'gold'));
  end if;
end $$;

-- 3) RLS 정책 확인/보완.
-- public.members 는 이미 본인 update 정책이 있다고 가정 (members_self_update).
-- 추가 정책은 필요 없음 — 기존 정책이 컬럼 단위 제한 없이 update 를 허용하므로
-- authenticated 사용자가 자기 레코드의 theme 을 갱신할 수 있다.
-- 만약 정책이 없다면 아래를 주석 해제해 적용하라.

-- alter table public.members enable row level security;
-- drop policy if exists members_self_update on public.members;
-- create policy members_self_update
--   on public.members for update to authenticated
--   using (auth.uid() = id)
--   with check (auth.uid() = id);

-- 4) updated_at 자동 갱신 트리거가 이미 있으면 이 마이그레이션은 완료.
--    없다면 아래 예시를 참고해 별도 추가 가능.
--
-- create or replace function public.touch_updated_at()
-- returns trigger language plpgsql as $$
-- begin new.updated_at = now(); return new; end $$;
-- drop trigger if exists members_touch_updated_at on public.members;
-- create trigger members_touch_updated_at
--   before update on public.members
--   for each row execute function public.touch_updated_at();

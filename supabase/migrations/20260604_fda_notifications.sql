-- FDA 허가 알림 설정 컬럼 추가
-- user_notification_settings 테이블에 notify_fda 컬럼 추가.
-- 기존 행은 기본값 true(알림 ON)으로 초기화.
--
-- 멱등성 보장 — 여러 번 실행해도 안전.

do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'user_notification_settings'
      and column_name = 'notify_fda'
  ) then
    alter table public.user_notification_settings
      add column notify_fda boolean not null default true;
  end if;
end;
$$;

comment on column public.user_notification_settings.notify_fda
  is '국내 바이오기업 FDA 신규 허가 알림 ON/OFF';

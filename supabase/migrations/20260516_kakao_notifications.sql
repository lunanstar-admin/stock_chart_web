-- 카카오톡 이벤트 알림 설정 + 토큰 저장 테이블
-- 사용자가 '내 정보' 모달에서 카톡 알림을 켜면 talk_message scope 로 재동의 후
-- 받은 access_token / refresh_token 을 여기에 저장.
-- 매일 cron 이 opted_in 사용자만 골라 카카오 API 로 메시지 발송.
--
-- 실행: Supabase Studio → SQL editor 에 통째로 붙여넣기.
-- 멱등성 보장 — 여러 번 실행해도 안전.

-- 1) 메인 테이블
create table if not exists public.user_notification_settings (
  user_id                 uuid primary key references auth.users(id) on delete cascade,
  kakao_notify_enabled    boolean not null default false,

  -- 이벤트 카테고리별 ON/OFF
  notify_rate             boolean not null default true,   -- 금통위/FOMC
  notify_cpi              boolean not null default true,   -- CPI 발표
  notify_expiry           boolean not null default true,   -- KOSPI200 만기

  -- 발송 시각 (KST 시 0~23)
  send_hour               int not null default 8 check (send_hour between 0 and 23),

  -- 카카오 토큰 (talk_message 권한)
  kakao_access_token      text,
  kakao_refresh_token     text,
  kakao_token_expires_at  timestamptz,
  kakao_scopes            text[],                          -- 현재 동의된 scope 목록

  -- 발송 추적 (중복 방지)
  last_sent_date          date,                            -- 마지막 발송일 (KST)
  last_sent_event_keys    text[],                          -- 'date|tag|country' 키 배열

  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

-- 2) updated_at 자동 갱신 트리거
create or replace function public.touch_user_notification_settings()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_touch_user_notification_settings
  on public.user_notification_settings;
create trigger trg_touch_user_notification_settings
  before update on public.user_notification_settings
  for each row execute function public.touch_user_notification_settings();

-- 3) RLS — 사용자는 자기 행만 read/write 가능
alter table public.user_notification_settings enable row level security;

drop policy if exists "users read own settings" on public.user_notification_settings;
create policy "users read own settings"
  on public.user_notification_settings
  for select using (auth.uid() = user_id);

drop policy if exists "users insert own settings" on public.user_notification_settings;
create policy "users insert own settings"
  on public.user_notification_settings
  for insert with check (auth.uid() = user_id);

drop policy if exists "users update own settings" on public.user_notification_settings;
create policy "users update own settings"
  on public.user_notification_settings
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "users delete own settings" on public.user_notification_settings;
create policy "users delete own settings"
  on public.user_notification_settings
  for delete using (auth.uid() = user_id);

-- 4) 발송 cron 용 service_role 전용 인덱스 — opted_in + 시각으로 빠르게 조회
create index if not exists idx_user_notif_optedin_hour
  on public.user_notification_settings (send_hour)
  where kakao_notify_enabled = true;

-- 5) 신규 사용자 가입 시 기본 행 자동 생성 (선택 — 없어도 lazy create 가능)
create or replace function public.create_default_notification_settings()
returns trigger as $$
begin
  insert into public.user_notification_settings (user_id, kakao_notify_enabled)
  values (new.id, false)
  on conflict (user_id) do nothing;
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists trg_create_default_notification_settings
  on auth.users;
create trigger trg_create_default_notification_settings
  after insert on auth.users
  for each row execute function public.create_default_notification_settings();

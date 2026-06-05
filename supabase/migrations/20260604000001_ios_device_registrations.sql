-- iOS FDA 알리미 앱 — 디바이스 등록 및 구독 테이블
-- 멱등성 보장 — 여러 번 실행해도 안전.

-- 1) 디바이스 등록 테이블 (APNs 토큰 저장)
create table if not exists public.device_registrations (
  apns_token      text primary key,
  environment     text not null default 'production'
                  check (environment in ('sandbox', 'production')),
  app_version     text,
  os_version      text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  last_active_at  timestamptz not null default now()
);

-- 2) FDA 구독 테이블 (어떤 기업 허가 알림 받을지)
-- company_code = 'all' → 전체 기업 구독
create table if not exists public.fda_watchlist (
  apns_token    text not null references public.device_registrations(apns_token) on delete cascade,
  company_code  text not null default 'all',
  created_at    timestamptz not null default now(),
  primary key (apns_token, company_code)
);

-- 3) updated_at 자동 갱신 트리거
create or replace function public.touch_device_registrations()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_touch_device_registrations on public.device_registrations;
create trigger trg_touch_device_registrations
  before update on public.device_registrations
  for each row execute function public.touch_device_registrations();

-- 4) RLS — Edge Function 은 service_role 로 접근 (RLS 우회)
--    일반 anon 클라이언트는 자기 토큰만 읽기 가능 (선택적)
alter table public.device_registrations enable row level security;
alter table public.fda_watchlist enable row level security;

-- anon/authenticated 는 직접 접근 차단 (Edge Function service_role 만 허용)
drop policy if exists "deny all device_registrations" on public.device_registrations;
create policy "deny all device_registrations"
  on public.device_registrations for all using (false);

drop policy if exists "deny all fda_watchlist" on public.fda_watchlist;
create policy "deny all fda_watchlist"
  on public.fda_watchlist for all using (false);

-- 5) 조회 성능 인덱스
create index if not exists idx_device_reg_environment
  on public.device_registrations (environment);
create index if not exists idx_fda_watchlist_company
  on public.fda_watchlist (company_code);

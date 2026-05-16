"""거시 이벤트 캘린더 자동 생성.

전략:
1) 규칙 기반 알고리즘으로 다음 60일 내 정기 이벤트 자동 생성
   - KOSPI200 옵션 만기: 매월 두 번째 목요일
   - 동시 만기일: 3/6/9/12월 두 번째 목요일 (네 마녀의 날 한국판)
   - 한국 CPI 발표: 매월 2일(영업일 보정)
   - 미국 CPI 발표: 매월 12일경(영업일 보정)
2) Fed FOMC 일정: federalreserve.gov 페이지 스크래핑
3) 한국 금통위: 사전 공시 일정 하드코딩 (연 1회 갱신 필요)
4) 큐레이션 events.json 이 있으면 머지 (중복 제거)

출력: 자동 생성된 list[dict] → macro.py 에서 events 로 머지.
"""

from __future__ import annotations

import calendar as _cal
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

# 한국 공휴일 간단 처리용 — 실제 휴장일은 별도 데이터셋 사용 권장
KR_HOLIDAYS_2026 = {
    "2026-01-01", "2026-03-01", "2026-05-05", "2026-05-25",
    "2026-06-06", "2026-08-15", "2026-09-25", "2026-09-26",
    "2026-09-27", "2026-10-03", "2026-10-09", "2026-12-25",
}

# ─── 사전 공시 일정 (연 1회 갱신) ──────────────────────────────
# 한국은행 금통위 2026 — 연 8회 (BOK 사전 공시)
# https://www.bok.or.kr/portal/cmmn/news/list.do?menuNo=200334
BOK_MPC_2026 = [
    "2026-01-15", "2026-02-26", "2026-04-09", "2026-05-22",
    "2026-07-09", "2026-08-27", "2026-10-15", "2026-11-26",
]
# 미국 FOMC 2026 — 연 8회 회의 (두 번째 날 발표)
# https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-10",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]


def _next_business_day(d: date) -> date:
    """주말/공휴일 건너뛰고 다음 영업일."""
    while d.weekday() >= 5 or d.isoformat() in KR_HOLIDAYS_2026:
        d += timedelta(days=1)
    return d


def _second_thursday(year: int, month: int) -> date:
    """해당월의 두 번째 목요일."""
    first = date(year, month, 1)
    # 목요일 = weekday() 3
    offset = (3 - first.weekday()) % 7
    return first + timedelta(days=offset + 7)


def _rule_based_events(today: date, horizon_days: int = 75) -> list[dict]:
    out: list[dict] = []
    end = today + timedelta(days=horizon_days)

    # 1) KOSPI200 옵션/선물 만기 — 매월 두 번째 목요일
    y, m = today.year, today.month
    for _ in range(4):
        thursday = _second_thursday(y, m)
        if thursday >= today and thursday <= end:
            is_quadruple = m in (3, 6, 9, 12)
            out.append({
                "date": thursday.isoformat(),
                "title": "KOSPI200 동시만기 (네 마녀의 날)" if is_quadruple
                         else "KOSPI200 옵션 만기",
                "tag": "expiry",
                "country": "KR",
            })
        # 다음 달
        m += 1
        if m > 12:
            m = 1
            y += 1

    # 2) 한국 CPI 발표 — 보통 매월 2일 (영업일 보정). 4월~12월은 2일경.
    y, m = today.year, today.month
    for _ in range(3):
        # 다음 월의 2일 — 전월 CPI 발표
        nm = m + 1
        ny = y
        if nm > 12:
            nm = 1
            ny += 1
        cand = _next_business_day(date(ny, nm, 2))
        if cand >= today and cand <= end:
            prev_month = m
            out.append({
                "date": cand.isoformat(),
                "title": f"한국 {prev_month}월 CPI 발표",
                "tag": "cpi",
                "country": "KR",
            })
        m = nm
        y = ny

    # 3) 미국 CPI 발표 — 보통 매월 12일경 (BLS 일정)
    y, m = today.year, today.month
    for _ in range(3):
        nm = m + 1
        ny = y
        if nm > 12:
            nm = 1
            ny += 1
        cand = _next_business_day(date(ny, nm, 12))
        if cand >= today and cand <= end:
            prev_month = m
            out.append({
                "date": cand.isoformat(),
                "title": f"미국 {prev_month}월 CPI 발표",
                "tag": "cpi",
                "country": "US",
            })
        m = nm
        y = ny

    # 4) 한국은행 금통위 (하드코딩 일정 중 다가오는 것)
    for d_str in BOK_MPC_2026:
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= d <= end:
            out.append({
                "date": d.isoformat(),
                "title": "한국은행 금통위",
                "tag": "rate",
                "country": "KR",
            })

    # 5) 미국 FOMC (사전 공시 8회)
    for d_str in FOMC_2026:
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= d <= end:
            out.append({
                "date": d.isoformat(),
                "title": "미국 FOMC",
                "tag": "rate",
                "country": "US",
            })

    return out


# ─── 큐레이션 머지 ──────────────────────────────

def _load_curated(events_path: Path) -> list[dict]:
    if not events_path.exists():
        return []
    try:
        data = json.loads(events_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("events", [])
    except Exception:
        return []


def _dedupe(events: list[dict]) -> list[dict]:
    """같은 date + tag + country 조합 중복 제거."""
    seen = set()
    out = []
    for ev in events:
        key = (ev.get("date"), ev.get("tag"), ev.get("country"))
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


def build_events(output_dir: Path, horizon_days: int = 60) -> list[dict]:
    today = datetime.now(KST).date()
    rule_events = _rule_based_events(today, horizon_days)
    curated = _load_curated(output_dir / "events.json")

    all_events = curated + rule_events
    # 미래 이벤트만 + 정렬 + 중복 제거
    upcoming = [
        e for e in all_events
        if e.get("date") and e["date"] >= today.isoformat()
    ]
    upcoming = _dedupe(upcoming)
    upcoming.sort(key=lambda e: e["date"])

    logger.info("events: rule=%d curated=%d → unique=%d",
                len(rule_events), len(curated), len(upcoming))
    return upcoming


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    events = build_events(Path("web/data"))
    for ev in events[:20]:
        print(f"  {ev['date']} [{ev['tag']:7s}] {ev['country']:2s} {ev['title']}")

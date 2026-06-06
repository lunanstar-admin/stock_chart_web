"""FDA 실시간 알림 파이프라인 — DART 공시 + FDA Newsroom RSS 모니터링.

openFDA API 는 승인 후 DB 반영까지 수일~수주 시차가 있어 '속보'엔 부적합하다.
가장 빠른 두 채널을 직접 리스닝한다:

  1) DART OpenAPI  — 국내 상장 바이오기업의 의무공시 (FDA 허가·임상·실사)
                     의무공시라 사실상 실시간 (수초~수분).
  2) FDA Newsroom RSS — FDA 가 openFDA DB 반영 전에 먼저 배포하는 보도자료.

신규 항목은 web/data/fda_alerts_state.json (seen ID 집합) 으로 dedup 하고,
web/data/fda_alerts.json (최근 피드) 로 저장한다. 신규 발생 시 Supabase
Edge Function(send-fda-push) 으로 iOS 푸시를 트리거한다.

환경변수:
  DART_API_KEY               — DART OpenAPI 인증키 (필수, 없으면 DART 스캔 스킵)
  SUPABASE_URL               — 푸시 트리거용 (선택)
  SUPABASE_SERVICE_ROLE_KEY  — 푸시 트리거용 (선택)

실행:
  python -m batch.fda_realtime [--output web/data] [--days 3]
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import requests

from batch.fda_approvals import KOREAN_BIO_COMPANIES

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

# ── DART ───────────────────────────────────────────────────────────────────
DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_CORPCODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"

# corp_code 매핑 캐시 (gitignore 된 batch/.cache/)
_CACHE_DIR = Path(__file__).resolve().parent / ".cache"
_CORPMAP_CACHE = _CACHE_DIR / "dart_corpcode.json"
_CORPMAP_TTL_DAYS = 7

# report_nm(공시 제목) 에 포함되면 FDA 관련으로 강하게 판단하는 키워드
DART_STRONG_KEYWORDS = [
    "FDA", "BLA", "NDA", "ANDA", "품목허가", "시판허가",
    "신속심사", "패스트트랙", "희귀의약품", "우선심사",
]
# 바이오기업이 FDA 관련 내용을 담아 올리는 자율/주요경영사항 공시 유형.
# 제목 자체엔 'FDA' 가 없을 수 있어, 이 유형이면 후보로 포함한다.
DART_CONTEXT_KEYWORDS = [
    "기타경영사항", "투자판단", "단일판매", "공급계약", "임상시험",
    "기술이전", "라이선스", "수출",
]

# ── FDA Newsroom RSS ─────────────────────────────────────────────────────────
FDA_RSS_FEEDS = [
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/fda-newsroom/rss.xml",
]

_HEADERS = {
    "User-Agent": "secomdal-fda-tracker/1.0 (https://secomdal.com)",
    "Accept": "application/json, application/xml, text/xml, */*",
}

# FDA(www.fda.gov)는 Akamai 봇 보호로 비브라우저 UA 에 403 을 줄 수 있어,
# RSS 요청엔 브라우저형 User-Agent 를 사용한다.
_RSS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

MAX_FEED_ITEMS = 120  # fda_alerts.json 에 보관할 최대 항목 수


# ── corp_code 매핑 ───────────────────────────────────────────────────────────

def _load_corp_map(api_key: str) -> dict[str, str]:
    """종목코드(6자리) → DART corp_code(8자리) 매핑. 7일 캐시."""
    if _CORPMAP_CACHE.exists():
        try:
            age_days = (datetime.now().timestamp() - _CORPMAP_CACHE.stat().st_mtime) / 86400
            if age_days < _CORPMAP_TTL_DAYS:
                return json.loads(_CORPMAP_CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass

    logger.info("DART corpCode.xml 다운로드 중...")
    r = requests.get(
        DART_CORPCODE_URL, params={"crtfc_key": api_key}, headers=_HEADERS, timeout=30
    )
    r.raise_for_status()

    mapping: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        xml_name = next((n for n in zf.namelist() if n.endswith(".xml")), None)
        if not xml_name:
            raise RuntimeError("corpCode zip 안에 xml 없음")
        root = ET.fromstring(zf.read(xml_name))

    for item in root.iter("list"):
        stock = (item.findtext("stock_code") or "").strip()
        corp = (item.findtext("corp_code") or "").strip()
        if stock and corp and stock != " ":
            mapping[stock] = corp

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CORPMAP_CACHE.write_text(json.dumps(mapping), encoding="utf-8")
    logger.info("corp_code 매핑 %d건 캐시", len(mapping))
    return mapping


# ── DART 스캔 ────────────────────────────────────────────────────────────────

def _fetch_disclosures(api_key: str, corp_code: str, bgn_de: str, end_de: str) -> list[dict]:
    """한 기업의 기간 내 공시 목록 조회."""
    try:
        r = requests.get(
            DART_LIST_URL,
            params={
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "page_count": 100,
            },
            headers=_HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        # status 000=정상, 013=조회된 데이터 없음
        if data.get("status") not in ("000", "013"):
            logger.warning("DART %s status=%s msg=%s", corp_code, data.get("status"), data.get("message"))
            return []
        return data.get("list", []) or []
    except Exception as e:
        logger.warning("DART 조회 실패 %s: %s", corp_code, e)
        return []


def _match_dart(report_nm: str) -> tuple[bool, str, str]:
    """공시 제목 판정. (matched, tier, matched_keyword).

    tier="strong" — FDA/허가 직접 키워드 → 푸시 발송
    tier="context" — 바이오 자율공시 유형 → 피드에만 노출(푸시 안 함, 노이즈 방지)
    """
    title = report_nm or ""
    for kw in DART_STRONG_KEYWORDS:
        if kw in title:
            return True, "strong", kw
    for kw in DART_CONTEXT_KEYWORDS:
        if kw in title:
            return True, "context", kw
    return False, "", ""


def _scan_dart(api_key: str, days: int) -> list[dict]:
    """국내 바이오기업 DART 공시 스캔 → 알림 후보 리스트."""
    corp_map = _load_corp_map(api_key)
    today = datetime.now(KST)
    bgn_de = (today - timedelta(days=days)).strftime("%Y%m%d")
    end_de = today.strftime("%Y%m%d")

    alerts: list[dict] = []
    for company in KOREAN_BIO_COMPANIES:
        code = company["code"]
        corp_code = corp_map.get(code)
        if not corp_code:
            logger.debug("corp_code 없음: %s(%s)", company["name_ko"], code)
            continue

        for d in _fetch_disclosures(api_key, corp_code, bgn_de, end_de):
            report_nm = d.get("report_nm", "")
            matched, tier, kw = _match_dart(report_nm)
            if not matched:
                continue
            rcept_no = d.get("rcept_no", "")
            if not rcept_no:
                continue
            alerts.append({
                "id": f"dart:{rcept_no}",
                "source": "DART",
                "company_ko": company["name_ko"],
                "company_en": company["name_en"],
                "code": code,
                "title": report_nm.strip(),
                "url": DART_VIEWER.format(rcept_no),
                "published": _fmt_dart_date(d.get("rcept_dt", "")),
                "tier": tier,
                "matched_keyword": kw,
                "flr_nm": d.get("flr_nm", ""),
            })
    logger.info("DART 스캔 완료: 후보 %d건", len(alerts))
    return alerts


def _fmt_dart_date(yyyymmdd: str) -> str:
    s = (yyyymmdd or "").strip()
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


# ── FDA Newsroom RSS 스캔 ────────────────────────────────────────────────────

def _company_match_terms() -> list[tuple[str, dict]]:
    """RSS 본문에서 찾을 (소문자 검색어, 회사) 목록."""
    terms: list[tuple[str, dict]] = []
    for c in KOREAN_BIO_COMPANIES:
        seen: set[str] = set()
        for t in [c["name_en"], *c.get("fda_queries", [])]:
            t = (t or "").strip().lower()
            # 너무 짧거나 일반적인 토큰은 제외 (오탐 방지)
            if len(t) >= 4 and t not in seen:
                seen.add(t)
                terms.append((t, c))
    return terms


def _scan_rss() -> list[dict]:
    """FDA Newsroom RSS 에서 국내 기업 언급 항목 추출."""
    terms = _company_match_terms()
    alerts: list[dict] = []
    seen_ids: set[str] = set()

    for feed_url in FDA_RSS_FEEDS:
        try:
            r = requests.get(feed_url, headers=_RSS_HEADERS, timeout=20)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except Exception as e:
            logger.warning("FDA RSS 조회 실패 %s: %s", feed_url, e)
            continue

        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or link).strip()
            pub = (item.findtext("pubDate") or "").strip()
            haystack = f"{title}\n{desc}".lower()

            for term, company in terms:
                if term in haystack:
                    aid = f"rss:{guid}"
                    if aid in seen_ids:
                        continue
                    seen_ids.add(aid)
                    alerts.append({
                        "id": aid,
                        "source": "FDA RSS",
                        "company_ko": company["name_ko"],
                        "company_en": company["name_en"],
                        "code": company["code"],
                        "title": title,
                        "url": link,
                        "published": pub,
                        "tier": "strong",  # FDA 보도자료에 직접 언급 → 푸시
                        "matched_keyword": term,
                    })
                    break  # 한 항목당 한 회사만 매칭
    logger.info("FDA RSS 스캔 완료: 후보 %d건", len(alerts))
    return alerts


# ── 상태 관리 & 메인 ─────────────────────────────────────────────────────────

def _load_state(path: Path) -> set[str]:
    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding="utf-8")).get("seen", []))
        except Exception:
            pass
    return set()


def _save_state(path: Path, seen: set[str]) -> None:
    # seen 집합이 무한정 커지지 않게 최근 2000개만 보관
    trimmed = list(seen)[-2000:]
    path.write_text(
        json.dumps({"updated": datetime.now(KST).replace(microsecond=0).isoformat(),
                    "seen": trimmed}, ensure_ascii=False),
        encoding="utf-8",
    )


def build_alerts(output_dir: Path, days: int = 3) -> dict:
    """DART + RSS 스캔 → 신규 항목 감지 → 피드 저장 + 푸시 트리거.

    Returns: {"new": int, "total": int}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    state_path = output_dir / "fda_alerts_state.json"
    feed_path = output_dir / "fda_alerts.json"

    seen = _load_state(state_path)

    candidates: list[dict] = []

    dart_key = os.environ.get("DART_API_KEY", "").strip()
    if dart_key:
        try:
            candidates.extend(_scan_dart(dart_key, days))
        except Exception as e:
            logger.warning("DART 스캔 예외(무시): %s", e)
    else:
        logger.info("DART_API_KEY 미설정 — DART 스캔 스킵")

    try:
        candidates.extend(_scan_rss())
    except Exception as e:
        logger.warning("RSS 스캔 예외(무시): %s", e)

    # 신규 항목만 추출
    new_alerts = [a for a in candidates if a["id"] not in seen]

    # 기존 피드 로드 후 병합 (신규 우선, 최신순 유지)
    existing: list[dict] = []
    if feed_path.exists():
        try:
            existing = json.loads(feed_path.read_text(encoding="utf-8")).get("alerts", [])
        except Exception:
            existing = []

    merged = new_alerts + existing
    # id 중복 제거 (앞쪽 우선)
    deduped: list[dict] = []
    seen_ids: set[str] = set()
    for a in merged:
        if a["id"] in seen_ids:
            continue
        seen_ids.add(a["id"])
        deduped.append(a)
    deduped = deduped[:MAX_FEED_ITEMS]

    payload = {
        "updated": datetime.now(KST).replace(microsecond=0).isoformat(),
        "total": len(deduped),
        "new_count": len(new_alerts),
        "alerts": deduped,
    }
    feed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("fda_alerts.json 저장: 전체 %d건, 신규 %d건", len(deduped), len(new_alerts))

    # 상태 갱신
    for a in candidates:
        seen.add(a["id"])
    _save_state(state_path, seen)

    # 신규 발생 시 푸시 트리거 — 노이즈 방지를 위해 strong tier 만 발송.
    # context(자율공시 유형) 는 피드/웹/앱에는 노출되지만 푸시는 보내지 않는다.
    push_alerts = [a for a in new_alerts if a.get("tier", "strong") == "strong"]
    if push_alerts:
        _trigger_push(push_alerts)

    return {
        "new": len(new_alerts),
        "pushed": len(push_alerts),
        "total": len(deduped),
    }


def _trigger_push(new_alerts: list[dict]) -> None:
    """신규 알림을 Supabase Edge Function 으로 전달해 iOS 푸시 발송."""
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_role_key:
        logger.info("푸시 스킵 (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 미설정)")
        return

    url = f"{supabase_url}/functions/v1/send-fda-push"
    payload = {
        "alerts": [
            {
                "company_ko": a.get("company_ko", ""),
                "company_en": a.get("company_en", ""),
                "code": a.get("code", ""),
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("source", ""),
                "published": a.get("published", ""),
            }
            for a in new_alerts
        ]
    }
    try:
        r = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )
        if r.status_code == 200:
            logger.info("푸시 전송 완료: %s", r.json())
        else:
            logger.warning("푸시 응답 오류: %d %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("푸시 전송 실패(무시): %s", e)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="FDA 실시간 알림 (DART + RSS)")
    parser.add_argument("--output", default="web/data")
    parser.add_argument("--days", type=int, default=3, help="DART 조회 기간 (일)")
    args = parser.parse_args()
    result = build_alerts(Path(args.output), days=args.days)
    print(f"신규 {result['new']}건 (푸시 {result['pushed']}건) / 전체 {result['total']}건")

"""FDA 신약 허가 데이터 수집 — 국내 바이오기업 필터링.

openFDA drug applications API 를 조회해 한국 기업의 NDA/BLA/ANDA 허가 내역을
web/data/fda_approvals.json 으로 저장.

새 허가 감지 기준: approval_date 가 오늘부터 90일 이내 → is_new = True.
카카오 알림은 별도 cron 이 new_approvals 를 읽어 발송 예정.

실행: python -m batch.fda_approvals [--output web/data]
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

# openFDA drug applications API — 무료 (40 req/min, 1000 req/day)
FDA_BASE = "https://api.fda.gov/drug/drugsfda.json"
REQUEST_DELAY = 1.6  # API rate limit 보호 (40 req/min = 1.5s/req)
NEW_APPROVAL_DAYS = 90  # 최근 N일 이내 허가를 is_new=True 로 표시

# 국내 주요 바이오·제약기업 — (한국어명, 영문명, 종목코드, 분야, FDA 스폰서명 검색어)
KOREAN_BIO_COMPANIES: list[dict] = [
    {
        "name_ko": "셀트리온",
        "name_en": "Celltrion",
        "code": "068270",
        "sector": "바이오시밀러",
        "fda_queries": ["CELLTRION"],
    },
    {
        "name_ko": "삼성바이오에피스",
        "name_en": "Samsung Bioepis",
        "code": "207940",
        "sector": "바이오시밀러",
        "fda_queries": ["SAMSUNG BIOEPIS"],
    },
    {
        "name_ko": "SK바이오팜",
        "name_en": "SK Biopharmaceuticals",
        "code": "326030",
        "sector": "CNS 신약",
        "fda_queries": ["SK LIFE SCIENCE"],
    },
    {
        "name_ko": "휴젤",
        "name_en": "Hugel",
        "code": "145020",
        "sector": "보툴리눔 톡신",
        "fda_queries": ["HUGEL"],
    },
    {
        "name_ko": "한미약품",
        "name_en": "Hanmi Pharma",
        "code": "128940",
        "sector": "제약·바이오",
        "fda_queries": ["HANMI PHARM"],
    },
    {
        "name_ko": "대웅제약",
        "name_en": "Daewoong Pharmaceutical",
        "code": "069620",
        "sector": "제약",
        "fda_queries": ["DAEWOONG"],
    },
    {
        "name_ko": "메디톡스",
        "name_en": "Medytox",
        "code": "086900",
        "sector": "보툴리눔 톡신",
        "fda_queries": ["MEDYTOX"],
    },
    {
        "name_ko": "종근당",
        "name_en": "Chong Kun Dang",
        "code": "185750",
        "sector": "제약",
        "fda_queries": ["CHONG KUN DANG", "CKD PHARMA"],
    },
    {
        "name_ko": "보령",
        "name_en": "Boryung",
        "code": "003850",
        "sector": "제약",
        "fda_queries": ["BORYUNG"],
    },
    {
        "name_ko": "유한양행",
        "name_en": "Yuhan",
        "code": "000100",
        "sector": "제약",
        "fda_queries": ["YUHAN"],
    },
    {
        "name_ko": "동아에스티",
        "name_en": "Dong-A ST",
        "code": "170900",
        "sector": "제약",
        "fda_queries": ["DONG-A ST"],
    },
    {
        "name_ko": "에이치엘비",
        "name_en": "HLB",
        "code": "028300",
        "sector": "항암제",
        "fda_queries": ["ELEVAR THERAPEUTICS"],
    },
    {
        "name_ko": "오스코텍",
        "name_en": "Oscotec",
        "code": "039200",
        "sector": "항암제",
        "fda_queries": ["OSCOTEC"],
    },
    {
        "name_ko": "제넥신",
        "name_en": "Genexine",
        "code": "095700",
        "sector": "바이오의약품",
        "fda_queries": ["GENEXINE"],
    },
]


def _fetch_applications(query_term: str) -> list[dict]:
    """openFDA drug applications API 에서 스폰서명으로 결과 조회."""
    try:
        params = {
            "search": f'sponsor_name:"{query_term}"',
            "limit": 100,
        }
        r = requests.get(FDA_BASE, params=params, timeout=20)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json().get("results", [])
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return []
        logger.warning("FDA API '%s' HTTP 오류: %s", query_term, e)
        return []
    except Exception as e:
        logger.warning("FDA API '%s' 예외: %s", query_term, e)
        return []


def _parse_approval(app: dict) -> dict | None:
    """openFDA application dict → 정리된 허가 정보. ORIG AP 없으면 None."""
    app_num = app.get("application_number", "")
    if not app_num:
        return None

    if app_num.startswith("NDA"):
        app_type, numeric = "NDA", app_num[3:]
    elif app_num.startswith("BLA"):
        app_type, numeric = "BLA", app_num[3:]
    elif app_num.startswith("ANDA"):
        app_type, numeric = "ANDA", app_num[4:]
    else:
        app_type, numeric = "OTHER", app_num

    products = app.get("products", [])
    brand_name = generic_name = dosage_form = route = ""
    if products:
        p = products[0]
        brand_name = p.get("brand_name", "") or ""
        dosage_form = p.get("dosage_form", "") or ""
        route = p.get("route", "") or ""
        ingreds = p.get("active_ingredients") or []
        if ingreds:
            generic_name = ingreds[0].get("name", "") or ""

    # 최초 허가(ORIG AP) submission 찾기. 없으면 SUPPL AP 도 시도.
    subs = app.get("submissions") or []
    approval_sub = next(
        (s for s in subs
         if s.get("submission_status") == "AP"
         and s.get("submission_type") == "ORIG"),
        None,
    )
    if not approval_sub:
        approval_sub = next(
            (s for s in sorted(subs, key=lambda s: s.get("submission_status_date", ""))
             if s.get("submission_status") == "AP"),
            None,
        )
    if not approval_sub:
        return None  # 미허가

    raw_date = approval_sub.get("submission_status_date", "") or ""
    if len(raw_date) == 8:
        approval_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
    else:
        approval_date = raw_date

    is_new = False
    if approval_date:
        try:
            d = date.fromisoformat(approval_date)
            is_new = (date.today() - d).days <= NEW_APPROVAL_DAYS
        except ValueError:
            pass

    # 보충 허가(최신 SUPPL AP) 날짜도 수집 — 적응증 확대 등 트래킹용
    latest_suppl_date = ""
    for s in sorted(subs, key=lambda s: s.get("submission_status_date", ""), reverse=True):
        if s.get("submission_status") == "AP" and s.get("submission_type") == "SUPPL":
            rd = s.get("submission_status_date", "") or ""
            if len(rd) == 8:
                latest_suppl_date = f"{rd[:4]}-{rd[4:6]}-{rd[6:8]}"
            break

    fda_url = (
        "https://www.accessdata.fda.gov/scripts/cder/daf/"
        f"index.cfm?event=overview.process&ApplNo={numeric.zfill(6)}"
    )

    return {
        "app_number": app_num,
        "app_type": app_type,
        "brand_name": brand_name.title(),
        "generic_name": generic_name.lower(),
        "dosage_form": dosage_form,
        "route": route,
        "approval_date": approval_date,
        "latest_suppl_date": latest_suppl_date,
        "is_new": is_new,
        "fda_url": fda_url,
    }


def _collect_company(company: dict) -> dict:
    """한 회사의 FDA 허가 데이터 수집 → 정리된 dict."""
    seen: set[str] = set()
    approvals: list[dict] = []

    for query in company["fda_queries"]:
        time.sleep(REQUEST_DELAY)
        apps = _fetch_applications(query)
        for app in apps:
            num = app.get("application_number", "")
            if num in seen:
                continue
            seen.add(num)
            parsed = _parse_approval(app)
            if parsed:
                approvals.append(parsed)

    approvals.sort(key=lambda a: a.get("approval_date", ""), reverse=True)

    latest = approvals[0]["approval_date"] if approvals else None
    new_count = sum(1 for a in approvals if a.get("is_new"))

    return {
        "name_ko": company["name_ko"],
        "name_en": company["name_en"],
        "code": company["code"],
        "sector": company.get("sector", ""),
        "approvals": approvals,
        "total_approvals": len(approvals),
        "latest_approval": latest,
        "new_count": new_count,
    }


def build_fda(output_dir: Path) -> bool:
    """FDA 허가 데이터 수집 → output_dir/fda_approvals.json."""
    companies_data: list[dict] = []
    new_approvals: list[dict] = []

    for company in KOREAN_BIO_COMPANIES:
        logger.info("FDA 수집: %s (%s)", company["name_ko"], company["fda_queries"])
        result = _collect_company(company)
        companies_data.append(result)

        for app in result["approvals"]:
            if app.get("is_new"):
                new_approvals.append({
                    "company_ko": company["name_ko"],
                    "company_en": company["name_en"],
                    "code": company["code"],
                    **app,
                })
        logger.info(
            "  %s: 허가 %d건 (신규 %d건)",
            company["name_ko"], result["total_approvals"], result["new_count"],
        )

    # 최근 허가 순 정렬
    companies_data.sort(
        key=lambda c: c.get("latest_approval") or "0000-00-00",
        reverse=True,
    )

    total_approvals = sum(c["total_approvals"] for c in companies_data)
    companies_with_approvals = sum(1 for c in companies_data if c["total_approvals"] > 0)

    payload = {
        "updated": datetime.now(KST).replace(microsecond=0).isoformat(),
        "companies": companies_data,
        "new_approvals": new_approvals,
        "total_companies": len(companies_data),
        "total_companies_with_approvals": companies_with_approvals,
        "total_approvals": total_approvals,
    }

    out = output_dir / "fda_approvals.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "wrote %s (기업=%d, 허가=%d, 신규=%d)",
        out, len(companies_data), total_approvals, len(new_approvals),
    )
    return True


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="FDA 허가 데이터 수집")
    parser.add_argument("--output", default="web/data")
    args = parser.parse_args()
    build_fda(Path(args.output))

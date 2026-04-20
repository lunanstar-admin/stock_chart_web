"""일일 배치 메인 엔트리.

매일 장마감 후 실행:
  python -m batch.run_batch [--limit N] [--workers N] [--output DIR]

생성 파일:
  {output}/meta.json             — 전체 요약
  {output}/stocks.json           — 종목 리스트
  {output}/chart/{code}.json     — 종목별 차트 + 지표 + 수급 + 메타
"""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import socket
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 네트워크 hang 방지 — 모든 socket 호출에 30s 타임아웃 적용.
# fdr / pykrx / requests 모두 socket 레벨에서 블록된다.
socket.setdefaulttimeout(30)

from batch.collectors import (
    chart_records,
    compute_indicators,
    fetch_company_info,
    fetch_market_listing,
    fetch_meta,
    fetch_ohlcv,
    resample_ohlcv,
)
from batch.supply import fetch_investor
from batch.writers import write_json

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def _now_kst_iso() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def _process_stock(stock: dict, output_dir: Path) -> tuple[str, bool, str]:
    code = stock["code"]
    try:
        # 일봉은 120개만 보여주지만, 월봉(120개 ≈ 10년) 리샘플 위해 넉넉히 수집
        raw = fetch_ohlcv(code, days=120 * 31)
        if raw.empty:
            return code, False, "empty_ohlcv"

        # 1) 일봉 지표 (최근 120일)
        daily = compute_indicators(raw)
        data = chart_records(daily, tail=120)
        if not data:
            return code, False, "no_chart_records"

        # 2) 주봉 (금요일 종료, 최근 120주 ≈ 2.3년)
        try:
            w_raw = resample_ohlcv(raw, "W-FRI")
            w = compute_indicators(w_raw) if not w_raw.empty else w_raw
            data_w = chart_records(w, tail=120)
        except Exception as e:
            logger.debug("weekly resample failed %s: %s", code, e)
            data_w = []

        # 3) 월봉 (월말, 최근 120개월 ≈ 10년)
        try:
            m_raw = resample_ohlcv(raw, "ME")
            m = compute_indicators(m_raw) if not m_raw.empty else m_raw
            data_m = chart_records(m, tail=120)
        except Exception as e:
            logger.debug("monthly resample failed %s: %s", code, e)
            data_m = []

        investor = fetch_investor(code, days=60)
        meta = fetch_meta(code)

        # 회사 기본정보 (실패해도 종목 처리 자체는 계속)
        try:
            company = fetch_company_info(code)
            if company:
                meta["company"] = company
        except Exception as e:
            logger.debug("company_info failed %s: %s", code, e)

        # stocks.json의 시장 스냅샷도 meta에 포함 (프론트 편의)
        meta.update({
            "name": stock.get("name", ""),
            "market": stock.get("market", ""),
            "price": stock.get("price", ""),
            "change": stock.get("change", ""),
            "changeRate": stock.get("changeRate", ""),
            "changeDir": stock.get("changeDir", ""),
            "volume": stock.get("volume", ""),
            "marketCap": stock.get("marketCap", ""),
        })

        payload = {
            "code": code,
            "name": stock.get("name", code),
            "updated": _now_kst_iso(),
            "data": data,
            "dataW": data_w,
            "dataM": data_m,
            "investor": investor,
            "meta": meta,
        }
        write_json(output_dir / "chart" / f"{code}.json", payload)
        return code, True, ""
    except Exception as e:
        logger.warning("process failed %s: %s", code, e)
        return code, False, str(e)[:120]


def run(output_dir: Path, limit: int | None, workers: int) -> None:
    t0 = time.time()
    logger.info("=== batch start @ %s (output=%s) ===", _now_kst_iso(), output_dir)

    # 1. 종목 리스트 수집
    kospi = fetch_market_listing("KOSPI")
    kosdaq = fetch_market_listing("KOSDAQ")
    all_stocks = kospi + kosdaq
    if limit:
        all_stocks = all_stocks[:limit]
        logger.info("limited to %d stocks", limit)

    stocks_payload = {
        "updated": _now_kst_iso(),
        "count": len(all_stocks),
        "markets": {
            "KOSPI": len(kospi),
            "KOSDAQ": len(kosdaq),
        },
        "stocks": all_stocks,
    }
    write_json(output_dir / "stocks.json", stocks_payload)
    logger.info("wrote stocks.json (%d stocks)", len(all_stocks))

    # 2. 개별 종목 처리
    ok_count = 0
    fail_count = 0
    failures: list[tuple[str, str]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_process_stock, s, output_dir): s["code"] for s in all_stocks}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            code, ok, err = fut.result()
            if ok:
                ok_count += 1
            else:
                fail_count += 1
                failures.append((code, err))
            if i % 100 == 0 or i == len(all_stocks):
                logger.info("progress %d/%d (ok=%d, fail=%d)", i, len(all_stocks), ok_count, fail_count)

    # 3. 메타 파일
    meta_payload = {
        "updated": _now_kst_iso(),
        "elapsed_sec": round(time.time() - t0, 1),
        "counts": {
            "total": len(all_stocks),
            "success": ok_count,
            "failed": fail_count,
        },
        "markets": {"KOSPI": len(kospi), "KOSDAQ": len(kosdaq)},
        "failed_samples": failures[:20],
    }
    write_json(output_dir / "meta.json", meta_payload)
    logger.info("=== batch done in %.1fs (ok=%d, fail=%d) ===",
                time.time() - t0, ok_count, fail_count)

    # 4. 일간 포스트 생성 + 블로그 정적 빌드 (실패해도 배치 자체는 성공으로 본다)
    try:
        from batch import daily_post
        daily_post.generate()
    except Exception as e:
        logger.warning("daily_post.generate 실패(무시): %s", e)

    try:
        from batch import build_blog
        build_blog.build()
    except Exception as e:
        logger.warning("build_blog.build 실패(무시): %s", e)


def main() -> None:
    parser = argparse.ArgumentParser(description="차트연구 일일 배치")
    parser.add_argument("--output", default="web/data", help="출력 디렉토리")
    parser.add_argument("--limit", type=int, default=None, help="처리할 종목 수 상한 (디버그용)")
    parser.add_argument("--workers", type=int, default=8, help="병렬 워커 수")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    run(output_dir, limit=args.limit, workers=args.workers)


if __name__ == "__main__":
    main()

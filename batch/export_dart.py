"""DART 공시 정적 데이터 export.

데이터 흐름:
  surge_detector data/ticks.sqlite (dart_news)
    → stock_chart_web/web/data/dart/disclosures.json (검색 인덱스)
    → stock_chart_web/web/data/dart/{rcept_no}.json (상세 — LLM 요약 + 주가영향)

배포 후 https://secomdal.com/dart/ 정적 페이지가 이 JSON을 fetch.
Vercel CDN이 캐시 — 매일 1회 commit해서 갱신.

사용:
  python -m batch.export_dart                                    # 기본 (최근 90일)
  python -m batch.export_dart --days 30
  python -m batch.export_dart --src /path/to/ticks.sqlite
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
_KST = ZoneInfo("Asia/Seoul")

DEFAULT_SRC = "/Users/kimkihong/Project_AI/surge_detector/data/ticks.sqlite"
DEFAULT_DST = Path(__file__).resolve().parent.parent / "web" / "data" / "dart"


def export(src: str, dst: Path, days: int, limit: int) -> dict:
    """dart_news + disclosure_price_impacts → JSON.

    - disclosures.json: 검색 인덱스 (가벼운 필드만, 정렬: 최근순)
    - {rcept_no}.json: 개별 상세 (LLM 요약 + key_figures + 주가영향)
    """
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "detail").mkdir(exist_ok=True)

    since_epoch = time.time() - days * 86400
    conn = sqlite3.connect(src)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT * FROM dart_news
           WHERE ts_epoch >= ?
           ORDER BY ts_epoch DESC LIMIT ?""",
        (since_epoch, limit),
    ).fetchall()
    logger.info(f"dart_news rows: {len(rows)}")

    impact_rows = {
        r["rcept_no"]: dict(r)
        for r in conn.execute(
            "SELECT * FROM disclosure_price_impacts WHERE base_date >= ?",
            ((datetime.now(_KST).replace(hour=0, minute=0, second=0)).strftime("%Y%m%d"),),
        ).fetchall()
    }
    # 기간 무관하게 전부 (impact는 기간이 짧지 않으므로)
    impact_rows = {
        r["rcept_no"]: dict(r)
        for r in conn.execute("SELECT * FROM disclosure_price_impacts").fetchall()
    }

    index_items = []
    for r in rows:
        rec = dict(r)
        # 가벼운 검색 인덱스 (전체 fetch해도 가벼움)
        idx = {
            "rcept_no": rec["rcept_no"],
            "ts_epoch": rec["ts_epoch"],
            "code": rec["code"],
            "name": rec["name"],
            "report_nm": rec["report_nm"],
            "sentiment": rec["sentiment"],
            "confidence": rec["confidence"],
            "url": rec["url"],
            "has_summary": bool(rec.get("llm_at")),
            "summary_short": rec.get("summary_short"),
        }
        index_items.append(idx)

        # 상세 파일 — LLM 요약이 있거나 영향 데이터가 있을 때만
        impact = impact_rows.get(rec["rcept_no"])
        if rec.get("llm_at") or impact:
            detail = {
                **rec,
                "key_figures": (
                    json.loads(rec["key_figures"]) if rec.get("key_figures") else None
                ),
                "impact": impact,
            }
            (dst / "detail" / f"{rec['rcept_no']}.json").write_text(
                json.dumps(detail, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

    # 검색 인덱스 — 최근순으로 정렬됨
    index = {
        "generated_at": datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "days_window": days,
        "total": len(index_items),
        "items": index_items,
    }
    index_path = dst / "disclosures.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, default=str), encoding="utf-8"
    )

    # 통계 (보고서 타입별 평균 영향)
    stats = conn.execute(
        """SELECT dn.report_nm, dn.sentiment,
                  COUNT(*) AS n,
                  AVG(dpi.ret_t0)  AS avg_t0,
                  AVG(dpi.ret_t5)  AS avg_t5,
                  AVG(dpi.ret_t20) AS avg_t20
             FROM disclosure_price_impacts dpi
             JOIN dart_news dn ON dn.rcept_no = dpi.rcept_no
            WHERE dpi.ret_t0 IS NOT NULL OR dpi.ret_t5 IS NOT NULL
            GROUP BY dn.report_nm, dn.sentiment
           HAVING n >= 3 ORDER BY n DESC LIMIT 200"""
    ).fetchall()
    (dst / "stats.json").write_text(
        json.dumps(
            {"generated_at": index["generated_at"], "items": [dict(r) for r in stats]},
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    conn.close()
    size_kb = index_path.stat().st_size // 1024
    logger.info(f"✅ disclosures.json: {len(index_items)} items, {size_kb} KB")
    logger.info(f"✅ detail/*.json: {len(list((dst/'detail').glob('*.json')))} files")
    logger.info(f"✅ stats.json: {len(stats)} report types")
    return {"items": len(index_items), "kb": size_kb, "stats": len(stats)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", default=DEFAULT_SRC, help="surge_detector ticks.sqlite 경로")
    p.add_argument("--dst", default=str(DEFAULT_DST), help="출력 디렉토리")
    p.add_argument("--days", type=int, default=90, help="최근 N일 (default 90)")
    p.add_argument("--limit", type=int, default=5000, help="최대 row")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    export(args.src, Path(args.dst), days=args.days, limit=args.limit)


if __name__ == "__main__":
    main()

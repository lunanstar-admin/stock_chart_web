"""
재벌 가계도 + 그룹사 관계도 데이터 수집 파이프라인.

매월 첫 토요일 GitHub Actions 가 실행. 로컬에서도 수동 실행 가능.

플로우:
  1) schema/create_db.py        — SQLite 스키마 생성 (없으면)
  2) collectors/01_company_list — KRX 종목 목록 (전종목, 빠름)
  3) collectors/04_shareholders_dividends --kospi200  (DART, 200 종목 × 1~3 호출)
  4) collectors/07_subsidiaries --kospi200            (DART, 200 종목 × 1~2 호출)
  5) collectors/08_group_inference                    (로컬 처리, 빠름)
  6) collectors/09_chaebol_family                     (data_md/chaebol_family.md)
  7) batch/export_chaebol --output web/data           (SQLite → JSON 2개)

환경변수:
  STOCK_DB        — DB 파일 경로 (기본: data/stock_db.sqlite)
  DART_API_KEY    — DART OpenAPI 키 (기본: base.py 의 fallback 사용)
  CHAEBOL_MD      — 가계도 마크다운 경로 (기본: data_md/chaebol_family.md)
  PIPELINE_LIMIT  — 4·7 단계의 종목 수 상한 (기본: --kospi200, 200 종목)
  SKIP_PHASES     — 건너뛸 단계 번호 콤마구분 (예: "1,4,7" — 1,4,7 단계 스킵)

사용법:
  python3 -m batch.run_chaebol_pipeline
  PIPELINE_LIMIT=50 python3 -m batch.run_chaebol_pipeline    # 디버그용 50종목
  SKIP_PHASES=4,7 python3 -m batch.run_chaebol_pipeline      # 빠른 export 만
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLLECTORS = ROOT / "collectors"
SCHEMA = ROOT / "schema"


def run_step(label: str, script: Path, args: list[str] | None = None) -> int:
    args = args or []
    print(f"\n{'=' * 60}")
    print(f"▶ {label}")
    print(f"  {script.name} {' '.join(args)}")
    print('=' * 60)
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, str(script)] + args,
        cwd=str(ROOT),
    )
    elapsed = time.time() - t0
    print(f"  완료 {elapsed:.1f}s  (exit={proc.returncode})")
    return proc.returncode


def parse_skip(env: str | None) -> set[int]:
    if not env:
        return set()
    out = set()
    for tok in env.split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.add(int(tok))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="재벌·그룹사 데이터 수집 파이프라인")
    parser.add_argument("--limit", type=int, default=None,
                        help="04·07 단계 종목 수 상한 (기본: --kospi200 사용)")
    parser.add_argument("--skip", default=os.environ.get("SKIP_PHASES", ""),
                        help="건너뛸 단계 번호 콤마구분 (예: 1,4)")
    args = parser.parse_args()

    skip = parse_skip(args.skip)
    limit_arg: list[str]
    if args.limit:
        limit_arg = ["--limit", str(args.limit)]
    elif os.environ.get("PIPELINE_LIMIT"):
        limit_arg = ["--limit", os.environ["PIPELINE_LIMIT"]]
    else:
        limit_arg = ["--kospi200"]

    pipeline_t0 = time.time()
    print(f"파이프라인 시작 · ROOT={ROOT}")
    print(f"DART 호출 단계 인자: {' '.join(limit_arg)}")
    if skip:
        print(f"건너뛸 단계: {sorted(skip)}")

    # 1. 스키마 생성
    if 1 not in skip:
        rc = run_step("Phase 1 — 스키마 생성", SCHEMA / "create_db.py")
        if rc != 0:
            print("⚠️ 스키마 생성 실패. 중단.")
            return 1

    # 2. 종목 목록 (KRX, 빠름)
    if 2 not in skip:
        run_step("Phase 2 — 종목 목록 (KRX)", COLLECTORS / "01_company_list.py")

    # 3. 주주·배당 (DART, KOSPI200)
    if 3 not in skip:
        run_step(
            "Phase 3 — 주주·배당 (DART, " + (limit_arg[0] if limit_arg[0] != "--kospi200" else "KOSPI200") + ")",
            COLLECTORS / "04_shareholders_dividends.py",
            limit_arg,
        )

    # 4. 자회사 (DART, KOSPI200)
    if 4 not in skip:
        run_step(
            "Phase 4 — 자회사 (DART)",
            COLLECTORS / "07_subsidiaries.py",
            limit_arg,
        )

    # 5. 그룹 추론 (로컬)
    if 5 not in skip:
        run_step("Phase 5 — 그룹 추론", COLLECTORS / "08_group_inference.py")

    # 6. 가계도 (Obsidian 마크다운)
    if 6 not in skip:
        run_step("Phase 6 — 가계도 (마크다운 → DB)", COLLECTORS / "09_chaebol_family.py")

    # 7. JSON export
    if 7 not in skip:
        rc = run_step(
            "Phase 7 — JSON export (chaebol.json + chaebol-codes.json)",
            ROOT / "batch" / "export_chaebol.py",
        )
        if rc != 0:
            print("⚠️ export 실패")
            return 1

    elapsed = time.time() - pipeline_t0
    print(f"\n{'=' * 60}")
    print(f"✅ 파이프라인 완료 · 총 {elapsed / 60:.1f}분 ({elapsed:.0f}s)")
    print('=' * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

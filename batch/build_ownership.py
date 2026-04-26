"""stock_db SQLite → secomdal.com 정적 계열사 관계 JSON.

매일 또는 수동 실행:
  python -m batch.build_ownership

입력:
  ~/Project_AI/stock_db/data/stock_db.sqlite

출력:
  web/data/ownership.json   - 회사·자회사·그룹 정보 통합
"""

from __future__ import annotations
import json, os, sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path.home() / 'Project_AI/stock_db/data/stock_db.sqlite'
OUT_PATH = ROOT / 'web/data/ownership.json'

# 페이지 로딩 속도 위해 의미있는 출자만 (5%↑) — 단순투자 노이즈 제외
MIN_PCT = 5.0


def build():
    if not DB_PATH.exists():
        raise SystemExit(f'❌ stock_db 없음: {DB_PATH}')

    conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 회사 (KOSPI/KOSDAQ 전체)
    companies = []
    for r in c.execute("""
        SELECT code, name, market, market_cap, market_cap_rank, group_name, is_kospi200
        FROM companies
        WHERE corp_code IS NOT NULL AND corp_code != ''
        ORDER BY market_cap_rank ASC
    """):
        companies.append({
            'code': r['code'],
            'name': r['name'],
            'market': r['market'],
            'cap': r['market_cap'] or 0,
            'rank': r['market_cap_rank'] or 99999,
            'group': r['group_name'] or None,
            'k200': bool(r['is_kospi200']),
        })

    # 자회사 (5% 이상)
    subs = []
    for r in c.execute("""
        SELECT parent_code, parent_name, sub_name, sub_code, ownership_pct, book_value, investment_purpose
        FROM subsidiaries
        WHERE ownership_pct >= ?
    """, (MIN_PCT,)):
        subs.append({
            'p': r['parent_code'],
            'pn': r['parent_name'],
            'sn': r['sub_name'],
            'sc': r['sub_code'],
            'pct': round(r['ownership_pct'], 2) if r['ownership_pct'] is not None else None,
            'bv': r['book_value'] or 0,
            'pur': r['investment_purpose'],
        })

    # 그룹 정보
    groups = []
    for r in c.execute("""
        SELECT bg.group_name, bg.representative_company,
               COUNT(DISTINCT gm.code) as listed_count
        FROM business_groups bg
        LEFT JOIN group_member_companies gm
          ON bg.group_name = gm.group_name AND gm.code IS NOT NULL
        GROUP BY bg.group_name
        ORDER BY listed_count DESC
    """):
        groups.append({
            'name': r['group_name'],
            'rep': r['representative_company'],
            'listed': r['listed_count'] or 0,
        })

    out = {
        'updated': datetime.now().isoformat(timespec='seconds'),
        'min_pct': MIN_PCT,
        'count_companies': len(companies),
        'count_subsidiaries': len(subs),
        'count_groups': len(groups),
        'companies': companies,
        'subsidiaries': subs,
        'groups': groups,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8'
    )
    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f'✅ {OUT_PATH} 생성 ({size_mb:.2f} MB)')
    print(f'   회사 {len(companies)}, 자회사 {len(subs)}, 그룹 {len(groups)}')

    conn.close()


if __name__ == '__main__':
    build()

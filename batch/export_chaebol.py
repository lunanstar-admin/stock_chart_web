"""
재벌 가계도 + 그룹사 관계도 데이터 export (월 1회).

소스: ~/Project_AI/stock_db/data/stock_db.sqlite
출력:
  web/data/chaebol.json         — 가계도 (인물·관계·인물↔회사)
                                  + 그룹 + 그룹별 회원사 (~150KB)
  web/data/chaebol-codes.json   — 종목코드 → {group, subsidiaries, shareholders}
                                  차트 모달의 "자회사·계열사·관계사" 표기용 인덱스 (~250KB)

사용법:
  python3 -m batch.export_chaebol            # 기본 — DB 자동 탐색
  python3 -m batch.export_chaebol --db PATH  # 명시적 DB 경로
  python3 -m batch.export_chaebol --output DIR

매월 1일 1회 실행 권장. 가계도/계열사 정보는 자주 변하지 않음.
실행 후 git commit 으로 web/data/chaebol*.json 변경 사항 push.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))

DEFAULT_DB_CANDIDATES = [
    Path.home() / "Project_AI" / "stock_db" / "data" / "stock_db.sqlite",
    Path.home() / "Project_AI" / "stock_db.sqlite",
]


def now_iso_kst() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def find_db(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p
        sys.exit(f"❌ DB 파일이 존재하지 않음: {p}")
    for p in DEFAULT_DB_CANDIDATES:
        if p.exists():
            return p
    sys.exit(
        "❌ stock_db.sqlite 를 찾을 수 없음. "
        f"--db PATH 로 명시하거나 다음 중 한 곳에 두세요:\n  "
        + "\n  ".join(str(p) for p in DEFAULT_DB_CANDIDATES)
    )


def fetch_persons(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("""
        SELECT id, name, name_alt, birth_year, death_year, gender,
               group_name, generation, role, notes
        FROM chaebol_persons
        ORDER BY group_name, generation, birth_year
    """).fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "nameAlt": r[2] or None,
            "birth": r[3],
            "death": r[4],
            "gender": r[5] or None,
            "group": r[6] or None,
            "gen": r[7],
            "role": r[8] or None,
            "notes": r[9] or None,
        }
        for r in rows
    ]


def fetch_family_relations(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("""
        SELECT from_id, to_id, rel_type, COALESCE(is_divorced, 0)
        FROM family_relations
        ORDER BY from_id, rel_type
    """).fetchall()
    return [
        {"from": r[0], "to": r[1], "type": r[2], "divorced": bool(r[3])}
        for r in rows
    ]


def fetch_person_company_links(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("""
        SELECT person_id, code, company_name, role, ownership_pct
        FROM person_company_links
        ORDER BY person_id
    """).fetchall()
    return [
        {
            "person": r[0],
            "code": r[1] or None,
            "company": r[2] or None,
            "role": r[3] or None,
            "pct": round(float(r[4]), 2) if r[4] is not None else None,
        }
        for r in rows
    ]


def fetch_groups(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("""
        SELECT group_name, group_code, representative_company,
               total_companies, total_assets, rank, designated_date
        FROM business_groups
        ORDER BY rank IS NULL, rank, group_name
    """).fetchall()
    return [
        {
            "name": r[0],
            "code": r[1] or None,
            "rep": r[2] or None,
            "total": r[3],
            "assets": r[4],
            "rank": r[5],
            "designated": r[6] or None,
        }
        for r in rows
    ]


def fetch_group_members(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("""
        SELECT group_name, company_name, code,
               COALESCE(is_listed, 0), COALESCE(is_representative, 0)
        FROM group_member_companies
        ORDER BY group_name, is_representative DESC, is_listed DESC, company_name
    """).fetchall()
    return [
        {
            "group": r[0],
            "name": r[1],
            "code": r[2] or None,
            "listed": bool(r[3]),
            "rep": bool(r[4]),
        }
        for r in rows
    ]


def fetch_subsidiaries_clean(con: sqlite3.Connection) -> list[dict]:
    """ownership_pct 가 있는 의미 있는 자회사만. '합계' 행 등 제외."""
    rows = con.execute("""
        SELECT parent_code, parent_name, sub_name, sub_code, ownership_pct
        FROM subsidiaries
        WHERE parent_code IS NOT NULL AND parent_code != ''
          AND sub_name IS NOT NULL AND sub_name != ''
          AND sub_name NOT IN ('합계', '소계', '계')
          AND ownership_pct IS NOT NULL
          AND bsns_year = (SELECT MAX(bsns_year) FROM subsidiaries)
        ORDER BY parent_code, ownership_pct DESC
    """).fetchall()
    return [
        {
            "parent": r[0],
            "parentName": r[1],
            "name": r[2],
            "code": r[3] or None,
            "pct": round(float(r[4]), 2) if r[4] is not None else None,
        }
        for r in rows
    ]


def fetch_shareholders_top(con: sqlite3.Connection, top_n: int = 5) -> dict:
    """종목별 상위 주주 N명만 export (전체는 너무 크다 — 26K건)."""
    # 최신 보고연도 기준
    cur = con.execute("SELECT MAX(report_year) FROM shareholders")
    latest_year = cur.fetchone()[0]
    rows = con.execute("""
        SELECT code, shareholder_name, relation, ownership_pct
        FROM shareholders
        WHERE report_year = ?
          AND ownership_pct IS NOT NULL
          AND ownership_pct >= 0.5
        ORDER BY code, ownership_pct DESC
    """, (latest_year,)).fetchall()
    by_code: dict[str, list[dict]] = {}
    for r in rows:
        code = r[0]
        if code not in by_code:
            by_code[code] = []
        if len(by_code[code]) >= top_n:
            continue
        by_code[code].append({
            "name": r[1],
            "rel": r[2] or None,
            "pct": round(float(r[3]), 2),
        })
    return by_code


def build_codes_index(
    group_members: list[dict],
    subsidiaries: list[dict],
    shareholders_by_code: dict,
) -> dict:
    """종목코드 → 그룹/자회사/주주 정보 인덱스. 차트 모달의 '자회사·계열사·관계사' 표기용."""

    # code → group
    code_to_group: dict[str, str] = {}
    group_codes: dict[str, list[str]] = {}  # group → [codes]
    for m in group_members:
        if m["code"] and m["listed"]:
            code_to_group[m["code"]] = m["group"]
            group_codes.setdefault(m["group"], []).append(m["code"])

    # code → 자회사 리스트 (parent_code 기준)
    parent_to_subs: dict[str, list[dict]] = {}
    for s in subsidiaries:
        if s["parent"]:
            parent_to_subs.setdefault(s["parent"], []).append({
                "name": s["name"],
                "code": s["code"],
                "pct": s["pct"],
            })

    # code → 모회사 (자기가 자회사로 등장하는 케이스)
    sub_to_parent: dict[str, dict] = {}
    for s in subsidiaries:
        if s["code"]:
            sub_to_parent[s["code"]] = {
                "code": s["parent"],
                "name": s["parentName"],
                "pct": s["pct"],
            }

    out: dict[str, dict] = {}
    # 그룹/자회사/모회사가 있는 모든 코드 union
    all_codes = set(code_to_group.keys()) | set(parent_to_subs.keys()) | set(sub_to_parent.keys())
    for code in all_codes:
        entry: dict = {}
        if code in code_to_group:
            grp = code_to_group[code]
            entry["group"] = grp
            # 같은 그룹 다른 회사 (계열사) — 상위 8개만, 자기 자신 제외
            siblings = [c for c in group_codes.get(grp, []) if c != code][:8]
            entry["affiliates"] = siblings
        if code in parent_to_subs:
            entry["subsidiaries"] = parent_to_subs[code][:10]
        if code in sub_to_parent:
            entry["parent"] = sub_to_parent[code]
        out[code] = entry
    return out


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="재벌 가계도/관계도 데이터 export")
    parser.add_argument("--db", help="stock_db.sqlite 경로 (기본: 자동 탐색)")
    parser.add_argument(
        "--output", default="web/data",
        help="출력 디렉토리 (기본: web/data, 결과는 chaebol.json + chaebol-codes.json)"
    )
    args = parser.parse_args()

    db_path = find_db(args.db)
    out_dir = Path(args.output)
    print(f"[chaebol] DB={db_path}")
    print(f"[chaebol] OUT={out_dir.resolve()}")

    con = sqlite3.connect(str(db_path))
    try:
        persons = fetch_persons(con)
        family = fetch_family_relations(con)
        links = fetch_person_company_links(con)
        groups = fetch_groups(con)
        members = fetch_group_members(con)
        subs = fetch_subsidiaries_clean(con)
        shareholders = fetch_shareholders_top(con, top_n=5)
    finally:
        con.close()

    chaebol = {
        "updated": now_iso_kst(),
        "counts": {
            "persons": len(persons),
            "family": len(family),
            "personLinks": len(links),
            "groups": len(groups),
            "groupMembers": len(members),
            "subsidiaries": len(subs),
        },
        "persons": persons,
        "family": family,
        "personLinks": links,
        "groups": groups,
        "groupMembers": members,
    }

    codes_index = build_codes_index(members, subs, shareholders)
    # 인덱스에 주주 정보도 합치기
    for code, lst in shareholders.items():
        codes_index.setdefault(code, {})["shareholders"] = lst

    chaebol_path = out_dir / "chaebol.json"
    codes_path = out_dir / "chaebol-codes.json"

    write_json(chaebol_path, chaebol)
    write_json(codes_path, codes_index)

    chaebol_size = chaebol_path.stat().st_size
    codes_size = codes_path.stat().st_size
    print(f"[chaebol] {chaebol_path}  ({chaebol_size:,} bytes)")
    print(f"[chaebol] {codes_path}  ({codes_size:,} bytes)")
    print(f"[chaebol] persons={len(persons)} family={len(family)} groups={len(groups)} "
          f"members={len(members)} subs={len(subs)} shareholders={len(shareholders)} codes")


if __name__ == "__main__":
    main()

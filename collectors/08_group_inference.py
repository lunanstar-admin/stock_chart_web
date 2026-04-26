"""
Step 8: 자회사 트리로부터 기업집단(그룹) 추론
- 다른 회사가 자회사로 갖지 않는 회사 = 그룹 head 후보
- head로부터 BFS로 모든 (직간접) 자회사 = 그룹 멤버
- 한국 주요 재벌 그룹 별칭 매핑 (삼성, SK, LG, 현대차, 롯데 등)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from base import get_conn, now_str, log

from collections import defaultdict, deque

# 주요 그룹 head (수동 정의 + 보완)
KOREAN_CHAEBOL_HEADS = {
    '삼성그룹':       ['삼성생명보험', '삼성물산', '삼성전자'],
    'SK그룹':        ['SK', 'SK스퀘어', 'SK이노베이션'],
    'LG그룹':        ['LG', 'LG전자'],
    '현대자동차그룹':   ['현대자동차', '현대차'],
    '롯데그룹':       ['롯데지주'],
    '포스코그룹':     ['POSCO홀딩스', 'POSCO홀딩스(주)'],
    '한화그룹':       ['한화', '(주)한화'],
    'GS그룹':        ['(주)GS', 'GS'],
    'HD현대그룹':     ['HD현대'],
    '신세계그룹':     ['이마트', '신세계'],
    '두산그룹':       ['(주)두산', '두산'],
    'CJ그룹':        ['CJ', 'CJ㈜'],
    '한진그룹':       ['한진칼'],
    '카카오그룹':     ['카카오'],
    '네이버그룹':     ['네이버', 'NAVER'],
    '효성그룹':       ['(주)효성', '효성'],
    'KT그룹':        ['KT', '(주)KT'],
    '대림그룹':       ['DL', 'DL이앤씨'],
    '한국타이어그룹':  ['한국앤컴퍼니'],
    '대한항공그룹':   ['한진칼', '대한항공'],
    '미래에셋그룹':   ['미래에셋증권', '미래에셋캐피탈'],
    '교보생명그룹':   ['교보생명보험'],
    '농협그룹':       ['농협경제지주'],
    '오리온그룹':     ['오리온홀딩스'],
    '한미약품그룹':   ['한미사이언스'],
    '동원그룹':       ['동원산업'],
    '코오롱그룹':     ['코오롱'],
    'OCI그룹':       ['OCI홀딩스'],
    '아모레퍼시픽그룹':['아모레퍼시픽그룹', '아모레퍼시픽'],
    'CS그룹':        ['CS홀딩스'],
}


def normalize(name):
    if not name: return ''
    return name.replace('㈜', '').replace('(주)', '').replace(' ', '').strip()


def main():
    conn = get_conn()
    c = conn.cursor()

    # 1) 자회사 그래프 구성 (parent → children with ownership)
    log.info("=== 자회사 그래프 구성 ===")
    parent_to_subs = defaultdict(list)   # parent_corp_code → [(sub_name, sub_code, sub_corp_code, pct)]
    sub_to_parents = defaultdict(list)   # sub_name(normalized) → [parent_name]

    rows = c.execute("""
        SELECT parent_name, parent_corp_code, sub_name, sub_code, ownership_pct, book_value
        FROM subsidiaries
        WHERE ownership_pct >= 20
    """).fetchall()
    log.info(f"지분 20%↑ 자회사 관계: {len(rows)}건")

    for r in rows:
        parent_name, parent_corp, sub_name, sub_code, pct, bv = r
        parent_to_subs[parent_corp].append({
            'sub_name': sub_name,
            'sub_code': sub_code,
            'pct': pct,
            'book_value': bv,
        })
        sub_to_parents[normalize(sub_name)].append(parent_name)

    # 2) 그룹 head별 BFS로 멤버 수집
    log.info("=== 그룹 멤버 매핑 ===")
    name_to_corp_code = {}
    name_to_code = {}
    for r in c.execute("SELECT code, name, corp_code FROM companies"):
        norm = normalize(r[1])
        name_to_corp_code[norm] = r[2]
        name_to_code[norm] = r[0]

    # 기존 그룹 데이터 클리어
    c.execute("DELETE FROM group_member_companies WHERE source='dart_inference'")
    c.execute("DELETE FROM business_groups WHERE source='dart_inference'")

    total_members = 0
    for group_name, head_candidates in KOREAN_CHAEBOL_HEADS.items():
        members = {}  # name → {pct, code, depth, parent}
        visited_corps = set()

        # head들로 시작
        queue = deque()
        for head in head_candidates:
            norm = normalize(head)
            head_corp = name_to_corp_code.get(norm)
            head_code = name_to_code.get(norm)
            if head_corp:
                members[head] = {'pct': 100, 'code': head_code, 'depth': 0, 'parent': None}
                queue.append((head_corp, head, 0))
                visited_corps.add(head_corp)

        # BFS - 자회사 트리 탐색 (최대 depth 3)
        while queue:
            cur_corp, cur_name, depth = queue.popleft()
            if depth >= 3:
                continue
            for sub in parent_to_subs.get(cur_corp, []):
                sub_name = sub['sub_name']
                sub_code = sub['sub_code']
                sub_corp = None
                if sub_code:
                    norm_sub = normalize(sub_name)
                    sub_corp = name_to_corp_code.get(norm_sub)
                # 그룹 멤버로 추가
                if sub_name not in members:
                    members[sub_name] = {
                        'pct': sub['pct'], 'code': sub_code,
                        'depth': depth + 1, 'parent': cur_name
                    }
                # 자회사의 자회사 탐색
                if sub_corp and sub_corp not in visited_corps:
                    visited_corps.add(sub_corp)
                    queue.append((sub_corp, sub_name, depth + 1))

        # DB 저장
        for member_name, info in members.items():
            is_listed = 1 if info['code'] else 0
            is_rep = 1 if info['depth'] == 0 else 0
            c.execute("""
                INSERT INTO group_member_companies
                    (group_name, company_name, code, is_listed, is_representative, source, updated_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT DO NOTHING
            """, (group_name, member_name, info['code'], is_listed, is_rep, 'dart_inference', now_str()))

        # business_groups 요약
        listed_count = sum(1 for m in members.values() if m['code'])
        c.execute("""
            INSERT INTO business_groups
                (group_name, representative_company, total_companies, source, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(group_name, source) DO UPDATE SET
                total_companies=excluded.total_companies, updated_at=excluded.updated_at
        """, (group_name, head_candidates[0], len(members), 'dart_inference', now_str()))

        # companies.group_name 업데이트
        for member_name, info in members.items():
            if info['code']:
                c.execute("UPDATE companies SET group_name=? WHERE code=?",
                          (group_name, info['code']))

        log.info(f"  {group_name:15} 멤버 {len(members):3}개 (상장 {listed_count})")
        total_members += len(members)

    conn.commit()
    log.info(f"=== 완료: {len(KOREAN_CHAEBOL_HEADS)}개 그룹, 총 {total_members}개 멤버 ===")

    # 결과 요약
    listed_grouped = c.execute(
        "SELECT COUNT(*) FROM companies WHERE group_name IS NOT NULL AND group_name != ''"
    ).fetchone()[0]
    log.info(f"상장사 그룹 매핑: {listed_grouped}개")
    conn.close()


if __name__ == '__main__':
    main()

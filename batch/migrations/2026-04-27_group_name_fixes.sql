-- ============================================================
-- 종목-그룹사 매핑 보정 마이그레이션 (영구)
-- 적용 대상: ~/Project_AI/stock_db/data/stock_db.sqlite
-- 작성일: 2026-04-27
-- 실행:   sqlite3 ~/Project_AI/stock_db/data/stock_db.sqlite \
--           < batch/migrations/2026-04-27_group_name_fixes.sql
--
-- 적용 후 반드시 다음 파이프라인 재실행:
--   python3 -m batch.build_ownership
--   python3 -m batch.export_chaebol
-- ============================================================

BEGIN;

-- ────────────────────────────────────────────────────────────
-- A. 그룹명 통합: '대한항공그룹' → '한진그룹'
--    근거: 공정거래위원회 지정 기업집단명은 '한진'이며,
--          '대한항공그룹'은 일반 통념상의 별칭에 불과함.
--          한진칼이 두 그룹의 대표회사로 동일하게 등록되어 있어
--          명백한 데이터 모델 중복.
-- ────────────────────────────────────────────────────────────
UPDATE companies                SET group_name = '한진그룹' WHERE group_name = '대한항공그룹';
UPDATE business_groups          SET group_name = '한진그룹' WHERE group_name = '대한항공그룹';
UPDATE group_member_companies   SET group_name = '한진그룹' WHERE group_name = '대한항공그룹';

-- 합쳐진 후 (한진그룹, code) 중복 발생 가능 → dedup
DELETE FROM group_member_companies
WHERE rowid NOT IN (
    SELECT MIN(rowid) FROM group_member_companies
    GROUP BY group_name, COALESCE(code, ''), company_name
);

-- business_groups 도 dedup (동일 group_name 두 행이 남았을 수 있음)
DELETE FROM business_groups
WHERE rowid NOT IN (
    SELECT MIN(rowid) FROM business_groups GROUP BY group_name
);

-- ────────────────────────────────────────────────────────────
-- B. 대교(019680) — 학습지 출판 기업, 어떤 재벌 그룹에도 속하지 않음.
--    현재 companies.group_name = '현대자동차그룹' 으로 잘못 입력됨.
-- ────────────────────────────────────────────────────────────
UPDATE companies SET group_name = NULL
 WHERE code IN ('019680','019685','019687','019689','01968K');

DELETE FROM group_member_companies
 WHERE code IN ('019680','019685','019687','019689','01968K');

-- ────────────────────────────────────────────────────────────
-- C. KSS해운(044450) — 1995년 한진그룹에서 분리된 독립 화학물질 운송회사.
--    공정위 한진 기업집단 계열사 명단에 포함되지 않음.
-- ────────────────────────────────────────────────────────────
UPDATE companies SET group_name = NULL
 WHERE code IN ('044450','044455','044457','044459','04445K');

DELETE FROM group_member_companies
 WHERE code IN ('044450','044455','044457','044459','04445K');

-- ────────────────────────────────────────────────────────────
-- D. 019685 대교우B — group_member_companies 에 '신세계그룹' 멤버로
--    잘못 등록되어 있던 행 제거 (B에서 처리됨).
-- ────────────────────────────────────────────────────────────
-- (별도 작업 없음 — 위 B에서 019685 모든 그룹 멤버십 삭제)

COMMIT;

-- ============================================================
-- 검증 쿼리
-- ============================================================
-- 1) "대한항공그룹" 이 어디에도 남아있지 않아야 함
SELECT 'companies' AS tbl, COUNT(*) AS n FROM companies WHERE group_name='대한항공그룹'
UNION ALL SELECT 'business_groups', COUNT(*) FROM business_groups WHERE group_name='대한항공그룹'
UNION ALL SELECT 'group_member_companies', COUNT(*) FROM group_member_companies WHERE group_name='대한항공그룹';

-- 2) 대교/KSS해운이 어떤 그룹에도 속하지 않아야 함
SELECT code, name, group_name FROM companies
 WHERE code IN ('019680','019685','019687','019689','01968K',
                '044450','044455','044457','044459','04445K');

-- 3) 한진그룹 상장 계열사 목록 (대한항공, 한진칼, 진에어, 한진, 아시아나항공, 에어부산, 한국공항)
SELECT code, name FROM companies WHERE group_name='한진그룹' ORDER BY code;

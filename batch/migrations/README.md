# 종목-그룹사 매핑 보정 마이그레이션

`web/data/{group_map,ownership,chaebol-codes,chaebol}.json` 의 그룹사명 보정은
SQLite DB(`~/Project_AI/stock_db/data/stock_db.sqlite`)에서 시작되어야 함.
본 디렉터리의 SQL 파일들은 그 보정용 마이그레이션이다.

## 파일

- `2026-04-27_group_name_fixes.sql` — '대한항공그룹' → '한진그룹' 통합,
  대교(019680) / KSS해운(044450) 잘못된 그룹 매핑 제거.

## 실행 절차

```bash
# 1) DB 백업
cp ~/Project_AI/stock_db/data/stock_db.sqlite \
   ~/Project_AI/stock_db/data/stock_db.sqlite.bak-$(date +%Y%m%d)

# 2) 마이그레이션 적용
sqlite3 ~/Project_AI/stock_db/data/stock_db.sqlite \
  < batch/migrations/2026-04-27_group_name_fixes.sql

# 3) JSON 재생성
python3 -m batch.build_ownership
python3 -m batch.export_chaebol

# 4) 결과 확인 후 commit
git add web/data/
git commit -m "fix: 종목-그룹사 매핑 보정 (한진/대한항공 통합, 대교·KSS해운 제거)"
```

# 한국 재벌가 가계도 데이터

> 자동매매 대시보드 **관계도 → 가계도 모드**의 데이터 원본.
> 이 문서를 편집하면 DB에 반영할 수 있습니다.

## 📌 사용 방법

### 데이터 갱신 (Obsidian 수정 후)
```bash
cd /Users/kimkihong/Project_AI/stock_db
python3 collectors/09_chaebol_family.py --from-md
```

### 형식 규칙
- **인물 표**: `id`는 영문/언더스코어, 한 인물당 한 행
- **관계 표**: `rel_type`은 `parent` | `spouse` | `sibling`, `divorced` 컬럼은 1=이혼/0=현재
- **회사 표**: `code`는 6자리 종목코드 (없으면 비워둠)
- 빈 셀은 `-` 또는 빈 칸 (둘 다 무시됨)

### 새 데이터 추가
1. 아래 표에 행 추가
2. id는 다른 인물과 겹치지 않게 (예: `kim_dongkwan`)
3. 부부 자녀가 있으면 양쪽 부모 모두에 parent 관계 추가
4. 위 명령 실행 후 대시보드에서 `관계도 탭 → 가계도 모드` 새로고침

---

## 1. 인물 (persons)

| id | name | name_alt | birth | death | gender | group | gen | role | notes |
|---|---|---|---|---|---|---|---|---|---|
| lee_byungchul | 이병철 | Lee Byung-chul | 1910 | 1987 | M | 삼성그룹 | 1 | 창업주 | 삼성그룹 창업주 |
| lee_maenghui | 이맹희 | - | 1931 | 2015 | M | CJ그룹 | 2 | 회장 | 이병철 장남, CJ 분리 |
| lee_kunhee | 이건희 | Lee Kun-hee | 1942 | 2020 | M | 삼성그룹 | 2 | 회장 | 삼성 2대 회장 |
| lee_myunghui | 이명희 | - | 1943 | - | F | 신세계그룹 | 2 | 회장 | 이병철 막내딸, 신세계 회장 |
| hong_rahui | 홍라희 | Hong Ra-hee | 1945 | - | F | 삼성그룹 | 2 | 前 리움 관장 | 이건희 배우자, 홍진기 前법무장관 딸 |
| lee_jaeyong | 이재용 | Jay Y. Lee | 1968 | - | M | 삼성그룹 | 3 | 회장 | 삼성전자 회장 |
| lee_bujin | 이부진 | Lee Boo-jin | 1970 | - | F | 삼성그룹 | 3 | 사장 | 호텔신라 사장 |
| lee_seohyun | 이서현 | Lee Seo-hyun | 1973 | - | F | 삼성그룹 | 3 | 이사장 | 삼성복지재단/삼성문화재단 |
| lim_woojae | 임우재 | - | 1968 | - | M | - | 3 | 前 사장 | 이부진 前 배우자, 前 삼성전기 사장 |
| kim_jaeyeol | 김재열 | - | 1968 | - | M | - | 3 | 사장 | 이서현 배우자, IOC 위원 |
| lim_seryeong | 임세령 | - | 1977 | - | F | - | 3 | 대상홀딩스 부회장 | 이재용 前 배우자, 임창욱 대상그룹 회장 딸 |
| lee_wonju | 이원주 | - | 2004 | - | F | 삼성그룹 | 4 | - | 이재용 장녀 (생년 보도마다 차이 있음) |
| lee_jiho | 이지호 | - | - | - | M | 삼성그룹 | 4 | - | 이재용 장남 (생년 비공개) |
| lim_sejoo | 임세주 | - | 2005 | - | M | - | 4 | - | 이부진·임우재 장남 |
| kim_jisoo | 김지수 | - | 2003 | - | F | - | 4 | - | 이서현·김재열 장녀 |
| kim_inseo | 김인서 | - | 2007 | - | F | - | 4 | - | 이서현·김재열 차녀 |
| kim_jay | 김제이 | - | 2010 | - | M | - | 4 | - | 이서현·김재열 장남 |
| lee_jaehyun | 이재현 | Lee Jay-hyun | 1960 | - | M | CJ그룹 | 3 | 회장 | 이맹희 장남, CJ 회장 |
| lee_jaehwan | 이재환 | - | 1962 | - | M | CJ그룹 | 3 | 前 부회장 | 이맹희 차남 |
| lee_kyunghu | 이경후 | - | 1985 | - | F | CJ그룹 | 4 | 브랜드전략실장 | 이재현 장녀 |
| lee_seonho | 이선호 | - | 1990 | - | M | CJ그룹 | 4 | 경영리더 | 이재현 장남 |
| chung_jaeun | 정재은 | - | 1939 | - | M | 신세계그룹 | 2 | 명예회장 | 이명희 배우자 |
| chung_yongjin | 정용진 | - | 1968 | - | M | 신세계그룹 | 3 | 회장 | 이마트 회장 |
| chung_yookyung | 정유경 | - | 1972 | - | F | 신세계그룹 | 3 | 사장 | 신세계 사장 |
| chung_juyoung | 정주영 | Chung Ju-yung | 1915 | 2001 | M | 현대그룹 | 1 | 창업주 | 현대그룹 창업주 |
| chung_monggu | 정몽구 | Chung Mong-koo | 1938 | - | M | 현대자동차그룹 | 2 | 명예회장 | 현대차 명예회장 |
| chung_monghon | 정몽헌 | - | 1948 | 2003 | M | 현대그룹 | 2 | 회장 | 前 현대그룹 회장 |
| chung_mongjun | 정몽준 | - | 1951 | - | M | 현대중공업그룹 | 2 | 대주주 | HD현대 대주주 |
| chung_monggun | 정몽근 | - | 1942 | - | M | 현대백화점그룹 | 2 | 명예회장 | 현대백화점 명예회장 |
| chung_monghyup | 정몽협 | - | 1953 | - | F | - | 2 | - | 정주영 장녀 |
| chung_uisun | 정의선 | Euisun Chung | 1970 | - | M | 현대자동차그룹 | 3 | 회장 | 현대차그룹 회장 |
| chung_seongi | 정성이 | - | 1962 | - | F | 해비치호텔 | 3 | 고문 | 정몽구 장녀 |
| chung_myungi | 정명이 | - | 1964 | - | F | 현대커머셜 | 3 | 사장 | 정몽구 차녀 |
| chung_yuni | 정윤이 | - | 1968 | - | F | 해비치호텔 | 3 | 전무 | 정몽구 삼녀 |
| chung_jisun | 정지선 | - | 1972 | - | M | 현대백화점그룹 | 3 | 회장 | 정몽근 장남 |
| chung_kyosun | 정교선 | - | 1974 | - | M | 현대그린푸드 | 3 | 부회장 | 정몽근 차남 |
| koo_inhwoi | 구인회 | Koo In-hwoi | 1907 | 1969 | M | LG그룹 | 1 | 창업주 | LG그룹 창업주 |
| koo_jakyung | 구자경 | - | 1925 | 2019 | M | LG그룹 | 2 | 명예회장 | LG 2대 회장 |
| koo_bonmoo | 구본무 | Koo Bon-moo | 1945 | 2018 | M | LG그룹 | 3 | 회장 | LG 3대 회장 |
| koo_kwangmo | 구광모 | Koo Kwang-mo | 1978 | - | M | LG그룹 | 4 | 회장 | LG 4대 회장 (구본무 양자) |
| koo_bonjun | 구본준 | - | 1951 | - | M | LX그룹 | 3 | 회장 | LX홀딩스 회장 |
| koo_bonneung | 구본능 | - | 1949 | - | M | 희성그룹 | 3 | 회장 | 희성그룹 회장 |
| huh_chang | 허창수 | - | 1948 | - | M | GS그룹 | 3 | 명예회장 | 前 GS그룹 회장 |
| huh_taesoo | 허태수 | - | 1957 | - | M | GS그룹 | 3 | 회장 | GS그룹 회장 |
| choi_jonggun | 최종건 | - | 1926 | 1973 | M | SK그룹 | 1 | 창업주 | SK그룹 창업주 |
| choi_jonghyun | 최종현 | - | 1929 | 1998 | M | SK그룹 | 2 | 회장 | SK 2대 회장 |
| choi_taewon | 최태원 | Chey Tae-won | 1960 | - | M | SK그룹 | 3 | 회장 | SK 3대 회장 |
| choi_jaewon | 최재원 | - | 1963 | - | M | SK그룹 | 3 | 수석부회장 | SK 수석부회장 |
| roh_sohyung | 노소영 | - | 1961 | - | F | - | 3 | 관장 | 아트센터나비, 노태우 前대통령 장녀, 최태원 前배우자 |
| choi_yoonjung | 최윤정 | - | 1989 | - | F | SK그룹 | 4 | - | 최태원 장녀 |
| choi_minjung | 최민정 | - | 1991 | - | F | SK그룹 | 4 | - | 최태원 차녀 |
| kim_jonghee | 김종희 | - | 1922 | 1981 | M | 한화그룹 | 1 | 창업주 | 한화그룹 창업주 |
| kim_seungyeon | 김승연 | Kim Seung-youn | 1952 | - | M | 한화그룹 | 2 | 회장 | 한화 2대 회장 |
| kim_dongkwan | 김동관 | - | 1983 | - | M | 한화그룹 | 3 | 부회장 | 한화에어로스페이스 부회장 |
| kim_dongwon | 김동원 | - | 1985 | - | M | 한화그룹 | 3 | 사장 | 한화생명 사장 |
| kim_dongsun | 김동선 | - | 1989 | - | M | 한화그룹 | 3 | 부사장 | 한화갤러리아 부사장 |
| shin_kyukho | 신격호 | Shin Kyuk-ho | 1922 | 2020 | M | 롯데그룹 | 1 | 창업주 | 롯데그룹 창업주 |
| shin_dongbin | 신동빈 | Shin Dong-bin | 1955 | - | M | 롯데그룹 | 2 | 회장 | 롯데 2대 회장 |
| shin_dongjoo | 신동주 | - | 1954 | - | M | - | 2 | 前 부회장 | 신격호 장남, 일본 롯데 분쟁 |
| shigemi_manami | 시게미츠 마나미 | - | 1958 | - | F | - | 2 | - | 신동빈 배우자 (일본인) |
| shin_yuyoung | 신유영 | - | 1986 | - | M | 롯데그룹 | 3 | 상무 | 신동빈 장남 |
| cho_choonghoon | 조중훈 | - | 1920 | 2002 | M | 한진그룹 | 1 | 창업주 | 한진그룹 창업주 |
| cho_yangho | 조양호 | - | 1949 | 2019 | M | 한진그룹 | 2 | 회장 | 한진그룹 2대 회장 |
| cho_won태 | 조원태 | - | 1976 | - | M | 한진그룹 | 3 | 회장 | 한진칼/대한항공 회장 |
| cho_hyunah | 조현아 | - | 1974 | - | F | - | 3 | 前 부사장 | 대한항공 前 부사장 (땅콩회항) |
| cho_hyunmin | 조현민 | - | 1983 | - | F | 한진그룹 | 3 | 사장 | 한진 사장 |
| park_yongkon | 박용곤 | - | 1932 | 2019 | M | 두산그룹 | 3 | 명예회장 | 두산 명예회장 |
| park_jeongwon | 박정원 | - | 1962 | - | M | 두산그룹 | 4 | 회장 | 두산그룹 회장 |
| cho_hyunjun | 조현준 | - | 1968 | - | M | 효성그룹 | 3 | 회장 | 효성그룹 회장 |
| cho_hyunsang | 조현상 | - | 1971 | - | M | 효성그룹 | 3 | 부회장 | 효성첨단소재 부회장 |
| chung_mongik | 정몽익 | - | 1962 | - | M | KCC그룹 | 3 | 회장 | KCC글라스 회장 |
| chung_monghoon | 정몽훈 | - | 1968 | - | M | KCC그룹 | 3 | 사장 | 성훈건설 |
| hong_jingi | 홍진기 | - | 1917 | 1986 | M | 중앙일보 | 1 | 회장 | 前 법무장관, 중앙일보 회장 |
| hong_seokhyun | 홍석현 | - | 1949 | - | M | 중앙홀딩스 | 2 | 회장 | 중앙홀딩스 회장 |

---

## 2. 가족 관계 (relations)

| from_id | to_id | rel_type | divorced | notes |
|---|---|---|---|---|
| lee_byungchul | lee_maenghui | parent | 0 | |
| lee_byungchul | lee_kunhee | parent | 0 | |
| lee_byungchul | lee_myunghui | parent | 0 | |
| lee_kunhee | hong_rahui | spouse | 0 | |
| lee_kunhee | lee_jaeyong | parent | 0 | |
| lee_kunhee | lee_bujin | parent | 0 | |
| lee_kunhee | lee_seohyun | parent | 0 | |
| hong_rahui | lee_jaeyong | parent | 0 | |
| hong_rahui | lee_bujin | parent | 0 | |
| hong_rahui | lee_seohyun | parent | 0 | |
| lee_bujin | lim_woojae | spouse | 1 | 이혼 |
| lee_seohyun | kim_jaeyeol | spouse | 0 | |
| lee_jaeyong | lim_seryeong | spouse | 1 | 2009 이혼 |
| lee_jaeyong | lee_wonju | parent | 0 | |
| lee_jaeyong | lee_jiho | parent | 0 | |
| lim_seryeong | lee_wonju | parent | 0 | |
| lim_seryeong | lee_jiho | parent | 0 | |
| lee_bujin | lim_sejoo | parent | 0 | |
| lim_woojae | lim_sejoo | parent | 0 | |
| lee_seohyun | kim_jisoo | parent | 0 | |
| kim_jaeyeol | kim_jisoo | parent | 0 | |
| lee_seohyun | kim_inseo | parent | 0 | |
| kim_jaeyeol | kim_inseo | parent | 0 | |
| lee_seohyun | kim_jay | parent | 0 | |
| kim_jaeyeol | kim_jay | parent | 0 | |
| hong_jingi | hong_rahui | parent | 0 | |
| hong_jingi | hong_seokhyun | parent | 0 | |
| lee_maenghui | lee_jaehyun | parent | 0 | |
| lee_maenghui | lee_jaehwan | parent | 0 | |
| lee_jaehyun | lee_kyunghu | parent | 0 | |
| lee_jaehyun | lee_seonho | parent | 0 | |
| lee_myunghui | chung_jaeun | spouse | 0 | |
| lee_myunghui | chung_yongjin | parent | 0 | |
| lee_myunghui | chung_yookyung | parent | 0 | |
| chung_jaeun | chung_yongjin | parent | 0 | |
| chung_jaeun | chung_yookyung | parent | 0 | |
| chung_juyoung | chung_monggu | parent | 0 | |
| chung_juyoung | chung_monghon | parent | 0 | |
| chung_juyoung | chung_mongjun | parent | 0 | |
| chung_juyoung | chung_monggun | parent | 0 | |
| chung_juyoung | chung_monghyup | parent | 0 | |
| chung_monggu | chung_uisun | parent | 0 | |
| chung_monggu | chung_seongi | parent | 0 | |
| chung_monggu | chung_myungi | parent | 0 | |
| chung_monggu | chung_yuni | parent | 0 | |
| chung_monggun | chung_jisun | parent | 0 | |
| chung_monggun | chung_kyosun | parent | 0 | |
| koo_inhwoi | koo_jakyung | parent | 0 | |
| koo_jakyung | koo_bonmoo | parent | 0 | |
| koo_jakyung | koo_bonjun | parent | 0 | |
| koo_jakyung | koo_bonneung | parent | 0 | |
| koo_bonmoo | koo_kwangmo | parent | 0 | 양자 입양 (구본능 친자) |
| choi_jonggun | choi_jonghyun | sibling | 0 | |
| choi_jonghyun | choi_taewon | parent | 0 | |
| choi_jonghyun | choi_jaewon | parent | 0 | |
| choi_taewon | roh_sohyung | spouse | 1 | 이혼 |
| choi_taewon | choi_yoonjung | parent | 0 | |
| choi_taewon | choi_minjung | parent | 0 | |
| kim_jonghee | kim_seungyeon | parent | 0 | |
| kim_seungyeon | kim_dongkwan | parent | 0 | |
| kim_seungyeon | kim_dongwon | parent | 0 | |
| kim_seungyeon | kim_dongsun | parent | 0 | |
| shin_kyukho | shin_dongjoo | parent | 0 | |
| shin_kyukho | shin_dongbin | parent | 0 | |
| shin_dongbin | shigemi_manami | spouse | 0 | |
| shin_dongbin | shin_yuyoung | parent | 0 | |
| cho_choonghoon | cho_yangho | parent | 0 | |
| cho_yangho | cho_won태 | parent | 0 | |
| cho_yangho | cho_hyunah | parent | 0 | |
| cho_yangho | cho_hyunmin | parent | 0 | |

---

## 3. 인물-회사 (person_company)

| person_id | code | company | role | ownership_pct |
|---|---|---|---|---|
| lee_jaeyong | 005930 | 삼성전자 | 회장 | - |
| lee_jaeyong | 028260 | 삼성물산 | 대주주 | 17.97 |
| lee_kunhee | 005930 | 삼성전자 | 前 회장 | - |
| hong_rahui | 005930 | 삼성전자 | 대주주 | 1.97 |
| lee_bujin | - | 호텔신라 | 사장 | - |
| lee_seohyun | 030000 | 제일기획 | 前 사장 | - |
| lee_jaehyun | - | CJ | 회장 | - |
| lee_seonho | - | CJ제일제당 | 경영리더 | - |
| chung_yongjin | 139480 | 이마트 | 회장 | - |
| chung_yookyung | 004170 | 신세계 | 사장 | - |
| chung_uisun | 005380 | 현대차 | 회장 | - |
| chung_uisun | 012330 | 현대모비스 | 대주주 | - |
| chung_monggu | 005380 | 현대차 | 명예회장 | - |
| chung_jisun | 069960 | 현대백화점 | 회장 | - |
| chung_kyosun | 453340 | 현대그린푸드 | 부회장 | - |
| chung_mongjun | 267250 | HD현대 | 대주주 | 26.6 |
| koo_kwangmo | 003550 | LG | 회장 | 15.95 |
| koo_bonjun | - | LX홀딩스 | 회장 | - |
| huh_taesoo | 078930 | GS | 회장 | - |
| choi_taewon | 034730 | SK | 회장 | 17.73 |
| choi_jaewon | 034730 | SK | 수석부회장 | - |
| kim_seungyeon | 000880 | 한화 | 회장 | - |
| kim_dongkwan | 012450 | 한화에어로스페이스 | 부회장 | - |
| kim_dongwon | - | 한화생명 | 사장 | - |
| kim_dongsun | 452260 | 한화갤러리아 | 부사장 | - |
| shin_dongbin | 004990 | 롯데지주 | 회장 | 13.04 |
| cho_won태 | 180640 | 한진칼 | 회장 | - |
| cho_hyunmin | - | 한진 | 사장 | - |
| park_jeongwon | 000150 | 두산 | 회장 | - |
| cho_hyunjun | 004800 | 효성 | 회장 | - |
| cho_hyunsang | 298050 | 효성첨단소재 | 부회장 | - |

---

## 📚 추가 참고

### 데이터 정확도 가이드
- ✅ **확실** (위키피디아·공식 보도): 창업주~3세대 본인 생년·배우자, 공시된 회장/임원 직책
- ⚠️ **검증 필요** (보도마다 차이): 미성년 자녀 생년, 이혼·양자 입양 시점, 비상장 회사 지분율
- ❌ **사용 금지**: SNS·블로그에서만 노출된 정보, 미성년 자녀 거주지·학교

### ⚠️ 검증되지 않은 항목 (수정 환영)
다음 항목은 보도/추정에 의존하므로 부정확할 수 있습니다:
- **이재용 자녀**: 이원주(2004 추정), 이지호(생년 비공개)
- **이부진 자녀**: 임세주(2005 추정)
- **이서현 자녀**: 김지수(2003), 김인서(2007), 김제이(2010) — 모두 추정
- **신동빈 자녀 외**: 신유영 외 자녀 데이터 미수집

→ 정확한 정보를 확인하시면 표에서 직접 수정 후 build 명령 실행하면 즉시 반영됩니다.

### 향후 추가 후보
- 정의선 가족 (배우자, 자녀)
- 박정원 (두산) 가족
- 조현준 (효성) 가족
- 신동빈 자녀 추가 (신유영 외)
- 구광모 가족 (입양/혈연 관계)

### 관련 파일
- 시드 스크립트: `/Users/kimkihong/Project_AI/stock_db/collectors/09_chaebol_family.py`
- DB: `/Users/kimkihong/Project_AI/stock_db/data/stock_db.sqlite`
- 대시보드: `/Users/kimkihong/Project_AI/auto_stock_trading/dashboard/app.py` → 관계도 탭

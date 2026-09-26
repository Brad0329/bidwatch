# BidWatch 데이터 모델 — 스키마 변경 결정 기록

> **AI는 임의로 컬럼 추가/변경, 마이그레이션 수정을 하지 않는다.**
> 스키마 변경 절차: ① 변경안을 이 문서 '변경 이력'에 먼저 기록 → ② 사용자 확인 → ③ 모델/마이그레이션 반영
> → ④ **구버전 저장본(로컬 개발 DB, 공고 1.7만 건+)을 실제로 읽어 마이그레이션 실측 + 되돌리기 경로(`alembic downgrade`·
> `pg_dump` 백업) 확인 + 사용자 실테스트** 후 배포.
> 이 문서는 "결정과 이유"를, 코드는 "현재 상태"를 담당한다 —
> 컬럼 정의는 `backend/app/models/*.py`, 적용 이력은 `backend/alembic/versions/NNN_*.py`가 정답이다.
> (2026-09-23 종전 `docs/db_schema.md`의 손으로 쓴 DDL을 폐기하고 이 문서로 대체 — DDL은 이미 코드와 어긋나 있었다.)

## 설계 원칙
- PostgreSQL 16, SQLAlchemy 2.0 async 모델, Alembic 마이그레이션(번호형 `001_`, `002_` …).
- **타임스탬프 (2026-09-23 실측 정정)**: 실제 컬럼은 전부 `timestamptz`(001 마이그레이션 `timezone=True`), 세션 TimeZone
  Asia/Seoul, 모델은 timezone 없는 `DateTime` — 이 어긋남 때문에 aware 값은 저장 실패, naive `utcnow()`는 9시간 이르게 저장된다.
  **결정(2026-09-23 사용자)**: 앱이 쓰는 시각은 `func.now()`(DB가 찍는다) — 코드만 바꾸고 모델·연결 TimeZone은 그대로.
  그 전에 utcnow()로 저장된 행(updated_at·system_sources.last_collected_at)은 보정하지 않는다(공개 전 개발 DB, 재수집 시 갱신).
  버린 대안: 모델을 `DateTime(timezone=True)`로 정렬(스키마 게이트·범위 큼) / 연결 TimeZone UTC(전역, ::date 계산이 바뀜).
  (종전 기록 "TIMESTAMP WITHOUT TIME ZONE + utcnow()"는 Phase 001 시점 DB 기준이었다.)
- 공고 식별: 출처 내 고유번호 `(source_id, bid_no)` / `(scraper_id, bid_no)` UNIQUE — 재수집은 갱신(upsert).
- 수집기별 추가 필드는 컬럼을 늘리지 않고 `extra JSONB`에 둔다(출처마다 필드가 다름). 첨부는 `attachments JSONB`.
- 다중 값 설정은 마이그레이션 회피를 위해 콤마 구분 문자열도 허용(예: `tenant_profiles.region = "서울,부산"`).
- 소프트 삭제는 구독(`is_active`)에만. 공고는 삭제하지 않는다.

## 핵심 엔티티와 관계
```
[공유 — 전 테넌트]
system_sources ──1:N──→ bid_notices             (공공 API 공고)
scraper_registry ──1:N──→ scraped_notices       (URL 스크래퍼 공고)

[테넌트별]
tenants ──1:N──→ users (owner/admin/member)
tenants ──M:N──→ system_sources                  via tenant_system_subscriptions
tenants ──M:N──→ scraper_registry                via tenant_source_subscriptions
tenants ──1:N──→ tenant_keywords
tenants ──1:N──→ tenant_tags                     (notice_type='bid'|'scraped' + notice_id — 다형 참조, FK 없음)
tenants ──1:1──→ tenant_profiles                 (현재 region만 사용)

[모델만 있고 미사용 — 이후 단계용]
tenant_matches · subscriptions · notification_settings
```

## 도메인별 설계 결정

### 공고 저장 — 공유 테이블
- **결정**: 공공 API 공고는 `bid_notices` 하나에 1회 저장하고 모든 테넌트가 조회 시점에 구독·키워드로 거른다.
- **이유**: 같은 공고를 테넌트마다 복제하면 저장·API 한도(data.go.kr 오퍼레이션별 일일 한도)가 테넌트 수에 비례한다.
- **버린 대안**: 테넌트별 공고 복사 — 비용 선형 증가로 기각.

### 사전규격 — 별도 출처 행
- **결정**: 나라장터 사전규격은 `bid_notices`에 `notice_type` 컬럼을 추가하지 않고 `system_sources`에 `nara_prespec` 행을 추가(003).
- **이유**: source_id만으로 구분돼 기존 쿼리·구조를 그대로 쓴다.
- **버린 대안**: notice_type 컬럼 — 마이그레이션+모든 쿼리 수정 필요로 기각. (`work_log/Phase_005.md`)

### 스크래퍼 — URL 단위 공유
- **결정**: `scraper_registry.url_hash`(정규화 URL의 SHA256) UNIQUE. 같은 URL은 스크래퍼 1개, 테넌트는 구독만 추가.
- **이유**: 두 번째 테넌트부터 AI 분석 비용 0.

- **기본 제공 사이트 (2026-09-24 — 004)**: 운영자가 미리 등록한 사이트는 `is_builtin = true`.
  관리자설정의 "기본 제공 사이트" 목록에는 이 행만 나온다 — 사용자가 직접 추가한 URL은 다른 회사에 드러나지 않는다
  (2026-09-23 결정 "다른 회사가 어떤 사이트를 지켜보는지 드러나지 않게" 유지). 기본 제공 행은 만든 회사가 없으므로
  `created_by_tenant_id`는 NULL. 구독은 지금처럼 URL을 넣어 하고, 같은 URL이면 분석 없이 즉시 붙는다.
  버린 대안: 등록 회사를 특정 테넌트로 지정(컬럼 추가 없이 가능하지만 그 회사가 "만든 것"으로 기록돼 F-016 운영자
  분리 때 되돌려야 함) / `scraper_config`에 표시 키를 숨김(JSONB 안이라 조회·인덱스가 어색하고 설정 재생성 때 지워진다).

### 태그 — 공고당 1개
- **결정**: `tenant_tags` UNIQUE `(tenant_id, notice_type, notice_id)`. 태그 값 허용 목록은 스키마가 아니라
  `backend/app/schemas/tag.py`의 `VALID_TAGS`에서 검증.
- **이유**: 검토요청→입찰대상→낙찰/유찰의 상태 전이 모델. (`work_log/Phase_007.md`)
- **버린 대안**: 공고당 다중 태그 — 워크플로가 상태 하나로 수렴하므로 기각.

### 지역 — 정규화 값 저장
- **결정**: `region`에 수집 시점 정규화한 짧은 이름(17개 시/도)을 저장. 정규화 불가 값은 원본 유지.
- **이유**: 수집기마다 표기가 달라 조회 시점 매칭이 복잡해진다. 로직 변경 시 `backend/scripts/backfill_regions.py`로 소급.
  (`work_log/Phase_008.md`)
- **원천 (2026-09-25)**: 나라장터 공사는 `extra.cnstrtsiteRgnNm`(공사현장), 그 외는 bid-collectors `region`(나라장터는 수요기관명)
  — `services/region.notice_region`. 소급은 같은 함수(538건 반영).

### 나라장터 차수·취소 — bidwatch가 원문으로 판정 (2026-09-25, F-017 · 2026-09-26 국방·LH·가스공사로 확장 — 007 행)
- **결정**: 이전 차수는 `superseded`(006), 취소는 기존 `status`에 `'cancelled'`. 둘 다 수집 저장 직후 `extra` 원문으로 bidwatch가 정한다.
- **이유**: bid-collectors는 "표준 필드에 추정 금지" 원칙으로 status·region 방침이 미정이다 — 원문(`extra`)에 기대면 그쪽 결정과 무관하다(사용자 결정).
- **주의**: 재수집 upsert는 status를 bid-collectors 값으로 덮지만 곧바로 `refresh_revisions`가 되살린다 — upsert 경로 밖에서 bid_notices를 쓰면 이 함수를 불러야 한다.

## 변경 이력 (최신이 위)
| 날짜 | 변경안 (무엇을, 왜, 영향 범위) | 사용자 확인 | 반영 |
|---|---|---|---|
| 2026-09-26 | 007 (안): system_sources에 기관 출처 4행 추가 — `('LH 입찰공고','lh')`·`('한국가스공사 입찰공고','kogas')`·`('국방전자조달 입찰공고','d2b')`·`('한국수자원공사 입찰공고','kwater')`. 005(알리오)와 같은 데이터 행 추가, 컬럼 변경 없음. 왜: 알리오는 예산·방식·자격이 없고, 가스공사는 알리오에 약 1/6만, 국방은 알리오에 없다(bid-collectors v1.4.0 handover, 요청서 §4-1 사용자 선택). 영향: 공공 출처 목록 4행(묶음은 입찰 — `SUPPORT_COLLECTOR_TYPES`에 넣지 않음), 구독해야 공고 목록에 나온다. 키는 기존 `DATA_GO_KR_KEY`(2026-09-26 bidwatch 키로 4종 errors 0 실측). 되돌리기: 005와 같이 이 출처의 공고·구독이 있으면 downgrade 거부. **같은 작업에서 정할 것**: 국방 차수 중복(7일 418행 중 27공고×2행)·취소 미반영(LH 2·가스 3·국방 12) — F-017 판정을 이 출처로 넓힐지(수집 시점 정규화 = 일반 트랙) → **넓힌다**(같은 날 사용자 결정, 컬럼 추가 없음 — 기존 `superseded`·`status`). 실측: 백업 `scripts/_tmp/backup_before_007_20260926_083110.dump`, 빈 상태 upgrade→downgrade→upgrade 왕복 OK, 수집 후(공고 575건) downgrade 거부·007 유지 | ✅ 2026-09-26 ("이 이름으로 진행") | `007_add_institution_sources.py` |
| 2026-09-25 | 006: `bid_notices.superseded BOOLEAN NOT NULL DEFAULT false` 추가 — 나라장터는 변경·재·취소공고가 **새 차수**(bid_no 끝 `-001`…)로 따로 와서 한 공고가 여러 행이 된다(7일치 6,345건 중 496행이 더 높은 차수가 있는 이전 차수). 목록은 최신 차수만 보여야 한다(F-017, 2026-09-25 사용자 결정). **왜 컬럼인가**: 조회 때 `extra->>'bidNtceNo'` NOT EXISTS로 거르면 1만 행에서 1회 205ms(해시 안티조인, 실측 `scripts/_tmp/latest_ord_perf.py`) — 목록은 건수+페이지 2회라 +0.4초, 한 달치면 ~1초 이상으로 늘어난다. 수집 때 한 번 계산해 두면 목록은 `superseded = false` 조건 하나. **값의 원천**: `extra`의 `bidNtceNo`·`bidNtceOrd`(원문) — 같은 출처·같은 공고번호에 더 높은 차수 행이 있으면 true. 수집(upsert) 직후 그 출처 전체를 다시 계산(`services/collection.refresh_revisions` — 행을 한 번 읽어 파이썬에서 판정, 바뀐 행만 id로 UPDATE. SQL 한 문장은 플래너가 JSONB 조건을 1행으로 오판해 20초 걸려 버렸다). 마이그레이션은 컬럼만 추가하고 기존 행은 같은 함수를 부르는 `backend/scripts/backfill_revisions.py`로 채운다(구현 한 곳). 영향: 목록 API 두 곳(공고·사전규격 — 사전규격은 해당 키가 없어 늘 false), 태그 필터가 걸린 조회(검토요청 등)는 거르지 않는다. 같은 작업의 **취소**는 컬럼 추가 없이 기존 `status`에 `'cancelled'`(interface.md 값 집합에 이미 있음)를 bidwatch가 `extra.ntceKindNm='취소공고'`로 넣고 같은 공고번호의 낮은 차수에도 퍼뜨린다. 버린 대안: 조회 시 NOT EXISTS(느림·데이터에 비례) / `extra->>'bidNtceNo'` 식 인덱스(안티조인은 여전히 전체를 훑는다) / `status='superseded'` 재사용(상태 의미가 섞이고 마감·취소와 겹친다). 되돌리기: downgrade = 컬럼 삭제(값은 extra에서 다시 계산 가능, 잃는 데이터 없음), 착수 전 `pg_dump` 백업 `scripts/_tmp/backup_before_006_20260925_135101.dump`. 실측(공고 1만 행 개발 DB): upgrade→downgrade→upgrade 왕복 OK, 채운 뒤 nara 6,345건 중 이전 차수 496·취소 579(취소공고 367 + 그보다 낮은 차수), 취소됐는데 cancelled 아닌 낮은 차수 0. **같은 작업의 데이터 변경**: 차수 정리가 이전 차수의 태그(`tenant_tags.notice_id`)를 최신 차수로 옮긴다(2026-09-25 사용자 결정 — 최신 차수에 그 회사 태그가 있으면 안 옮김) | ✅ 2026-09-25 ("컬럼 추가 진행") | `006_bid_notices_superseded.py` |
| 2026-09-24 | 005: system_sources에 `alio`(알리오 공공기관 입찰공고) 행 추가 — 003(nara_prespec)과 같은 데이터 행 추가, 컬럼 변경 없음. 자체조달 공기업 공고를 공공 출처로 받기 위해(`procurement_sources_research.md` 3-1). 영향: 공공 출처 목록에 1행, 구독해야 공고 목록에 나온다. 되돌리기: 이 출처의 공고·구독이 있으면 downgrade 거부 | ✅ 2026-09-24 ("전용 수집기 + 공공 출처" 선택) | `005_add_alio_source.py` |
| 2026-09-24 | 004: `scraper_registry.is_builtin BOOLEAN NOT NULL DEFAULT false` 추가 + `created_by_tenant_id` NULL 허용 — lets_portal 손 설정 39곳을 기본 제공 사이트로 옮겨 관리자설정에 목록 표시. 영향: 기존 행은 false·값 유지(데이터 변경 없음), 읽는 곳은 새 목록 API 1개, `created_by_tenant_id`는 쓰기만 하고 읽는 코드 없음. 되돌리기: 기본 제공 행(NULL)이 있으면 downgrade가 거부하고 멈춘다(조용히 지우지 않음) — 실측: 행 없을 때 왕복 OK·데이터 digest 동일, 행 있을 때 거부·004 유지. 백업 `scripts/_tmp/backup_before_004_*.dump` | ✅ 2026-09-24 | `004_scraper_builtin.py` |
| 2026-04-13 | 003: system_sources에 nara_prespec 행 추가 — 입찰 예고(F-008) | ✅ | `003_add_nara_prespec_source.py` |
| 2026-04-11 | 002: tenant_system_subscriptions 추가 — 사용자 직접 수집 → 출처 구독 구조 전환(F-004) | ✅ | `002_tenant_system_subscriptions.py` |
| 2026-04-11 | 001: 초기 스키마 (공고·테넌트·사용자·키워드·태그·스크래퍼·프로필·매칭·결제·알림) | ✅ | `001_initial_schema.py` |

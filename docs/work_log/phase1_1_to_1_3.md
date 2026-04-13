# Phase 1-1 ~ 1-3 작업 로그

> 작성일: 2026-04-11
> 다음 작업: Phase 1-4 (프론트엔드 + 공고/태그/키워드 API)

---

## Phase 1-1: 프로젝트 셋업 + DB + 인증

### 결정과 이유
- **passlib 제거, bcrypt 직접 사용:** passlib이 bcrypt 5.0과 호환되지 않음. 유지보수 중단된 라이브러리에 의존하지 않기로 결정.
- **database.py lazy 초기화 패턴:** 글로벌 엔진 대신 `get_engine()`/`get_session_factory()` 함수 사용. 테스트에서 이벤트 루프가 달라지면 "Future attached to a different loop" 에러 발생 — 테스트마다 엔진을 리셋하려면 lazy 패턴이 필수.

### 실패한 접근
1. passlib + bcrypt 5.0 → `AttributeError` → passlib 제거하고 bcrypt 직접 사용으로 해결
2. Windows ProactorEventLoop + asyncpg → 충돌 → `asyncio.WindowsSelectorEventLoopPolicy()` 적용 필수
3. 테스트 간 글로벌 엔진 공유 → "Future attached to a different loop" → lazy 초기화 + conftest에서 테스트마다 `db_mod._engine = None` 리셋 + `engine.dispose()`

### 외부 제약
- Windows에서 asyncpg 사용 시 반드시 SelectorEventLoopPolicy 설정 필요

---

## Phase 1-2: bid-collectors 연동 + 수집 파이프라인

### 결정과 이유
- **태스크별 독립 엔진:** Celery 태스크마다 `create_async_engine()` 생성 + 사용 후 `dispose()`. 메인 앱 엔진과 공유하면 이벤트 루프 충돌.
- **bid-collectors editable 설치:** `pip install -e C:/Users/user/Documents/bid-collectors` — 수집기 패키지를 동시에 개발하므로 editable 모드 필수.

### 실패한 접근
1. `datetime.now(timezone.utc)` → TIMESTAMP WITHOUT TIME ZONE 컬럼에 저장 불가 → `datetime.utcnow()` (timezone-naive)로 통일
2. 테스트 `drop_all`이 alembic 시드 데이터(system_sources 5개)까지 삭제 → `alembic downgrade base + upgrade head`로 복원. 이후 테스트에서 drop_all 자제.

### 외부 제약
- DB 타임스탬프: 프로젝트 전체에서 `datetime.utcnow()` 사용 (timezone-naive). PostgreSQL 컬럼이 WITHOUT TIME ZONE이므로.

### 실제 수집 테스트
- K-Startup: 13건 수집, 11초 소요, 에러 없음 확인

---

## Phase 1-3: AI 스크래퍼 생성 + URL 구독 플로우

### 결정과 이유
- **`_dispatch_analysis()` 분리:** Celery 디스패치를 라우터에서 별도 함수로 분리 — 테스트에서 mock하기 위한 유일한 해결책.
- **스크래퍼 재사용 설계:** 동일 URL을 다른 테넌트가 등록해도 기존 scraper에 구독만 추가 (AI 비용 0). scraper_registry.url_hash UNIQUE 제약으로 보장.

### 실패한 접근
1. Celery `.delay()` 호출 시 Redis 없으면 무한 대기 → 테스트 행(hang)
2. `broker_connection_timeout` 설정만으로는 해결 안 됨 → conftest에서 `patch("app.routers.sources._dispatch_analysis")` mock이 유일한 해결책

### 외부 제약
- ANTHROPIC_API_KEY: 운영 배포 시 반드시 설정 필요
- Redis 미설치 상태에서 Celery 관련 함수는 반드시 mock

---

## 환경
- Python 3.11.2, PostgreSQL 16 (로컬), Redis 미설치, Docker 미설치
- bid-collectors v1.0: `C:\Users\user\Documents\bid-collectors` (editable 설치)
- DB: `bidwatch:bidwatch_dev@localhost:5432/bidwatch`
- API 키: DATA_GO_KR_KEY, BIZINFO_API_KEY 설정 완료

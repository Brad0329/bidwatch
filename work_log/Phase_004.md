# Phase 1-4 작업 로그

> 작성일: 2026-04-11 (2차 갱신)
> 범위: Session 1 (초기 구현) + Session 2 (구조 리팩토링 + 모달)
> 다음 작업: 나라장터 상세 API 재검토, 태그 시스템, 대시보드, 자동 수집

---

## 결정과 이유

- **동기 수집 fallback (sync=true):** Redis 미설치 상태에서 Celery 비동기 수집 불가. admin.py에서 sync=true 시 `_collect_source()`를 직접 await. 자체 엔진 생성/dispose하므로 request handler 내 호출 안전.
- **ILIKE vs FTS:** 한국어 부분매칭에 ILIKE가 초기에 더 적합. FTS(to_tsvector/to_tsquery)는 데이터 증가 시 전환 필요.
- **Celery import lazy화:** celery 모듈 미설치 시 collect_api.py 전체 로드 실패 문제. celery import를 lazy + try/except로 변경하여 sync 모드에서 celery 없이 동작하도록 함.
- **출처 구독 모델 도입:** 기존 사용자 직접 수집 구조 → 서버가 수집한 공고 중 구독 출처+키워드로 필터링하는 구조로 전환. tenant_system_subscriptions 테이블 추가.
- **키워드 일괄 등록:** 쉼표/공백 분리 후 각각 등록. 중복은 무시하고 계속 진행.
- **보조금24 숨김:** 필요성 미확정이라 백엔드 변경 없이 프론트 HIDDEN_TYPES로 필터.
- **공고 목록 자동 필터링 로직:** 구독 출처 없으면 빈 결과, 키워드 있으면 ILIKE 자동매칭, 검색어(q) 있으면 키워드 필터 비활성화.
- **모달 2단계 로딩:** lets_portal 패턴 차용. 리스트 데이터 즉시 표시 → 상세 API(/api/notices/{id})로 보충 → DB 캐시.
- **나라장터 fetch_detail 스킵:** bid-collectors의 g2b.go.kr 스크래핑이 타임아웃. 나라장터는 목록 API 데이터가 전부이므로 상세 호출 자체를 건너뜀 (SKIP_DETAIL_TYPES 추가).
- **백엔드 포트 8000 → 8100:** 다른 프로젝트와 충돌.
- **max_keywords 기본값 3 → 100:** DDL default도 100으로 변경.

## 실패한 접근

1. **celery 미설치 + top-level import:** collect_api.py가 celery_app.py를 top-level import → ModuleNotFoundError. lazy import + try/except로 해결.
2. **bid-collectors 미설치 상태 수집 시도:** ModuleNotFoundError. `pip install -e` 재실행 + uvicorn 재시작 필요.
3. **FastAPI 라우트 순서 충돌:** `/api/sources/system/subscriptions`가 `/api/sources/{sub_id}`에 가려져 404. 코드 변경 후 uvicorn reload가 안 된 것이 원인 → 재시작으로 해결.
4. **나라장터 g2b.go.kr 스크래핑 → ConnectTimeout:** 사이트 접근 자체 불가. fetch_detail을 호출하지 않도록 SKIP_DETAIL_TYPES 추가.
5. **모달 extra 필드 키 불일치:** lets_portal 기준 키(assign_budget, contact_name 등)와 bid-collectors 실제 저장 키(budget, contact 등)가 달랐음. DB 실제 데이터 확인 후 수정.

## 외부 제약

- **data.go.kr API 일일 한도:** 기본 1,000회. 수집 + 상세 조회 합산. 소진 시 다음 날 리셋.
- **나라장터 목록 API에 content 없음:** 사업개요 필드 자체가 없음. lets_portal에서도 미해결 (Phase 4b 계획).
- **sync 수집 지연:** 10-30초 소요 가능. 프론트 타임아웃 주의.
- **admin 수집 엔드포인트:** owner/admin 역할 필요. 일반 사용자 수집은 별도 엔드포인트 검토 필요.

## 환경

- 백엔드: http://localhost:8100
- 프론트: http://localhost:3000 (Next.js 16.2.3, TypeScript, Tailwind, Zustand, TanStack Query)
- bid-collectors: editable 설치 (C:\Users\user\Documents\bid-collectors)

## 다음 작업

- 나라장터 상세 API 방안 재검토 (data.go.kr 상세 operation 확인)
- 태그 시스템 (검토요청/입찰대상/제외)
- 대시보드 구현
- 자동 수집 (Redis/Celery 또는 대안)

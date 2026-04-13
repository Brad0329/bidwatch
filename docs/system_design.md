# BidWatch - 입찰공고 모니터링 SaaS

> **관련 문서:**
> - [db_schema.md](db_schema.md) — PostgreSQL 테이블 DDL, 인덱스, 관계도
> - [api_spec.md](api_spec.md) — API 엔드포인트 명세 + 프론트엔드 페이지 구성
> - [roadmap.md](roadmap.md) — 개발 로드맵
> - [interface.md](interface.md) — bid-collectors 패키지 인터페이스 정의

## 1. 서비스 개요

**한줄 요약:** 정부/공공기관 입찰공고를 키워드로 자동 수집하여, 고객사에 맞는 공고를 매일 알려주는 구독형 서비스

**핵심 가치:**
- 나라장터 등 주요 공공 API를 기본 제공하여 즉시 사용 가능
- 사용자가 자기만의 입찰공고 사이트 URL을 추가하면 AI가 자동으로 스크래퍼 생성
- 회사 프로필 기반 AI 매칭으로 "나에게 맞는 공고" 자동 추천 (향후)

**타겟 고객:**
- 중소 IT/컨설팅 업체 (입찰 담당자 1~3명)
- 업종별/지역별 전문기관 공고를 놓치고 있는 업체

---

## 2. 시스템 아키텍처

### 2.1 현재 구조

```
[사용자 브라우저]
    │
    ├── [Frontend — Next.js (localhost:3000)]
    │       App Router, TypeScript, Tailwind, Zustand, TanStack Query
    │
    └── [Backend API — FastAPI (localhost:8100)]
            │
            ├── Auth 모듈 (JWT access + refresh)
            ├── 역할 기반 접근 제어 (require_role → owner/admin/member)
            ├── 공고 조회/검색 API (ILIKE 키워드 매칭)
            ├── 출처 구독 관리
            ├── 키워드 관리
            ├── 동기 수집 실행 (sync 모드, Celery 없이)
            ├── AI 스크래퍼 생성 (Claude API)
            └── 상세 보충 서비스 (fetch_detail → DB 캐시)
                    │
                    ▼
            [PostgreSQL 16]
                ├── bid_notices — 공공 API 공고 (전체 고객 공유)
                ├── scraper_registry — URL별 스크래퍼 설정 (공유)
                ├── scraped_notices — 스크래퍼 수집 공고 (구독 테넌트 공유)
                └── 테넌트별 데이터 (구독, 키워드, 태그, 설정)
```

### 2.2 목표 구조 (향후)

```
현재 구조 +
    [Celery Workers + Redis]
        ├── 정기 수집 — 공공 API (1일 2회)
        ├── 정기 수집 — 스크래퍼 URL (구독자 있는 것만)
        ├── AI URL 분석 (비동기)
        ├── AI 프로필 매칭 (배치)
        └── 알림 발송 (이메일, 카카오)
```

### 2.3 데이터 분리 전략

```
[공유 데이터 — 전체 고객]
  ├── bid_notices          공공 API 수집 공고
  ├── system_sources       공공 API 출처 정보 (6개: nara, nara_prespec, kstartup, bizinfo, subsidy24, smes)
  ├── scraper_registry     URL별 스크래퍼 설정 (AI 생성)
  └── scraped_notices      스크래퍼 수집 공고

[테넌트별 데이터 — 고객마다 독립]
  ├── tenant_system_subscriptions  공공 API 출처 구독
  ├── tenant_source_subscriptions  커스텀 스크래퍼 구독
  ├── tenant_keywords              키워드
  ├── tenant_tags                  태그 (검토요청, 입찰대상, 제외)
  └── users                        사용자 (역할: owner/admin/member)
```

**핵심:**
- 공공 API 공고는 1회 수집 → 전체 고객이 공유
- 스크래퍼는 URL 단위로 1개만 생성, 여러 테넌트가 구독
- 키워드 매칭은 조회 시점에 수행 (ILIKE, 향후 FTS 전환)

---

## 3. 사용자/관리자 분리 (Phase 1-6에서 구현)

### 역할 모델
- **owner**: 테넌트 생성 시 자동 부여, 모든 권한
- **admin**: 관리자 권한 (수집 관리 등)
- **member**: 일반 사용자 (조회, 키워드, 태그)

### 접근 제어
- Backend: `deps.py`의 `require_role()` 팩토리 → `require_admin = require_role("owner", "admin")`
- Frontend: Sidebar에서 역할 기반 메뉴 표시, Admin 페이지 role guard

### 페이지 분리
| 페이지 | 역할 | 기능 |
|--------|------|------|
| /settings | 모든 사용자 | 구독 출처 관리, 키워드 관리 |
| /admin | owner, admin | 수집 관리 (수동 수집 실행) |

---

## 4. 수집기 아키텍처

### 공공 API 수집 (bid-collectors 패키지)

| 출처 | collector_type | 패키지 |
|------|---------------|--------|
| 나라장터 입찰공고 | nara | NaraCollector |
| 나라장터 사전규격 | nara_prespec | NaraCollector.collect_pre_specs() |
| K-Startup | kstartup | KstartupCollector |
| 기업마당 | bizinfo | BizinfoCollector |
| 보조금24 | subsidy24 | Subsidy24Collector |
| 중소벤처기업부 | smes | SmesCollector |

### 수집 방식
- 현재: 관리자가 수동 실행 (sync 모드, POST /api/admin/collection/run)
- 연쇄 수집: nara 수집 시 nara_prespec 자동 수집 (CHAINED_COLLECTORS)
- 향후: Celery Beat 정기 수집

### AI 스크래퍼 (커스텀 URL)
1. 사용자 URL 제출 → URL 정규화 + 해시
2. scraper_registry에서 동일 URL 검색
3. 없으면 AI 분석 디스패치 (Claude API → scraper_config JSON 생성)
4. 분석 완료 후 미리보기 → 구독 확정

---

## 5. 기술 스택

### Backend
```
Python 3.11, FastAPI, Uvicorn
PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic
JWT (bcrypt, HS256)
bid-collectors (editable 설치)
```

### Frontend
```
Next.js (App Router), TypeScript
Tailwind CSS, Remix Icon
Zustand (인증 상태), TanStack Query (서버 상태)
```

### AI
```
Claude API (Anthropic SDK)
  - 스크래퍼 생성: scraper_config JSON 자동 생성
  - (향후) 프로필 매칭, 첨부파일 분석
```

---

## 6. 상세 문서

- **DB 스키마:** [db_schema.md](db_schema.md) — 전체 테이블 DDL, 인덱스, 관계도, 구현 상태
- **API 명세:** [api_spec.md](api_spec.md) — 구현 완료/미구현 엔드포인트, 프론트 페이지 구성
- **로드맵:** [roadmap.md](roadmap.md) — Phase 1~4 개발 계획, 진행 상태
- **인터페이스:** [interface.md](interface.md) — bid-collectors 패키지 인터페이스 정의

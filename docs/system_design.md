# BidWatch - 입찰공고 모니터링 SaaS

> **관련 문서:**
> - [db_schema.md](db_schema.md) — PostgreSQL 테이블 DDL, 인덱스, 관계도
> - [api_spec.md](api_spec.md) — API 엔드포인트 명세 + 프론트엔드 페이지 구성
> - [roadmap.md](roadmap.md) — 개발 로드맵, 비용 구조, 리스크
> - [bid_collectors.md](../../bid-collectors/docs/bid_collectors.md) — bid-collectors 패키지 설계 (공공 API 25개+, 단계별 연동 계획)
> - [dev_reference.md](dev_reference.md) — lets_portal 핵심 코드 구조 레퍼런스

## 1. 서비스 개요

**한줄 요약:** 정부/공공기관 입찰공고를 키워드로 자동 수집하여, 고객사에 맞는 공고를 매일 알려주는 구독형 서비스

**핵심 가치:**
- 나라장터 등 주요 공공 API를 기본 제공하여 즉시 사용 가능
- 사용자가 자기만의 입찰공고 사이트 URL을 추가하면 AI가 자동으로 스크래퍼 생성
- 회사 프로필 기반 AI 매칭으로 "나에게 맞는 공고" 자동 추천

**타겟 고객:**
- 중소 IT/컨설팅 업체 (입찰 담당자 1~3명)
- 업종별/지역별 전문기관 공고를 놓치고 있는 업체
- 자기 회사만의 맞춤 공고 출처를 구축하고 싶은 업체

---

## 2. 요금제

| 구분 | 체험(무료) | 기본 | 프리미엄 | 엔터프라이즈 |
|------|-----------|------|---------|------------|
| 월 요금 | 0원 | 3~5만원 | 10~15만원 | 별도 협의 |
| 공고 출처 | 공공 API만 (나라장터 등) | 공공 API + URL 5개 | 공공 API + URL 무제한 | 전용 인스턴스 |
| 키워드 | 3개 | 20개 | 무제한 | 무제한 |
| 조회 기간 | 최근 7일 | 최근 30일 | 최근 90일 | 무제한 |
| URL 추가 (AI 스크래퍼) | X | 5개 | 무제한 | 무제한 |
| 자동 수집 | 1일 1회 | 1일 2회 | 1일 3회 | 실시간 |
| 알림 | 이메일 | 이메일 | 이메일 + 카카오 알림톡 | 전체 + API |
| AI 프로필 매칭 | X | X | O ("내게 맞는 공고") | O + 커스텀 |
| AI 첨부파일 분석 | X | X | O (자격요건 체크) | O |
| 팀 계정 | 1명 | 2명 | 5명 | 무제한 |
| 태그/워크플로우 | X | 기본 (검토요청/제외) | 전체 (입찰관리 포함) | 전체 + 커스텀 |

**출처 구조:**
- **공공 API (기본 제공, 모든 요금제):** 나라장터, K-Startup, 기업마당(Bizinfo) — 정부 공식 API, 전 고객 공유
- **사용자 URL 추가 (유료):** 고객이 직접 입찰공고 게시판 URL을 입력 → AI가 스크래퍼 자동 생성
  - 예: 교육컨설팅 회사 → 각 지역 교육청, 대학교, 교육관련 재단 URL 등록
  - 예: IT 업체 → 정보통신산업진흥원, 각 테크노파크, 지역 혁신센터 URL 등록
  - 각 고객의 업종/관심 분야에 맞는 맞��형 출처 구성

---

## 3. 시스템 아키텍처

### 3.1 전체 구조

```
[사용자 브라우저]
    │
    ▼
[Nginx / Reverse Proxy]
    │
    ├── [Frontend — React/Next.js]
    │       SPA, SSR, 반응형 UI
    │
    └── [Backend API — FastAPI (Python)]
            │
            ├── Auth 모듈 (JWT + OAuth)
            ├── Tenant 관리
            ├── 공고 조회/검색 API
            ├── 태그/워크플로우 API
            ├── 알림 발송 모듈
            ├── AI 연동 모듈 (Claude API)
            └── 수집 스케줄러 연동
                    │
                    ▼
            [Celery Workers]
                ├── 정기 수집 — 공공 API (나라장터/K-Startup/Bizinfo, 전체 공유)
                ├── 정기 수집 — 스크래퍼 URL (scraper_registry 기반, 구독자 있는 것만)
                ├── AI URL 분석 (신규 스크래퍼 생성 → scraper_registry)
                ├── AI 프로필 매칭 (배치)
                └── 첨부파일 다운로드/파싱
                    │
                    ▼
            [Redis] — 작업 큐 + 캐시 + 세션
                    │
                    ▼
            [PostgreSQL]
                ├── bid_notices — 공공 API 공고 (전체 고객 공유)
                ├── scraper_registry — URL별 스크래퍼 설정 (공유 자산)
                ├── scraped_notices — 스크래퍼 수집 공고 (구독 테넌트 공유)
                ├── tenant_source_subscriptions — 테넌트↔스크래퍼 구독
                ├── 테넌트별 데이터 (키워드, 태그, 설정, 프로필)
                ├── 사용자/구독/결제 정보
                └── 수집 이력/로그
```

### 3.2 데이터 분리 전략 — 공유 vs 테넌트별

```
[공유 데이터 — 모든 고객이 같은 공공 API 공고를 봄]
  ├── bid_notices (source_type='api')   공공 API 수집 공고 (나라장터, K-Startup, Bizinfo)
  └── system_sources                    공공 API 출처 정보 (2~3개)

[공유 스크래퍼 — URL 단위로 1개만 유지, 여러 테넌트가 구독]
  ├── scraper_registry       URL별 스크래퍼 설정 (AI 생성, UNIQUE url)
  └── scraped_notices        스크래퍼가 수집한 공고 (구독 테넌트 공유)

[테넌트별 데이터 — 고객마다 완전 독립]
  ├── tenant_source_subscriptions  스크래퍼 구독 (scraper_registry FK, 테넌트별 별칭/활성)
  ├── tenant_keywords    키워드 목록 + 활성 상태
  ├── tenant_tags        공고별 태그 (검토요청, 입찰대상, 제외)
  ├── tenant_settings    표시 설정, 알림 설정
  ├── tenant_profiles    회사 프로필 (프리미엄)
  ├── tenant_matches     AI 매칭 결과 (프리미엄)
  └── tenant_members     팀원 계정
```

**핵심 설계:**
- **공공 API 공고**는 1회 수집 → 전체 고객이 공유 (나라장터, K-Startup, Bizinfo)
- **사용자 URL 공고**는 URL 단위로 1회 수집 → 해당 URL을 구독하는 모든 테넌트가 공유
  - A 테넌트가 URL 등록 → AI가 스크래퍼 생성 → `scraper_registry`에 저장
  - C 테넌트가 같은 URL 등록 → 기존 스크래퍼 즉시 구독 (AI 비용 0, 시간 0)
  - 수집도 URL당 1회만 실행 → 서버 부하/차단 리스크 감소
- 키워드 매칭은 조회 시점에 수행 (공유 공고 + 구독 스크래퍼 공고 합쳐서 tenant_keywords로 필터)
- 사용자가 볼 수 있는 공고 = 공공 API 공고(공유) + 내가 구독한 스크래퍼의 공고(구독)

### 3.3 수집기 아키텍처 재설계

#### 현재 lets_portal 구조 (단일 테넌트)

```
수집 실행 → 키워드 1세트 로드 → API/스크래퍼 호출 → bid_notices에 저장
                                                        ↓
                                                사용자가 바로 조회
```

**문제:** 키워드가 1세트, 모든 공고를 1 DB에 저장, 수집과 조회가 1:1

#### BidWatch 구조 (멀티테넌트)

```
[수집 레이어 — 2개 트랙]

  트랙 1: 공공 API 수집 (전체 공유, 하루 2~3회, Celery Beat)
  │   ├── 나라장터 API → 당일 전체 공고 수집 (키워드 필터 없이)
  │   ├── K-Startup API → 전체 공고 수집
  │   └── Bizinfo API → 전체 공고 수집 (추후)
  │   → 결과 → bid_notices 테이블 (전체 고객 공유)
  │
  트랙 2: 스크래퍼 URL 수집 (URL 단위, 하루 1~3회)
      → scraper_registry에서 is_active=true인 스크래퍼 조회
      → 1개 이상의 테넌트가 구독 중인 스크래퍼만 수집 실행
      → AI가 생성한 scraper_config로 수집
      → 결과 → scraped_notices 테이블 (구독 테넌트 공유)
      → 같은 URL을 구독하는 테넌트가 여러 명이어도 수집은 1회

[조회 레이어 — 테넌트별 키워드 매칭]
  사용자 요청
    → tenant_keywords 로드
    → bid_notices(공공API 공유)
       UNION scraped_notices(내가 구독한 스크래퍼 공고)
       에서 키워드 FTS 검색
    → tenant_tags JOIN (해당 테넌트의 태그만)
    → 결과 반환
```

#### 공공 API 수집 방식

**현재 lets_portal:** 키워드별로 API 호출 (bidNtceNm 파라미터) → 테넌트마다 키워드가 다르므로 부적합

**BidWatch:** 전체 수집 + DB 매칭
- 나라장터: 키워드 없이 당일 전체 공고 수집 (하루 ~500~1,000건)
- K-Startup/Bizinfo: 동일하게 전체 수집
- DB에 저장 후, 각 테넌트 키워드로 PostgreSQL FTS 검색 → 응답 빠름
- 공공 API 공고는 **수집 1회 → 전 고객 공유** (비용 효율)

#### 사용자 URL 수집 방식 — AI 스크래퍼

사용자가 등록한 URL은 **AI가 scraper_config를 자동 생성**하여 수집.
lets_portal의 generic_scraper.py + scraper_configs.json 구조를 그대로 활용.

| 항목 | lets_portal 현재 | BidWatch 활용 |
|------|-----------------|--------------|
| generic_scraper.py | 설정 기반 범용 파서 | **그대로 사용** — URL 수집 엔진 |
| scraper_configs.json | 48개 사이트 수동 설정 | AI가 동일 포맷으로 자동 생성 → `scraper_registry`에 저장 |
| BaseCollector | save_to_db() 표준화 | PostgreSQL, `scraped_notices`에 저장 (테넌트 무관) |

**핵심:**
- 스크래퍼는 **URL 단위로 1개만 생성** → `scraper_registry` 테이블 (url UNIQUE)
- 테넌트는 스크래퍼를 **구독** → `tenant_source_subscriptions` 테이블
- 같은 URL을 여러 테넌트가 등록해도 AI 분석 1회, 수집 1회
- 키워드 필터링은 조회 시점에 테넌트별로 적용 (수집과 무관)
- generic_scraper.py는 config를 받아 실행하는 엔진이므로 재사용 가능.

---

## 4. 사용자 URL 추가 — AI 자동 스크래퍼 생성

### 4.1 플로우

```
[사용자]                    [시스템]                      [AI (Claude API)]
   │                          │                              │
   ├─ URL 입력 ──────────────→│                              │
   │  "https://example.or.kr  │                              │
   │   /board/bid_list.php"   │                              │
   │                          │                              │
   │                          ├─ URL 정규화 (trailing slash,  │
   │                          │   query param 정리 등)        │
   │                          │                              │
   │                          ├─ scraper_registry에서         │
   │                          │   동일 URL 검색               │
   │                          │                              │
   │              ┌────────── (A) 기존 스크래퍼 있음 ──────────┐
   │              │                                          │
   │              │  status=ready인 경우:                     │
   │              │  → 기존 수집 공고 미리보기 즉시 표시         │
   │              │  → AI 분석 불필요 (비용 0, 시간 0)          │
   │              │                                          │
   │              │  status=failed인 경우:                    │
   │              │  → "이전에 분석 실패한 URL" 안내            │
   │              │  → 사용자 선택: 재분석 요청 또는 취소        │
   │              │                                          │
   │              └────────────────────────────────────────────┘
   │              ┌────────── (B) 기존 스크래퍼 없음 ──────────┐
   │              │                                          │
   │              │  ├─ HTML 페이지 fetch ──────────────────→│
   │              │  │                                       │
   │              │  │←── HTML 분석 결과 ─────────────────────┤
   │              │  │  "게시판 구조 감지됨"                    │
   │              │  │  "제목: td.title a"                    │
   │              │  │  "날짜: td:nth-child(4)"               │
   │              │  │  → scraper_config JSON 생성            │
   │              │  │                                       │
   │              │  ├─ scraper_registry에 저장               │
   │              │  │  (url UNIQUE, status=analyzing→ready)  │
   │              │  │                                       │
   │              │  ├─ 테스트 수집 실행                       │
   │              │  │  (config로 실제 파싱 시도)               │
   │              │  │                                       │
   │              └────────────────────────────────────────────┘
   │                          │                              │
   │←── 결과 표시 ────────────┤                              │
   │  "5건 수집 성공"          │                              │
   │  [미리보기: 제목/날짜]     │                              │
   │                          │                              │
   ├─ "등록" 클릭 ───────────→│                              │
   │                          ├─ tenant_source_subscriptions  │
   │                          │  에 구독 추가                  │
   │                          │  (tenant_id + scraper_id)     │
   │                          │                              │
   │←── "등록 완료" ──────────┤                              │
```

### 4.2 AI 프롬프트 전략

```
[시스템 프롬프트]
당신은 웹 스크래퍼 설정 생성 전문가입니다.
주어진 HTML을 분석하여 아래 JSON 형식의 스크래퍼 설정을 생성하세요.

[출력 형식]
{
  "list_selector": "게시판 행을 선택하는 CSS 셀렉터",
  "title_selector": "제목 텍스트를 포함하는 요소",
  "link_selector": "상세페이지 링크를 포함하는 a 태그",
  "date_selector": "날짜를 포함하는 요소",
  "date_format": "날짜 포맷 (yyyy-MM-dd 등)",
  "pagination": "페이지네이션 URL 패턴",
  "encoding": "문자 인코딩",
  "notes": "특이사항"
}

[사용자 프롬프트]
URL: {url}
아래는 이 페이지의 HTML입니다:
{html_content}
```

### 4.3 성공률 및 대응

| 사이트 유형 | 예상 성공률 | 대응 |
|------------|:---------:|------|
| 표준 게시판 (gnuboard, XE 등) | 90% | 자동 |
| 공공기관 커스텀 게시판 | 70% | 자동, 일부 수동 보정 |
| JavaScript SPA | 30% | 수동 대응 (Playwright 필요 시 안내) |
| 로그인 필요 사이트 | 0% | 지원 불가 안내 |

실패 시: "자동 분석에 실패했습니다. 고객지원팀이 24시간 내 수동 설정해드립니다."
→ 수동 설정 결과를 config DB에 누적 → 시간이 지날수록 커버리지 증가

---

## 5. AI 프로필 매칭 (프리미엄)

### 5.1 회사 프로필 입력

```
[프로필 입력 화면]
┌─────────────────────────────────────┐
│ 회사 프로필 설정                       │
├─────────────────────────────────────┤
│ 1. 기본 정보                          │
│    회사명: [          ]               │
│    업종:   [IT/컨설팅 ▼]              │
│    규모:   [10~50인 ▼]               │
│    소재지: [서울 ▼]                   │
│                                     │
│ 2. 사업 분야 (복수 선택)               │
│    [x] 교육/연수   [ ] 홍보/마케팅     │
│    [x] 컨설팅      [x] SI/개발        │
│    [ ] 용역        [ ] 연구개발        │
│                                     │
│ 3. 경쟁력 키워드 (자유 입력)            │
│    [ESG, 디지털전환, 교육콘텐츠, ...]   │
│                                     │
│ 4. 선호 조건                          │
│    예산 범위: [3천만원] ~ [3억원]       │
│    선호 기관: [정부부처, 공공기관 ▼]     │
│                                     │
│ 5. 상세 프로필 (자유 텍스트, 선택)       │
│    [주요 실적, 보유 인증, 가점 요소 등   │
│     자유롭게 작성...]                  │
│                                     │
│                        [저장]         │
└─────────────────────────────────────┘
```

### 5.2 매칭 로직

```
[매일 배치 — Celery Beat, 아침 9시]

for each 프리미엄 테넌트:
    1. 테넌트 프로필 로드
    2. 최근 24시간 신규 공고 로드 (해당 테넌트 키워드 매칭된 것)
    3. Claude API 호출:
       - 시스템: "입찰 매칭 전문가" 역할
       - 입력: 프로필 + 공고 목록 (제목/기관/예산/키워드)
       - 출력: 각 공고별 매칭 점수(1~5) + 이유 (1줄)
    4. 점수 3 이상 → tenant_matches에 저장
    5. 알림 발송 (이메일/카카오)
```

**비용 최적화:**
- 1차 필터: 키워드 매칭 (비용 0원) → 후보 공고 추림
- 2차 필터: AI 매칭 (후보만 대상) → 비용 최소화
- Haiku 모델 사용 시: 공고 50건 스크리닝 ~200원

---

## 6. 기술 스택

### Backend
```
언어:         Python 3.12
프레임워크:    FastAPI + Uvicorn
DB:           PostgreSQL 16
캐시/큐:      Redis 7
작업 큐:      Celery 5 + Celery Beat (정기 수집)
ORM:          SQLAlchemy 2.0 (async)
마이그레이션:  Alembic
인증:         JWT (access + refresh token)
```

### Frontend
```
프레임워크:    Next.js 15 (React 19)
스타일:        Tailwind CSS
상태관리:      Zustand 또는 React Query
차트:          Recharts (대시보드)
```

### 인프라
```
서버:          AWS EC2 또는 Docker Compose (초기)
DB:           AWS RDS PostgreSQL 또는 Docker
파일 저장:    AWS S3 (첨부파일)
알림:          이메일 (AWS SES), 카카오 알림톡 (비즈엠)
결제:          토스페이먼츠 (정기결제)
모니터링:      Sentry (에러), UptimeRobot (가용성)
```

### AI
```
Claude API:   Anthropic SDK (Python)
  - 스크래퍼 생성: Sonnet (비용 효율)
  - 프로필 매칭: Haiku (대량 배치) 또는 Sonnet (정확도)
  - 첨부 분석: Sonnet (PDF 직접 전달)
```

### 수집기 패키지 (별도 프로젝트)

공공 API 수집기는 **bid-collectors** 패키지로 분리하여 병렬 개발.
상세: [bid_collectors.md](../../bid-collectors/docs/bid_collectors.md)

```
bid-collectors 패키지에서 가져옴:
  ├── BaseCollector + Notice 모델   공통 인터페이스
  ├── nara.py                       나라장터 (lets_portal에서 이식, 전체 수집 모드)
  ├── bizinfo.py                    기업마당
  ├── subsidy24.py                  보조금24
  ├── kstartup.py                   K-Startup (lets_portal에서 이식)
  ├── generic_scraper.py            AI 스크래퍼 엔진 (lets_portal에서 이식)
  └── + LH, KEPCO, 방위사업청 등    2~3단계 확장

BidWatch 본체에서 새로 작성:
  ├── AI 스크래퍼 생성 모듈 (URL → Claude API → scraper_config 자동 생성)
  ├── 멀티테넌트 인증/권한 (JWT + 테넌트 격리)
  ├── 구독/결제 모듈 (토스페이먼츠)
  ├── 알림 발송 모듈 (이메일, 카카오)
  ├── AI 프로필 매칭 모듈 (프리미엄)
  ├── Celery 작업 정의 (공공API 수집 + 스크래퍼 수집 + AI 배치)
  └── Next.js 프론트엔드 전체
```

---

## 7. 상세 문서

아래 내용은 각각 별도 문서로 분리되어 있습니다.

- **DB 스키마:** [db_schema.md](db_schema.md) — 전체 테이블 DDL, 인덱스, 관계도
- **API 명세:** [api_spec.md](api_spec.md) — 엔드포인트 목록, 프론트엔드 페이지 구성
- **로드맵:** [roadmap.md](roadmap.md) — Phase 1~4 개발 계획, 비용 구조, 리스크
- **수집기 패키지:** [bid_collectors.md](../../bid-collectors/docs/bid_collectors.md) — 공공 API 25개+, 단계별 연동 계획
- **코드 레퍼런스:** [dev_reference.md](dev_reference.md) — lets_portal 수집기/스크래퍼/유틸리티 코드 구조


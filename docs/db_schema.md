# BidWatch DB 스키마

> **관련 문서:** [system_design.md](system_design.md) — 전체 아키텍처 및 데이터 분리 전략

PostgreSQL 16 기준. 마이그레이션은 Alembic으로 관리.

---

## 1. 공유 데이터 (공공 API 공고)

```sql
-- 공공 API 수집 출처 (시스템 관리)
CREATE TABLE system_sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,              -- '나라장터', 'K-Startup', '기업마당'
    collector_type TEXT NOT NULL,    -- nara, kstartup, bizinfo
    is_active BOOLEAN DEFAULT true,
    last_collected_at TIMESTAMPTZ,
    last_collected_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 공공 API 공고 원문 (전체 고객 공유)
CREATE TABLE bid_notices (
    id BIGSERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES system_sources(id),
    bid_no TEXT,                    -- 공고 고유번호
    title TEXT NOT NULL,
    organization TEXT,              -- 발주기관
    start_date DATE,                -- 공고일
    end_date DATE,                  -- 마감일
    status TEXT,                    -- ongoing/closed/cancelled
    url TEXT,                       -- 원문 URL
    detail_url TEXT,                -- 상세 페이지 URL
    content TEXT,                   -- 공고 내용 요약
    budget BIGINT,                  -- 예산(원)
    region TEXT,                    -- 지역
    attachments JSONB,              -- 첨부파일 목록
    collected_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    UNIQUE(source_id, bid_no)
);

-- Full-Text Search 인덱스
CREATE INDEX idx_notices_fts ON bid_notices
    USING GIN (to_tsvector('simple', title || ' ' || COALESCE(content, '')));

CREATE INDEX idx_notices_dates ON bid_notices (start_date DESC, end_date);
CREATE INDEX idx_notices_status ON bid_notices (status);
```

---

## 2. 테넌트 / 사용자

```sql
-- 테넌트 (고객사)
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,             -- 회사명
    plan TEXT DEFAULT 'free',       -- free/basic/premium/enterprise
    plan_expires_at TIMESTAMPTZ,
    max_keywords INTEGER DEFAULT 3,
    max_custom_sources INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 사용자
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'member',     -- owner/admin/member
    is_active BOOLEAN DEFAULT true,
    must_change_password BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 3. 키워드 / 태그

```sql
-- 테넌트별 키워드
CREATE TABLE tenant_keywords (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    keyword TEXT NOT NULL,
    keyword_group TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, keyword)
);

-- 테넌트별 태그 (공고에 대한 고객별 평가)
-- notice_type으로 bid_notices / scraped_notices 구분
CREATE TABLE tenant_tags (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    notice_type TEXT NOT NULL,      -- 'bid' (공공API) 또는 'scraped' (스크래퍼)
    notice_id BIGINT NOT NULL,      -- bid_notices.id 또는 scraped_notices.id
    tag TEXT NOT NULL,              -- 검토요청/입찰대상/제외/낙찰/유찰
    tagged_by INTEGER REFERENCES users(id),
    memo TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, notice_type, notice_id)
);
```

---

## 4. 스크래퍼 레지스트리 + 구독 + 수집 공고

```sql
-- 스크래퍼 레지스트리 (URL 단위로 1개만, 여러 테넌트가 공유)
CREATE TABLE scraper_registry (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,       -- 정규화된 게시판 URL (UNIQUE)
    url_hash TEXT NOT NULL UNIQUE,  -- URL의 SHA256 해시 (빠른 조회용)
    name TEXT NOT NULL,             -- 사이트명 (AI가 자동 추출 또는 첫 등록자 입력)
    scraper_config JSONB,           -- AI가 자동 생성한 스크래퍼 설정
    status TEXT DEFAULT 'pending',  -- pending/analyzing/ready/failed
    analysis_log TEXT,              -- AI 분석 과정 로그 (실패 시 원인)
    subscriber_count INTEGER DEFAULT 0,  -- 구독 테넌트 수 (캐시, 0이면 수집 스킵)
    is_active BOOLEAN DEFAULT true,
    last_collected_at TIMESTAMPTZ,
    last_collected_count INTEGER,
    created_by_tenant_id INTEGER REFERENCES tenants(id),  -- 최초 등록 테넌트
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 테넌트 → 스크래퍼 구독 (M:N 관계)
CREATE TABLE tenant_source_subscriptions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    scraper_id INTEGER REFERENCES scraper_registry(id),
    custom_name TEXT,               -- 테넌트별 별칭 (예: "경기도교육청 입찰")
    is_active BOOLEAN DEFAULT true,
    subscribed_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, scraper_id)
);

CREATE INDEX idx_subscriptions_tenant ON tenant_source_subscriptions (tenant_id) WHERE is_active;
CREATE INDEX idx_subscriptions_scraper ON tenant_source_subscriptions (scraper_id) WHERE is_active;

-- 스크래퍼 수집 공고 (URL별 공유 — 구독 테넌트 모두 접근)
CREATE TABLE scraped_notices (
    id BIGSERIAL PRIMARY KEY,
    scraper_id INTEGER REFERENCES scraper_registry(id),
    bid_no TEXT,                    -- 공고 고유번호 (URL 해시 등)
    title TEXT NOT NULL,
    organization TEXT,              -- 기관명 (scraper_registry.name에서)
    start_date DATE,
    end_date DATE,
    status TEXT,
    url TEXT,                       -- 원문 URL
    detail_url TEXT,
    content TEXT,
    budget BIGINT,
    region TEXT,
    attachments JSONB,
    collected_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    UNIQUE(scraper_id, bid_no)
);

CREATE INDEX idx_scraped_notices_fts ON scraped_notices
    USING GIN (to_tsvector('simple', title || ' ' || COALESCE(content, '')));

CREATE INDEX idx_scraped_notices_scraper ON scraped_notices (scraper_id, start_date DESC);
```

---

## 5. 프로필 / AI 매칭 (프리미엄)

```sql
-- 회사 프로필
CREATE TABLE tenant_profiles (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) UNIQUE,
    company_name TEXT,
    industry TEXT,                   -- 업종
    size TEXT,                       -- 규모
    region TEXT,                     -- 소재지
    business_areas TEXT[],           -- 사업 분야
    competency_keywords TEXT[],     -- 경쟁력 키워드
    min_budget BIGINT,
    max_budget BIGINT,
    preferred_org_types TEXT[],     -- 선호 기관 유형
    detail_profile TEXT,            -- 상세 프로필 (자유 텍스트)
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- AI 매칭 결과
CREATE TABLE tenant_matches (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    notice_type TEXT NOT NULL,      -- 'bid' 또는 'scraped'
    notice_id BIGINT NOT NULL,      -- bid_notices.id 또는 scraped_notices.id
    match_score INTEGER,            -- 1~5
    match_reason TEXT,              -- AI가 생성한 매칭 이유
    matched_at TIMESTAMPTZ DEFAULT now(),
    is_notified BOOLEAN DEFAULT false,
    UNIQUE(tenant_id, notice_type, notice_id)
);
```

---

## 6. 구독/결제 / 알림

```sql
-- 구독/결제
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    plan TEXT NOT NULL,
    status TEXT DEFAULT 'active',   -- active/cancelled/expired
    billing_key TEXT,               -- 토스페이먼츠 빌링키
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 알림 설정
CREATE TABLE notification_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    user_id INTEGER REFERENCES users(id),
    email_enabled BOOLEAN DEFAULT true,
    kakao_enabled BOOLEAN DEFAULT false,
    kakao_phone TEXT,
    notify_new_match BOOLEAN DEFAULT true,   -- AI 매칭 결과
    notify_new_notices BOOLEAN DEFAULT true,  -- 키워드 매칭 신규 공고
    notify_deadline BOOLEAN DEFAULT true,     -- 마감 임박 알림
    quiet_hours_start TIME,                   -- 알림 금지 시작
    quiet_hours_end TIME                      -- 알림 금지 종료
);
```

---

## 테이블 관계 요약

```
system_sources ──1:N──→ bid_notices        (공공 API 공고)
scraper_registry ──1:N──→ scraped_notices   (스크래퍼 수집 공고)
tenants ──M:N──→ scraper_registry           (via tenant_source_subscriptions)
tenants ──1:N──→ tenant_keywords
tenants ──1:N──→ tenant_tags               (→ bid_notices 또는 scraped_notices)
tenants ──1:1──→ tenant_profiles
tenants ──1:N──→ tenant_matches            (→ bid_notices 또는 scraped_notices)
tenants ──1:N──→ users
tenants ──1:N──→ subscriptions
users ──1:N──→ notification_settings
```

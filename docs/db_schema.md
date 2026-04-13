# BidWatch DB 스키마

> **관련 문서:** [system_design.md](system_design.md) — 전체 아키텍처 및 데이터 분리 전략

PostgreSQL 16 기준. 마이그레이션은 Alembic으로 관리.

---

## 1. 공유 데이터 (공공 API 공고)

```sql
-- 공공 API 수집 출처 (시스템 관리)
CREATE TABLE system_sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,              -- '나라장터', 'K-Startup', '기업마당' 등
    collector_type TEXT NOT NULL,    -- nara, nara_prespec, kstartup, bizinfo, subsidy24, smes
    is_active BOOLEAN DEFAULT true,
    last_collected_at TIMESTAMP,
    last_collected_count INTEGER,
    created_at TIMESTAMP DEFAULT now()
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
    content TEXT,                   -- 공고 내용
    budget BIGINT,                  -- 예산(원)
    region TEXT,                    -- 지역
    category TEXT,                  -- 분류
    attachments JSONB,              -- 첨부파일 [{name, url}, ...]
    extra JSONB,                    -- 수집기별 추가 데이터 (est_price, contact 등)
    collected_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(source_id, bid_no)
);

CREATE INDEX ix_bid_notices_dates ON bid_notices (start_date, end_date);
CREATE INDEX ix_bid_notices_status ON bid_notices (status);
```

---

## 2. 테넌트 / 사용자

```sql
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT DEFAULT 'free',       -- free/pro/enterprise
    plan_expires_at TIMESTAMP,
    max_keywords INTEGER DEFAULT 100,
    max_custom_sources INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'member',     -- owner/admin/member
    is_active BOOLEAN DEFAULT true,
    must_change_password BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP
);
```

---

## 3. 구독 / 키워드 / 태그

```sql
-- 테넌트별 공공 API 출처 구독
CREATE TABLE tenant_system_subscriptions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    system_source_id INTEGER REFERENCES system_sources(id),
    subscribed_at TIMESTAMP DEFAULT now(),
    UNIQUE(tenant_id, system_source_id)
);

-- 테넌트별 키워드
CREATE TABLE tenant_keywords (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    keyword TEXT NOT NULL,
    keyword_group TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(tenant_id, keyword)
);

-- 테넌트별 태그 (공고에 대한 평가)
CREATE TABLE tenant_tags (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    notice_type TEXT NOT NULL,      -- 'bid' 또는 'scraped'
    notice_id BIGINT NOT NULL,
    tag TEXT NOT NULL,              -- 검토요청/입찰대상/제외/낙찰/유찰
    tagged_by INTEGER REFERENCES users(id),
    memo TEXT,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(tenant_id, notice_type, notice_id)
);
```

---

## 4. 스크래퍼 레지스트리 + 구독 + 수집 공고

```sql
CREATE TABLE scraper_registry (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    url_hash TEXT NOT NULL UNIQUE,  -- SHA256
    name TEXT NOT NULL,
    scraper_config JSONB,           -- AI 생성 스크래퍼 설정
    status TEXT DEFAULT 'pending',  -- pending/analyzing/ready/failed
    analysis_log TEXT,
    subscriber_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    last_collected_at TIMESTAMP,
    last_collected_count INTEGER,
    created_by_tenant_id INTEGER REFERENCES tenants(id),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE tenant_source_subscriptions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    scraper_id INTEGER REFERENCES scraper_registry(id),
    custom_name TEXT,
    is_active BOOLEAN DEFAULT true,
    subscribed_at TIMESTAMP DEFAULT now(),
    UNIQUE(tenant_id, scraper_id)
);

CREATE INDEX ix_sub_tenant_active ON tenant_source_subscriptions (tenant_id) WHERE is_active;
CREATE INDEX ix_sub_scraper_active ON tenant_source_subscriptions (scraper_id) WHERE is_active;

CREATE TABLE scraped_notices (
    id BIGSERIAL PRIMARY KEY,
    scraper_id INTEGER REFERENCES scraper_registry(id),
    bid_no TEXT,
    title TEXT NOT NULL,
    organization TEXT,
    start_date DATE,
    end_date DATE,
    status TEXT,
    url TEXT,
    detail_url TEXT,
    content TEXT,
    budget BIGINT,
    region TEXT,
    attachments JSONB,
    extra JSONB,
    collected_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(scraper_id, bid_no)
);

CREATE INDEX ix_scraped_scraper_date ON scraped_notices (scraper_id, start_date);
```

---

## 5. 프로필 / AI 매칭 (미구현 — 향후 프리미엄)

```sql
CREATE TABLE tenant_profiles (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) UNIQUE,
    company_name TEXT,
    industry TEXT,
    size TEXT,
    region TEXT,
    business_areas TEXT[],
    competency_keywords TEXT[],
    min_budget BIGINT,
    max_budget BIGINT,
    preferred_org_types TEXT[],
    detail_profile TEXT,
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE tenant_matches (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    notice_type TEXT NOT NULL,
    notice_id BIGINT NOT NULL,
    match_score INTEGER,            -- 1~5
    match_reason TEXT,
    matched_at TIMESTAMP DEFAULT now(),
    is_notified BOOLEAN DEFAULT false,
    UNIQUE(tenant_id, notice_type, notice_id)
);
```

---

## 6. 구독/결제 / 알림 (미구현)

```sql
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    plan TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    billing_key TEXT,
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE notification_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    user_id INTEGER REFERENCES users(id),
    email_enabled BOOLEAN DEFAULT true,
    kakao_enabled BOOLEAN DEFAULT false,
    kakao_phone TEXT,
    notify_new_match BOOLEAN DEFAULT true,
    notify_new_notices BOOLEAN DEFAULT true,
    notify_deadline BOOLEAN DEFAULT true,
    quiet_hours_start TIME,
    quiet_hours_end TIME
);
```

---

## 테이블 관계 요약

```
system_sources ──1:N──→ bid_notices
tenants ──M:N──→ system_sources          (via tenant_system_subscriptions)
scraper_registry ──1:N──→ scraped_notices
tenants ──M:N──→ scraper_registry        (via tenant_source_subscriptions)
tenants ──1:N──→ tenant_keywords
tenants ──1:N──→ tenant_tags
tenants ──1:1──→ tenant_profiles
tenants ──1:N──→ tenant_matches
tenants ──1:N──→ users
users ──1:N──→ notification_settings
```

## 구현 상태

| 테이블 | 상태 | Alembic |
|--------|------|---------|
| system_sources | 구현 완료 | 001 + 003 |
| bid_notices | 구현 완료 | 001 |
| tenants / users | 구현 완료 | 001 |
| tenant_system_subscriptions | 구현 완료 | 002 |
| tenant_keywords | 구현 완료 | 001 |
| tenant_tags | 모델만 정의 | 001 |
| scraper_registry | 구현 완료 | 001 |
| tenant_source_subscriptions | 구현 완료 | 001 |
| scraped_notices | 구현 완료 | 001 |
| tenant_profiles / tenant_matches | 모델만 정의 | 001 |
| subscriptions / notification_settings | 모델만 정의 | 001 |

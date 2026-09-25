// Auth
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: number;
  email: string;
  name: string | null;
  role: string;
  tenant_id: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  company_name: string;
}

// Keywords
export interface Keyword {
  id: number;
  tenant_id: number;
  keyword: string;
  keyword_group: string | null;
  is_active: boolean;
  created_at: string;
}

export interface KeywordCreateRequest {
  keyword: string;
  keyword_group?: string | null;
}

// Sources
export interface SystemSource {
  id: number;
  name: string;
  collector_type: string;
  is_active: boolean;
  last_collected_at: string | null;
  last_collected_count: number | null;
}

export interface CollectionRunRequest {
  source_id?: number;
  days: number;
  sync: boolean;
}

export interface CollectionRunResponse {
  status: string;
  message: string;
  task_id?: string | null;
}

// Notices
export interface BidNotice {
  // "bid"(공공 API 출처) | "scraped"(직접 추가한 URL 출처) — 두 종류는 id가 겹치므로 (notice_type, id)가 식별자.
  // scraped면 source_id 자리에 scraper_id가 온다.
  notice_type: "bid" | "scraped";
  id: number;
  source_id: number;
  source_name: string;
  bid_no: string;
  title: string;
  organization: string;
  start_date: string | null;
  end_date: string | null;
  status: string;
  url: string;
  detail_url: string;
  content: string;
  budget: number | null;
  region: string;
  category: string;
  collected_at: string | null;
  matched_keywords: string[];
  tag: string | null;
  attachments: Array<{ name: string; url: string }> | null;
  extra: Record<string, unknown> | null;
  related?: RelatedNotice[]; // 상세 API만 — 사전규격 ↔ 본 공고 (F-018)
}

export interface RelatedNotice {
  id: number;
  kind: "prespec" | "notice" | "nara"; // nara = 알리오 → 같은 나라장터 공고
  bid_no: string;
  title: string;
  status: string;
}

export interface NoticeListResponse {
  items: BidNotice[];
  total: number;
  page: number;
  page_size: number;
}

// URL 출처 구독 (AI 스크래퍼) — 백엔드 SubscriptionResponse
export type ScraperStatus = "pending" | "analyzing" | "ready" | "failed";

export interface BuiltinSite {
  id: number;
  name: string;
  url: string;
  status: ScraperStatus;
  last_collected_at: string | null;
  last_collected_count: number | null;
}

export interface UrlSubscription {
  id: number;
  scraper_id: number;
  scraper_name: string;
  scraper_status: ScraperStatus;
  scraper_url: string;
  custom_name: string | null;
  is_active: boolean;
  last_collected_at: string | null;
  last_collected_count: number | null;
}

export interface UrlSourceAddResponse {
  scraper_id: number;
  subscription_id: number | null;
  scraper_status: ScraperStatus;
  message: string;
}

// Collection Stats
export interface CollectionStats {
  bid_notices_count: number;
  scraped_notices_count: number;
  active_scrapers_count: number;
}

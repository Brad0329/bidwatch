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
}

export interface NoticeListResponse {
  items: BidNotice[];
  total: number;
  page: number;
  page_size: number;
}

// Collection Stats
export interface CollectionStats {
  bid_notices_count: number;
  scraped_notices_count: number;
  active_scrapers_count: number;
}

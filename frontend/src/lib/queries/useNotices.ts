import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { NoticeListResponse } from "@/types";

interface NoticeParams {
  page?: number;
  page_size?: number;
  q?: string;
  source_id?: number;
  scraper_id?: number;
  category?: "bid" | "support"; // 출처 묶음 — 전체 출처(입찰) / 전체 출처(지원)
  status?: string;
  tag?: string;
  region?: string;
  keyword_match?: boolean;
}

export function useNotices(params: NoticeParams = {}) {
  return useQuery<NoticeListResponse>({
    queryKey: ["notices", params],
    queryFn: async () => {
      const res = await api.get("/api/notices", { params });
      return res.data;
    },
  });
}

export function usePreSpecNotices(params: Omit<NoticeParams, "source_id" | "scraper_id" | "category"> = {}) {
  return useQuery<NoticeListResponse>({
    queryKey: ["pre-spec-notices", params],
    queryFn: async () => {
      const res = await api.get("/api/notices/pre-specs", { params });
      return res.data;
    },
  });
}

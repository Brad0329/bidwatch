import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { SystemSource, UrlSourceAddResponse, UrlSubscription } from "@/types";

export function useSystemSources() {
  return useQuery<SystemSource[]>({
    queryKey: ["system-sources"],
    queryFn: async () => {
      const res = await api.get("/api/sources/system");
      return res.data;
    },
  });
}

export function useSystemSubscriptions() {
  return useQuery<number[]>({
    queryKey: ["system-subscriptions"],
    queryFn: async () => {
      const res = await api.get("/api/sources/system/subscriptions");
      return res.data;
    },
  });
}

export function useSubscribe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sourceId: number) => {
      const res = await api.post(`/api/sources/system/${sourceId}/subscribe`);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-subscriptions"] });
      qc.invalidateQueries({ queryKey: ["notices"] });
    },
  });
}

// ── URL 출처 (AI 스크래퍼) ──

const ANALYZING: UrlSubscription["scraper_status"][] = ["pending", "analyzing"];

export function useUrlSubscriptions() {
  return useQuery<UrlSubscription[]>({
    queryKey: ["url-subscriptions"],
    queryFn: async () => {
      const res = await api.get("/api/sources");
      return res.data;
    },
    // 분석 중인 사이트가 있는 동안만 3초마다 상태를 다시 받는다
    refetchInterval: (query) =>
      query.state.data?.some((s) => s.is_active && ANALYZING.includes(s.scraper_status))
        ? 3000
        : false,
  });
}

export function useAddUrlSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (url: string) => {
      const res = await api.post<UrlSourceAddResponse>("/api/sources", { url });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["url-subscriptions"] });
    },
  });
}

export function useRemoveUrlSubscription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (subscriptionId: number) => {
      const res = await api.delete(`/api/sources/${subscriptionId}`);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["url-subscriptions"] });
      qc.invalidateQueries({ queryKey: ["notices"] });
    },
  });
}

export function useUnsubscribe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sourceId: number) => {
      const res = await api.delete(`/api/sources/system/${sourceId}/unsubscribe`);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-subscriptions"] });
      qc.invalidateQueries({ queryKey: ["notices"] });
    },
  });
}


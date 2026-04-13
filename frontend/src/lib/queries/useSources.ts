import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { SystemSource } from "@/types";

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


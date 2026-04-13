import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { Keyword, KeywordCreateRequest } from "@/types";

export function useKeywords() {
  return useQuery<Keyword[]>({
    queryKey: ["keywords"],
    queryFn: async () => {
      const res = await api.get("/api/keywords");
      return res.data;
    },
  });
}

export function useCreateKeyword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: KeywordCreateRequest) => {
      const res = await api.post("/api/keywords", data);
      return res.data as Keyword;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keywords"] }),
  });
}

export function useDeleteKeyword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/keywords/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keywords"] }),
  });
}

export function useToggleKeyword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const res = await api.patch(`/api/keywords/${id}`, { is_active });
      return res.data as Keyword;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keywords"] }),
  });
}

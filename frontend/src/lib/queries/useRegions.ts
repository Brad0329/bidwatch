import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export function useRegionList() {
  return useQuery<string[]>({
    queryKey: ["regions"],
    queryFn: async () => {
      const res = await api.get("/api/notices/regions");
      return res.data;
    },
    staleTime: Infinity,
  });
}

export function useRegionPreference() {
  return useQuery<string[]>({
    queryKey: ["region-preference"],
    queryFn: async () => {
      const res = await api.get("/api/profile/regions");
      return res.data.regions;
    },
  });
}

export function useUpdateRegionPreference() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (regions: string[]) => {
      const res = await api.put("/api/profile/regions", { regions });
      return res.data.regions;
    },
    onSuccess: (regions) => {
      queryClient.setQueryData(["region-preference"], regions);
    },
  });
}

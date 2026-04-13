import { useMutation } from "@tanstack/react-query";
import api from "@/lib/api";
import type { CollectionRunRequest, CollectionRunResponse } from "@/types";

export function useRunCollection() {
  return useMutation<CollectionRunResponse, Error, CollectionRunRequest>({
    mutationFn: async (data) => {
      const res = await api.post("/api/admin/collection/run", data);
      return res.data;
    },
  });
}

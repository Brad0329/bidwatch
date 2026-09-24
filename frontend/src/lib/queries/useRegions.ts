import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

// 관심 지역(/api/profile/regions) 조회·저장 훅은 2026-09-24 자동 적용·설정 화면 폐기로 뺐다.
// 저장된 값과 API는 백엔드에 남아 있다(AI 매칭·알림 후보) — 다시 쓰면 git 이력에서 가져온다.

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

"use client";

import {
  useSystemSources,
  useSystemSubscriptions,
  useSubscribe,
  useUnsubscribe,
} from "@/lib/queries/useSources";
import type { SystemSource } from "@/types";
import CollectionButton from "./CollectionButton";

interface Props {
  showCollection?: boolean;
}

export default function SourceList({ showCollection = false }: Props) {
  const { data: sources, isLoading: loadingSources } = useSystemSources();
  const { data: subscribed, isLoading: loadingSubs } = useSystemSubscriptions();
  const subscribeMutation = useSubscribe();
  const unsubscribeMutation = useUnsubscribe();

  if (loadingSources || loadingSubs) {
    return <div className="text-sm text-gray-400 py-4">로딩 중...</div>;
  }

  // 사전규격은 구독과 무관하게 입찰 예고 화면에 나온다(F-008) — 구독 목록에서 숨김
  const HIDDEN_TYPES = ["nara_prespec"];
  const filtered = (sources || []).filter(
    (s) => !HIDDEN_TYPES.includes(s.collector_type)
  );
  // 입찰 전문 — 지원사업은 선택 구독이라 따로 묶는다(2026-09-25). 묶음은 백엔드가 정한 category를 따른다
  const bidSources = filtered.filter((s) => s.category !== "support");
  const supportSources = filtered.filter((s) => s.category === "support");
  const subscribedSet = new Set(subscribed || []);

  const handleToggle = (sourceId: number) => {
    if (subscribedSet.has(sourceId)) {
      unsubscribeMutation.mutate(sourceId);
    } else {
      subscribeMutation.mutate(sourceId);
    }
  };

  const renderSource = (source: SystemSource) => {
        const isSubscribed = subscribedSet.has(source.id);
        const isPending =
          subscribeMutation.isPending || unsubscribeMutation.isPending;

        return (
          <div
            key={source.id}
            className={`rounded-lg transition-colors ${
              isSubscribed
                ? "bg-blue-50 border border-blue-200"
                : "bg-gray-50 border border-transparent hover:bg-gray-100"
            }`}
          >
            <label className="flex items-center gap-4 px-5 py-4 cursor-pointer">
              <input
                type="checkbox"
                checked={isSubscribed}
                onChange={() => handleToggle(source.id)}
                disabled={isPending}
                className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <div className="flex-1 min-w-0">
                <span className="text-sm font-semibold text-gray-900">
                  {source.name}
                </span>
                {source.last_collected_at && (
                  <span className="ml-3 text-xs text-gray-400">
                    최근 수집:{" "}
                    {new Date(source.last_collected_at).toLocaleDateString("ko-KR")}
                    {source.last_collected_count !== null &&
                      ` · ${source.last_collected_count}건`}
                  </span>
                )}
              </div>
            </label>
            {showCollection && isSubscribed && (
              <div className="px-5 pb-4 pt-0">
                <CollectionButton
                  sourceId={source.id}
                  lastCollectedAt={source.last_collected_at}
                />
              </div>
            )}
          </div>
        );
  };

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-gray-500">입찰 공고</h4>
        {bidSources.map(renderSource)}
      </div>
      {supportSources.length > 0 && (
        <div className="space-y-2 rounded-lg border border-gray-200 p-3">
          <div className="flex items-center gap-2">
            <h4 className="text-xs font-semibold text-gray-500">지원사업 (선택)</h4>
            <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded">기본 꺼짐</span>
          </div>
          <p className="text-xs text-gray-400">
            정부가 기업에 주는 지원(자금·바우처·교육 등) 공고입니다. 입찰이 아니라 신청해서 받는 사업이에요.
            켜면 입찰공고 목록에 &quot;지원&quot; 표시와 함께 나옵니다.
          </p>
          {supportSources.map(renderSource)}
        </div>
      )}
    </div>
  );
}

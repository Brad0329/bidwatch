"use client";

import {
  useSystemSources,
  useSystemSubscriptions,
  useSubscribe,
  useUnsubscribe,
} from "@/lib/queries/useSources";
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

  // 보조금24 숨김 (추후 재판단)
  const HIDDEN_TYPES = ["subsidy24", "nara_prespec"];
  const filtered = (sources || []).filter(
    (s) => !HIDDEN_TYPES.includes(s.collector_type)
  );
  const subscribedSet = new Set(subscribed || []);

  const handleToggle = (sourceId: number) => {
    if (subscribedSet.has(sourceId)) {
      unsubscribeMutation.mutate(sourceId);
    } else {
      subscribeMutation.mutate(sourceId);
    }
  };

  return (
    <div className="space-y-2">
      {filtered.map((source) => {
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
                  sourceName={source.name}
                  lastCollectedAt={source.last_collected_at}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

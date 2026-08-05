"use client";

import {
  useRegionList,
  useRegionPreference,
  useUpdateRegionPreference,
} from "@/lib/queries/useRegions";

export default function RegionSettings() {
  const { data: regions = [] } = useRegionList();
  const { data: selected = [], isLoading } = useRegionPreference();
  const { mutate: update, isPending } = useUpdateRegionPreference();

  const toggle = (region: string) => {
    const next = selected.includes(region)
      ? selected.filter((r) => r !== region)
      : [...selected, region];
    update(next);
  };

  const selectAll = () => update([...regions]);
  const clearAll = () => update([]);

  if (isLoading) {
    return <div className="text-sm text-gray-400">로딩 중...</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={selectAll}
          disabled={isPending}
          className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
        >
          전체 선택
        </button>
        <button
          onClick={clearAll}
          disabled={isPending}
          className="text-xs text-gray-500 hover:text-gray-700 disabled:opacity-50"
        >
          전체 해제
        </button>
        {selected.length > 0 && (
          <span className="text-xs text-gray-400">
            {selected.length}개 선택됨
          </span>
        )}
      </div>
      <div className="grid grid-cols-6 gap-2">
        {regions.map((r) => (
          <button
            key={r}
            onClick={() => toggle(r)}
            disabled={isPending}
            className={`text-sm px-3 py-2 rounded-lg border transition-colors disabled:opacity-50 ${
              selected.includes(r)
                ? "bg-indigo-50 text-indigo-700 border-indigo-300 font-medium"
                : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
            }`}
          >
            {r}
          </button>
        ))}
      </div>
      {selected.length === 0 && (
        <p className="text-xs text-gray-400 mt-3">
          지역을 선택하지 않으면 전체 지역의 공고가 표시됩니다
        </p>
      )}
    </div>
  );
}

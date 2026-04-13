"use client";

import { useKeywords, useDeleteKeyword } from "@/lib/queries/useKeywords";

export default function KeywordList() {
  const { data: keywords, isLoading } = useKeywords();
  const deleteMutation = useDeleteKeyword();

  if (isLoading) {
    return <div className="text-sm text-gray-400 py-4">로딩 중...</div>;
  }

  if (!keywords?.length) {
    return (
      <div className="text-sm text-gray-400 py-6 text-center">
        등록된 키워드가 없습니다
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {keywords.map((kw) => (
        <span
          key={kw.id}
          className="inline-flex items-center gap-1.5 bg-gray-100 text-gray-700 pl-3 pr-1.5 py-1.5 rounded-full text-sm font-medium"
        >
          {kw.keyword}
          <button
            onClick={() => deleteMutation.mutate(kw.id)}
            className="w-5 h-5 flex items-center justify-center rounded-full text-gray-400 hover:bg-gray-300 hover:text-gray-600 transition-colors"
          >
            <i className="ri-close-line text-sm"></i>
          </button>
        </span>
      ))}
    </div>
  );
}

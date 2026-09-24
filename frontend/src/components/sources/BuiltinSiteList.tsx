"use client";

import { useBuiltinSites } from "@/lib/queries/useSources";
import type { ScraperStatus } from "@/types";

const STATUS_BADGE: Record<ScraperStatus, { label: string; className: string }> = {
  pending: { label: "분석 대기", className: "bg-gray-100 text-gray-600" },
  analyzing: { label: "AI 분석 중", className: "bg-amber-50 text-amber-700" },
  ready: { label: "사용 가능", className: "bg-green-50 text-green-700" },
  failed: { label: "수집 불가", className: "bg-red-50 text-red-600" },
};

export default function BuiltinSiteList() {
  const { data: sites, isLoading, isError } = useBuiltinSites();

  if (isLoading) return <div className="text-sm text-gray-400 py-2">로딩 중...</div>;
  if (isError) return <div className="text-sm text-red-500 py-2">목록을 불러오지 못했습니다</div>;
  if (!sites || sites.length === 0) {
    return <div className="text-sm text-gray-400 py-2">기본 제공 사이트가 없습니다</div>;
  }

  const readyCount = sites.filter((s) => s.status === "ready").length;

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        전체 {sites.length}곳 · 사용 가능 {readyCount}곳. 구독하려면 사용자설정 &gt; 직접 추가한 사이트에 아래 주소를
        넣으세요 — 이미 분석돼 있어 바로 사용 가능이 됩니다.
      </p>
      <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg">
        {sites.map((s) => {
          const badge = STATUS_BADGE[s.status] ?? STATUS_BADGE.pending;
          return (
            <li key={s.id} className="flex items-center gap-4 px-4 py-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900 truncate">{s.name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge.className}`}>
                    {badge.label}
                  </span>
                </div>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-xs text-gray-400 hover:text-blue-600 truncate mt-0.5"
                >
                  {s.url}
                </a>
              </div>
              <div className="text-xs text-gray-400 text-right whitespace-nowrap">
                {s.last_collected_at ? (
                  <>
                    최근 수집 {new Date(s.last_collected_at).toLocaleDateString("ko-KR")}
                    <br />
                    {s.last_collected_count ?? 0}건
                  </>
                ) : (
                  "수집 기록 없음"
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  useAddUrlSource,
  useRemoveUrlSubscription,
  useUrlSubscriptions,
} from "@/lib/queries/useSources";
import { useAuthStore } from "@/stores/authStore";
import type { ScraperStatus } from "@/types";

const STATUS_BADGE: Record<ScraperStatus, { label: string; className: string; icon: string }> = {
  pending: { label: "분석 대기", className: "bg-gray-100 text-gray-600", icon: "ri-time-line" },
  analyzing: { label: "AI 분석 중", className: "bg-amber-50 text-amber-700", icon: "ri-loader-4-line animate-spin" },
  ready: { label: "사용 가능", className: "bg-green-50 text-green-700", icon: "ri-checkbox-circle-line" },
  failed: { label: "자동 인식 실패", className: "bg-red-50 text-red-600", icon: "ri-error-warning-line" },
};

export default function UrlSourceList() {
  const { user } = useAuthStore();
  const canAdd = !!user && ["owner", "admin"].includes(user.role);
  const { data: subs, isLoading } = useUrlSubscriptions();
  const addMutation = useAddUrlSource();
  const removeMutation = useRemoveUrlSubscription();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const value = url.trim();
    if (!value) return;
    try {
      await addMutation.mutateAsync(value);
      setUrl("");
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "사이트 추가에 실패했습니다");
    }
  };

  const active = (subs || []).filter((s) => s.is_active);

  return (
    <div className="space-y-3">
      {canAdd && (
        <div>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="공고 게시판 목록 페이지 주소 (https://...)"
              className="flex-1 px-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              type="submit"
              disabled={addMutation.isPending || !url.trim()}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-sm font-medium transition-colors whitespace-nowrap"
            >
              {addMutation.isPending ? "추가 중..." : "사이트 추가"}
            </button>
          </form>
          {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
          <p className="mt-2 text-xs text-gray-400">
            AI가 게시판 구조를 분석하고 시험 수집으로 확인합니다. 보통 1분 안에 끝납니다.
          </p>
        </div>
      )}

      {isLoading ? (
        <div className="text-sm text-gray-400 py-2">로딩 중...</div>
      ) : active.length === 0 ? (
        <div className="text-sm text-gray-400 py-2">추가한 사이트가 없습니다</div>
      ) : (
        <ul className="space-y-2">
          {active.map((s) => {
            const badge = STATUS_BADGE[s.scraper_status] ?? STATUS_BADGE.pending;
            const name = s.custom_name || (s.scraper_name !== s.scraper_url ? s.scraper_name : "");
            return (
              <li
                key={s.id}
                className="flex items-center gap-4 px-5 py-4 rounded-lg bg-gray-50 border border-transparent"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900 truncate">
                      {name || "새 사이트"}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${badge.className}`}
                    >
                      <i className={badge.icon}></i>
                      {badge.label}
                    </span>
                  </div>
                  <a
                    href={s.scraper_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-xs text-gray-400 hover:text-blue-600 truncate mt-0.5"
                  >
                    {s.scraper_url}
                  </a>
                  {s.scraper_status === "failed" && (
                    <p className="text-xs text-red-500 mt-1">
                      이 사이트는 자동으로 공고를 읽지 못했습니다. 게시판 목록 페이지 주소인지 확인해 주세요.
                    </p>
                  )}
                  {s.last_collected_at && (
                    <p className="text-xs text-gray-400 mt-0.5">
                      최근 수집: {new Date(s.last_collected_at).toLocaleDateString("ko-KR")}
                      {s.last_collected_count !== null && ` · ${s.last_collected_count}건`}
                    </p>
                  )}
                </div>
                {canAdd && (
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`'${name || s.scraper_url}' 구독을 해지할까요?`)) {
                        removeMutation.mutate(s.id);
                      }
                    }}
                    disabled={removeMutation.isPending}
                    className="text-xs text-gray-400 hover:text-red-500 whitespace-nowrap"
                  >
                    구독 해지
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

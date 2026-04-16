"use client";

import type { BidNotice } from "@/types";

const TAG_COLORS: Record<string, string> = {
  검토요청: "bg-yellow-50 text-yellow-700",
  입찰대상: "bg-blue-50 text-blue-700",
  제외: "bg-gray-100 text-gray-500",
  낙찰: "bg-green-50 text-green-700",
  유찰: "bg-red-50 text-red-700",
};

interface Props {
  notices: BidNotice[];
  onFilterByKeyword?: (keyword: string) => void;
  onFilterByOrg?: (org: string) => void;
  onSelectNotice?: (notice: BidNotice) => void;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return dateStr;
}

function getDday(endDate: string | null): { text: string; urgent: boolean } {
  if (!endDate) return { text: "—", urgent: false };
  const diff = Math.ceil(
    (new Date(endDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
  );
  if (diff < 0) return { text: "마감", urgent: false };
  return { text: `D-${diff}`, urgent: diff <= 3 };
}

export default function NoticeTable({ notices, onFilterByKeyword, onFilterByOrg, onSelectNotice }: Props) {
  if (!notices.length) {
    return (
      <div className="text-center py-12 text-gray-400">
        <i className="ri-file-list-3-line text-5xl text-gray-300 mb-3 block"></i>
        <p className="text-sm">
          공고가 없습니다. 설정에서 수집 출처를 선택하고 키워드를 등록해주세요.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-[90px_1fr_120px_80px_80px_70px_130px] gap-3 px-6 py-3 bg-gray-50 border-b border-gray-100 text-xs font-semibold text-gray-500 uppercase tracking-wider">
        <div>출처</div>
        <div>공고명</div>
        <div>발주기관</div>
        <div className="text-center">등록일</div>
        <div className="text-center">마감일</div>
        <div className="text-center">태그</div>
        <div>키워드</div>
      </div>

      {/* Rows */}
      {notices.map((notice) => {
        const dday = getDday(notice.end_date);
        return (
          <div
            key={notice.id}
            className="grid grid-cols-[90px_1fr_120px_80px_80px_70px_130px] gap-3 px-6 py-3.5 border-b border-gray-50 items-center hover:bg-blue-50/50 transition-colors"
          >
            {/* 출처 */}
            <div>
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-medium truncate block">
                {notice.source_name || "—"}
              </span>
            </div>

            {/* 공고명 — 클릭 시 모달 */}
            <div className="min-w-0">
              <button
                onClick={() => onSelectNotice?.(notice)}
                className="text-sm font-medium text-gray-900 hover:text-blue-600 hover:underline truncate block text-left w-full"
              >
                {notice.title}
              </button>
            </div>

            {/* 발주기관 — 클릭 시 해당 기관으로 검색 */}
            <div className="min-w-0 overflow-hidden">
              <button
                onClick={() => onFilterByOrg?.(notice.organization)}
                title={notice.organization}
                className="text-xs text-gray-600 hover:text-blue-600 hover:underline truncate block text-left w-full"
              >
                {notice.organization}
              </button>
            </div>

            {/* 등록일 */}
            <div className="text-xs text-gray-500 text-center">
              {formatDate(notice.start_date)}
            </div>

            {/* 마감일 */}
            <div className="text-center">
              <span
                className={`text-xs font-semibold ${
                  dday.urgent ? "text-red-600" : dday.text === "마감" ? "text-gray-400" : "text-gray-600"
                }`}
              >
                {dday.text}
              </span>
              {notice.end_date && (
                <div className="text-xs text-gray-400">{notice.end_date}</div>
              )}
            </div>

            {/* 태그 */}
            <div className="text-center">
              {notice.tag && (
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${TAG_COLORS[notice.tag] || "bg-gray-100 text-gray-600"}`}>
                  {notice.tag}
                </span>
              )}
            </div>

            {/* 키워드 — 클릭 시 해당 키워드로 검색 */}
            <div className="flex flex-wrap gap-1">
              {(notice.matched_keywords || []).map((kw) => (
                <button
                  key={kw}
                  onClick={() => onFilterByKeyword?.(kw)}
                  className="text-xs bg-yellow-50 text-yellow-700 hover:bg-yellow-100 px-1.5 py-0.5 rounded font-medium cursor-pointer"
                >
                  {kw}
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

"use client";

import { useState } from "react";
import { useNotices } from "@/lib/queries/useNotices";
import NoticeTable from "@/components/notices/NoticeTable";
import NoticeModal from "@/components/notices/NoticeModal";
import type { BidNotice } from "@/types";

export default function NoticesPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNotice, setSelectedNotice] = useState<BidNotice | null>(null);

  const { data, isLoading } = useNotices({
    page,
    page_size: 20,
    q: searchQuery || undefined,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchQuery(search);
    setPage(1);
  };

  const handleFilter = (value: string) => {
    setSearch(value);
    setSearchQuery(value);
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div>
      <header className="bg-white border-b border-gray-200 px-8 py-4">
        <h1 className="text-xl font-bold text-gray-900">공고 목록</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {data ? `총 ${data.total}건` : "로딩 중..."}
        </p>
      </header>

      <div className="p-8">
        {/* 검색 */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm mb-6">
          <form onSubmit={handleSearch} className="px-6 py-4 flex gap-3">
            <div className="flex-1 relative">
              <i className="ri-search-line absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"></i>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="공고명, 기관명, 키워드로 검색..."
                className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 flex items-center gap-2"
            >
              <i className="ri-search-line"></i> 검색
            </button>
            {searchQuery && (
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setSearchQuery("");
                  setPage(1);
                }}
                className="px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
              >
                초기화
              </button>
            )}
          </form>
          {searchQuery && (
            <div className="px-6 pb-3 text-sm text-gray-500">
              <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-medium">
                {searchQuery}
              </span>
              <span className="ml-2">검색 결과</span>
            </div>
          )}
        </div>

        {/* 테이블 */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <NoticeTable
              notices={data?.items || []}
              onFilterByKeyword={handleFilter}
              onFilterByOrg={handleFilter}
              onSelectNotice={setSelectedNotice}
            />
          )}
        </div>

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center mt-6 gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="w-9 h-9 flex items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 disabled:opacity-30"
            >
              <i className="ri-arrow-left-s-line"></i>
            </button>
            {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map(
              (p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-9 h-9 flex items-center justify-center rounded-lg text-sm ${
                    p === page
                      ? "bg-blue-600 text-white font-medium"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {p}
                </button>
              )
            )}
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="w-9 h-9 flex items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 disabled:opacity-30"
            >
              <i className="ri-arrow-right-s-line"></i>
            </button>
          </div>
        )}
      </div>

      {/* 공고 상세 모달 */}
      {selectedNotice && (
        <NoticeModal
          notice={selectedNotice}
          onClose={() => setSelectedNotice(null)}
        />
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import type { BidNotice } from "@/types";

interface Props {
  notice: BidNotice;
  onClose: () => void;
}

function formatBudget(budget: number | null): string {
  if (!budget) return "—";
  if (budget >= 100000000) return `${(budget / 100000000).toFixed(1)}억원`;
  if (budget >= 10000) return `${Math.floor(budget / 10000).toLocaleString()}만원`;
  return `${budget.toLocaleString()}원`;
}

function getDday(endDate: string | null): { text: string; color: string } {
  if (!endDate) return { text: "—", color: "text-gray-400" };
  const diff = Math.ceil(
    (new Date(endDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
  );
  if (diff < 0) return { text: "마감", color: "text-gray-400" };
  if (diff <= 3) return { text: `D-${diff}`, color: "text-red-600" };
  return { text: `D-${diff}`, color: "text-blue-600" };
}

export default function NoticeModal({ notice: initialNotice, onClose }: Props) {
  const [notice, setNotice] = useState(initialNotice);
  const [loading, setLoading] = useState(false);

  // ESC 키로 닫기
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  // 상세 API 호출 (2단계 로딩: 리스트 데이터 즉시 표시 → 상세 보충)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<BidNotice>(`/api/notices/${initialNotice.id}`)
      .then((res) => {
        if (!cancelled) setNotice(res.data);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [initialNotice.id]);

  const dday = getDday(notice.end_date);
  const ex = (notice.extra || {}) as Record<string, string | number | null>;
  const isNara = notice.source_name === "나라장터";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-2xl w-[90%] max-w-[720px] max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-start justify-between rounded-t-xl z-10">
          <div className="flex-1 min-w-0 pr-4">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-medium">
                {notice.source_name}
              </span>
              <span
                className={`text-xs font-semibold ${
                  notice.status === "ongoing"
                    ? "bg-green-50 text-green-700"
                    : "bg-gray-100 text-gray-500"
                } px-2 py-0.5 rounded`}
              >
                {notice.status === "ongoing" ? "진행중" : "마감"}
              </span>
              <span className={`text-xs font-bold ${dday.color}`}>
                {dday.text}
              </span>
            </div>
            <h2 className="text-lg font-bold text-gray-900 leading-snug">
              {notice.title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 shrink-0"
          >
            <i className="ri-close-line text-xl"></i>
          </button>
        </div>

        {/* Loading indicator */}
        {loading && (
          <div className="px-6 py-2 text-xs text-blue-500 flex items-center gap-2 bg-blue-50">
            <span className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></span>
            상세 정보 불러오는 중...
          </div>
        )}

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* 기본 정보 */}
          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            <InfoRow label="발주기관" value={notice.organization} />
            <InfoRow label="공고번호" value={notice.bid_no} />
            <InfoRow label="공고등록일" value={notice.start_date || "—"} />
            <InfoRow label="마감일" value={notice.end_date || "—"} />
            <InfoRow label="예산" value={formatBudget(notice.budget)} />
            {notice.region && <InfoRow label="지역" value={notice.region} />}
            {notice.category && <InfoRow label="분류" value={notice.category} />}
          </div>

          {/* 출처별 상세 필드 */}
          {isNara ? (
            /* 나라장터 전용 */
            <NaraExtra ex={ex} />
          ) : (
            /* K-Startup / 기업마당 / 중소벤처기업부 등 */
            <GeneralExtra ex={ex} />
          )}

          {/* 키워드 */}
          {(notice.matched_keywords || []).length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">매칭 키워드</h3>
              <div className="flex flex-wrap gap-1.5">
                {notice.matched_keywords.map((kw) => (
                  <span
                    key={kw}
                    className="text-xs bg-yellow-50 text-yellow-700 px-2 py-1 rounded font-medium"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 공고 내용 */}
          {notice.content && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">공고 내용</h3>
              <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-4 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                {notice.content}
              </div>
            </div>
          )}

          {/* 첨부파일 */}
          {notice.attachments && notice.attachments.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                <i className="ri-attachment-2 mr-1"></i>
                첨부파일 ({notice.attachments.length}건)
              </h3>
              <div className="space-y-1.5">
                {notice.attachments.map((file, idx) => (
                  <a
                    key={idx}
                    href={file.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-blue-50 rounded-lg transition-colors group"
                  >
                    <i className="ri-file-download-line text-gray-400 group-hover:text-blue-600"></i>
                    <span className="text-sm text-gray-700 group-hover:text-blue-600 truncate">
                      {file.name || `첨부파일 ${idx + 1}`}
                    </span>
                    <i className="ri-external-link-line text-gray-300 group-hover:text-blue-400 ml-auto shrink-0"></i>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* 링크 버튼 */}
          <div className="flex gap-3 pt-2">
            {notice.url && (
              <a
                href={notice.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <i className="ri-external-link-line"></i>
                공고 사이트 바로가기
              </a>
            )}
            {ex.apply_url && (
              <a
                href={String(ex.apply_url)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <i className="ri-edit-line"></i>
                신청 페이지
              </a>
            )}
            {notice.detail_url && notice.detail_url !== notice.url && (
              <a
                href={notice.detail_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-lg text-sm font-medium transition-colors"
              >
                <i className="ri-file-text-line"></i>
                상세 페이지
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* 나라장터 전용 상세 필드 */
/* 실제 DB extra 키: bid_method, bid_type, budget, contact, est_price, open_date */
function NaraExtra({ ex }: { ex: Record<string, string | number | null> }) {
  const hasAny = ex.est_price || ex.bid_method || ex.bid_type || ex.open_date || ex.contact;

  if (!hasAny) return null;

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">나라장터 상세</h3>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {ex.est_price && <InfoRow label="추정 가격" value={formatPrice(ex.est_price)} />}
        {ex.bid_type && <InfoRow label="입찰 구분" value={String(ex.bid_type)} />}
        {ex.bid_method && <InfoRow label="입찰 방식" value={String(ex.bid_method)} />}
        {ex.open_date && <InfoRow label="개찰 일시" value={String(ex.open_date)} />}
        {ex.contact && <InfoRow label="담당자" value={String(ex.contact)} />}
      </div>
    </div>
  );
}

/* K-Startup / 기업마당 등 상세 필드 */
/* K-Startup 실제 키: apply_method, biz_name, biz_year, contact, department, excl_target, target, target_age */
/* 기업마당 실제 키: hashtags, reference, req_method, sub_category, target, view_count */
function GeneralExtra({ ex }: { ex: Record<string, string | number | null> }) {
  const hasAny = ex.biz_name || ex.target || ex.target_age || ex.biz_year ||
    ex.excl_target || ex.apply_method || ex.department || ex.contact ||
    ex.req_method || ex.sub_category || ex.hashtags || ex.reference;

  if (!hasAny) return null;

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">상세 정보</h3>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {ex.biz_name && <InfoRow label="사업명" value={String(ex.biz_name)} />}
        {ex.target && <InfoRow label="지원 대상" value={String(ex.target)} />}
        {ex.target_age && <InfoRow label="대상 연령" value={String(ex.target_age)} />}
        {ex.biz_year && <InfoRow label="창업 연차" value={String(ex.biz_year)} />}
        {ex.excl_target && <InfoRow label="제외 대상" value={String(ex.excl_target)} />}
        {ex.apply_method && <InfoRow label="접수 방법" value={String(ex.apply_method)} />}
        {ex.req_method && <InfoRow label="접수 방법" value={String(ex.req_method)} />}
        {ex.department && <InfoRow label="담당부서" value={String(ex.department)} />}
        {ex.contact && <InfoRow label="문의처" value={String(ex.contact)} />}
        {ex.sub_category && <InfoRow label="세부 분류" value={String(ex.sub_category)} />}
        {ex.hashtags && <InfoRow label="태그" value={String(ex.hashtags)} />}
        {ex.reference && <InfoRow label="참고" value={String(ex.reference)} />}
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs text-gray-400">{label}</span>
      <div className="text-sm text-gray-900 mt-0.5">{value}</div>
    </div>
  );
}

function formatPrice(value: string | number | null): string {
  if (!value) return "—";
  const num = typeof value === "string" ? parseInt(value.replace(/[^0-9]/g, ""), 10) : value;
  if (isNaN(num)) return String(value);
  return num.toLocaleString() + "원";
}

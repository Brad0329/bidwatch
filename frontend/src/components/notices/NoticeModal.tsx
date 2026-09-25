"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import type { BidNotice } from "@/types";

const TAG_OPTIONS = ["검토요청", "입찰대상", "제외", "낙찰", "유찰"] as const;
const TAG_COLORS: Record<string, string> = {
  검토요청: "bg-yellow-50 text-yellow-700 border-yellow-200",
  입찰대상: "bg-blue-50 text-blue-700 border-blue-200",
  제외: "bg-gray-100 text-gray-500 border-gray-200",
  낙찰: "bg-green-50 text-green-700 border-green-200",
  유찰: "bg-red-50 text-red-700 border-red-200",
};

interface Props {
  notice: BidNotice;
  onClose: () => void;
  onTagChange?: () => void;
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

export default function NoticeModal({ notice: initialNotice, onClose, onTagChange }: Props) {
  const [notice, setNotice] = useState(initialNotice);
  const [loading, setLoading] = useState(false);
  const [currentTag, setCurrentTag] = useState<string | null>(initialNotice.tag || null);
  const [tagSaving, setTagSaving] = useState(false);

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

  const noticeType = initialNotice.notice_type ?? "bid";

  // 상세 API 호출 (2단계 로딩: 리스트 데이터 즉시 표시 → 상세 보충)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const detailUrl =
      noticeType === "scraped"
        ? `/api/notices/scraped/${initialNotice.id}`
        : `/api/notices/${initialNotice.id}`;
    api
      .get<BidNotice>(detailUrl)
      .then((res) => {
        if (!cancelled) {
          setNotice(res.data);
          setCurrentTag(res.data.tag || null);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [initialNotice.id, noticeType]);

  const handleTagChange = async (newTag: string) => {
    if (tagSaving) return;
    setTagSaving(true);
    try {
      if (newTag === currentTag) {
        // 같은 태그 클릭 → 삭제
        const tagRes = await api.get(`/api/tags/notice/${noticeType}/${notice.id}`);
        if (tagRes.data) {
          await api.delete(`/api/tags/${tagRes.data.id}`);
        }
        setCurrentTag(null);
      } else {
        await api.put("/api/tags", {
          notice_type: noticeType,
          notice_id: notice.id,
          tag: newTag,
        });
        setCurrentTag(newTag);
      }
      onTagChange?.();
    } catch {
      // 실패 시 무시
    } finally {
      setTagSaving(false);
    }
  };

  const dday = getDday(notice.end_date);
  const ex: Extra = notice.extra || {};
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
              {/* URL 출처는 bid-collectors가 status를 마감일이 아닌 게시일로 판정해 믿을 수 없다 — 배지를 숨긴다(2026-09-25) */}
              {noticeType !== "scraped" && (
                <span
                  className={`text-xs font-semibold ${
                    notice.status === "ongoing"
                      ? "bg-green-50 text-green-700"
                      : "bg-gray-100 text-gray-500"
                  } px-2 py-0.5 rounded`}
                >
                  {notice.status === "ongoing" ? "진행중" : "마감"}
                </span>
              )}
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

        {/* 태그 선택 */}
        <div className="px-6 py-3 border-b border-gray-100 flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500 mr-1">태그</span>
          {TAG_OPTIONS.map((t) => (
            <button
              key={t}
              onClick={() => handleTagChange(t)}
              disabled={tagSaving}
              className={`text-xs px-2.5 py-1 rounded-full border font-medium transition-colors ${
                currentTag === t
                  ? TAG_COLORS[t]
                  : "bg-white text-gray-400 border-gray-200 hover:border-gray-300"
              } ${tagSaving ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            >
              {t}
            </button>
          ))}
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
            {/* 지역을 모르는 공고도 지역 필터에 걸려 나온다 — 빈칸 대신 사실대로 표시 */}
            <InfoRow label="지역" value={notice.region || "지역 미상"} />
            {notice.category && <InfoRow label="분류" value={notice.category} />}
          </div>

          {/* 출처별 상세 필드 */}
          {isNara ? (
            /* 나라장터 전용 */
            <NaraExtra ex={ex} bidNo={notice.bid_no} />
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
            {text(ex.apply_url) && (
              <a
                href={text(ex.apply_url)!}
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

/* extra = 출처 응답 원문 전부, 원래 키 이름 그대로 (bid-collectors v1.2.5).
   키의 뜻·출현 빈도는 docs/source_fields.md. 값은 str만이 아니라 int·list·dict일 수 있다. */
type Extra = Record<string, unknown>;
type Row = [label: string, value: string | null];

/* 원문 값 → 표시 문자열. 빈 값은 null (행을 숨긴다) */
function text(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  if (Array.isArray(v)) return v.map(text).filter(Boolean).join(", ") || null;
  if (typeof v === "object") return JSON.stringify(v);
  return String(v).trim() || null;
}

/* HTML 태그·엔티티 제거 — K-Startup·기업마당 원문에는 HTML과 엔티티가 그대로 온다.
   엔티티로 감싼 태그(&lt;p&gt;)도 있어 두 번 푼다 */
function plain(v: unknown): string | null {
  let s = text(v);
  if (!s) return null;
  if (typeof window !== "undefined") {
    for (let i = 0; i < 2; i++) {
      s = new DOMParser().parseFromString(s, "text/html").body.textContent ?? "";
    }
  } else {
    s = s.replace(/<[^>]*>/g, " ");
  }
  return s.replace(/\s+/g, " ").trim() || null;
}

function first(ex: Extra, ...keys: string[]): string | null {
  for (const k of keys) {
    const v = text(ex[k]);
    if (v) return v;
  }
  return null;
}

function ExtraSection({ title, rows }: { title: string; rows: Row[] }) {
  const shown = rows.filter((r): r is [string, string] => !!r[1]);
  // 옛 형식(영어 키) 행은 여기 키가 하나도 없다 — 재수집 전까지 섹션을 숨긴다
  if (shown.length === 0) return null;
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{title}</h3>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {shown.map(([label, value]) => (
          <InfoRow key={label} label={label} value={value} />
        ))}
      </div>
    </div>
  );
}

/* 나라장터 입찰공고 (용역·물품·공사) — 조달청 입찰공고정보서비스 원문 키 */
function NaraExtra({ ex, bidNo }: { ex: Extra; bidNo: string }) {
  const tech = text(ex.techAbltEvlRt);
  const price = text(ex.bidPrceEvlRt);
  const evalRatio =
    tech && price ? `기술 ${tech}% : 가격 ${price}%`
      : tech ? `기술 ${tech}%`
        : price ? `가격 ${price}%`
          : null;
  const officer = [text(ex.ntceInsttOfclNm), text(ex.ntceInsttOfclTelNo)].filter(Boolean).join(" ");

  const rows: Row[] = [
    ["추정 가격", formatPrice(ex.presmptPrce)],
    // 공사는 배정예산 태그가 없고 예산금액(bdgtAmt)으로 온다
    ["배정 예산", formatPrice(ex.asignBdgtAmt ?? ex.bdgtAmt)],
    ["입찰 방식", text(ex.bidMethdNm)],
    ["계약 방식", text(ex.cntrctCnclsMthdNm)],
    ["낙찰 방식", text(ex.sucsfbidMthdNm)],
    ["평가 비율", evalRatio],
    ["개찰 일시", text(ex.opengDt)],
    ["참가자격 등록 마감", text(ex.bidQlfctRgstDt)],
    ["담당자", officer || null],
    // 용역은 공고기관 담당자 이메일이 늘 비어 온다(source_fields.md §2)
    ["담당자 이메일", text(ex.ntceInsttOfclEmailAdrs)],
  ];
  if (rows.every(([, v]) => !v)) return null;

  // 용역/물품/공사는 응답에 없고 bid_no 접두사에만 있다
  const bidType = bidNo.split("-")[0];
  if (["용역", "물품", "공사"].includes(bidType)) rows.unshift(["입찰 구분", bidType]);

  return <ExtraSection title="나라장터 상세" rows={rows} />;
}

/* K-Startup / 기업마당 — 출처끼리 키가 겹치지 않아 한 목록으로 둔다 */
function GeneralExtra({ ex }: { ex: Extra }) {
  const rows: Row[] = [
    ["사업명", plain(ex.intg_pbanc_biz_nm)],
    ["지원 대상", plain(ex.aply_trgt_ctnt) ?? plain(ex.trgetNm)],
    ["대상 연령", text(ex.biz_trgt_age)],
    ["창업 기간", text(ex.biz_enyy)],
    ["제외 대상", plain(ex.aply_excl_trgt_ctnt)],
    ["접수 방법",
      plain(first(ex, "aply_mthd_onli_rcpt_istc", "aply_mthd_vst_rcpt_istc", "aply_mthd_etc_istc"))
      ?? plain(ex.reqstMthPapersCn)],
    ["담당부서", plain(ex.biz_prch_dprt_nm)],
    ["문의처", text(ex.prch_cnpl_no)],
    ["세부 분류", text(ex.pldirSportRealmMlsfcCodeNm)],
    ["태그", text(ex.hashtags)],
    ["참고", plain(ex.refrncNm)],
  ];
  return <ExtraSection title="상세 정보" rows={rows} />;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs text-gray-400">{label}</span>
      <div className="text-sm text-gray-900 mt-0.5">{value}</div>
    </div>
  );
}

/* 나라장터 금액은 문자열("456714000")로 온다 */
function formatPrice(value: unknown): string | null {
  const s = text(value);
  if (!s) return null;
  const num = Number(s.replace(/[^0-9.]/g, ""));
  if (!s.match(/\d/) || isNaN(num)) return s;
  return Math.round(num).toLocaleString() + "원";
}

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
  nested?: boolean; // 연결 공고(F-018)로 위에 겹쳐 연 모달 — 페이지 스크롤 잠금은 바깥 모달이 맡는다
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

export default function NoticeModal({ notice: initialNotice, onClose, onTagChange, nested }: Props) {
  const [notice, setNotice] = useState(initialNotice);
  const [loading, setLoading] = useState(false);
  const [currentTag, setCurrentTag] = useState<string | null>(initialNotice.tag || null);
  const [tagSaving, setTagSaving] = useState(false);
  const [linked, setLinked] = useState<BidNotice | null>(null);
  const [linkLoading, setLinkLoading] = useState(false);

  // ESC 키로 닫기 — 연결 공고 모달이 떠 있으면 그쪽이 먼저 닫힌다
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !linked) onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    if (!nested) document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (!nested) document.body.style.overflow = "";
    };
  }, [onClose, linked, nested]);

  const openLinked = async (id: number) => {
    if (linkLoading) return;
    setLinkLoading(true);
    try {
      const res = await api.get<BidNotice>(`/api/notices/${id}`);
      setLinked({ ...res.data, notice_type: "bid" });
    } catch (err) {
      console.error("연결 공고 상세 조회 실패", err);
    } finally {
      setLinkLoading(false);
    }
  };

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
  // K-Startup 상세 보충의 apply_url, 없으면 기업마당 사업신청URL
  const applyUrl = text(ex.apply_url) ?? text(ex.rceptEngnHmpgUrl);
  const stdDocUrl = text(ex.stdNtceDocUrl);
  // 알리오 상세의 원문 링크(refrUrl) — 있으면 원문이 주 버튼, 알리오 게시물은 보조 버튼
  const originUrl = originHref(text(ex.refrUrl));

  return (
    <>
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
                    notice.status === "cancelled"
                      ? "bg-red-50 text-red-700"
                      : notice.status === "ongoing"
                        ? "bg-green-50 text-green-700"
                        : "bg-gray-100 text-gray-500"
                  } px-2 py-0.5 rounded`}
                >
                  {notice.status === "cancelled" ? "취소" : notice.status === "ongoing" ? "진행중" : "마감"}
                </span>
              )}
              {notice.status !== "cancelled" && (
                <span className={`text-xs font-bold ${dday.color}`}>
                  {dday.text}
                </span>
              )}
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
          ) : institutionOf(notice.bid_no) ? (
            /* 자체조달 기관 (LH·가스공사·국방·수자원, bid-collectors v1.4.0) */
            <InstitutionExtra ex={ex} kind={institutionOf(notice.bid_no)!} />
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

          {/* 연결된 공고 — 사전규격 ↔ 본 공고(F-018), 알리오 → 나라장터 */}
          {(notice.related || []).length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">연결된 공고</h3>
              <div className="space-y-1.5">
                {notice.related!.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => openLinked(r.id)}
                    disabled={linkLoading}
                    className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-blue-50 rounded-lg transition-colors group text-left disabled:opacity-50"
                  >
                    <span className="text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded shrink-0">
                      {r.kind === "prespec" ? "사전규격 보기" : r.kind === "nara" ? "나라장터 공고 보기" : "본 공고 보기"}
                    </span>
                    <span className="text-sm text-gray-700 group-hover:text-blue-600 truncate">{r.title}</span>
                    {r.status === "cancelled" && (
                      <span className="text-xs font-semibold bg-red-50 text-red-700 px-2 py-0.5 rounded shrink-0">취소</span>
                    )}
                  </button>
                ))}
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
            {originUrl && (
              <a
                href={originUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <i className="ri-external-link-line"></i>
                원문 바로가기{originSiteName(originUrl) ? ` (${originSiteName(originUrl)})` : ""}
              </a>
            )}
            {notice.url && (
              <a
                href={notice.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  originUrl
                    ? "border border-gray-200 hover:bg-gray-50 text-gray-700"
                    : "bg-blue-600 hover:bg-blue-700 text-white"
                }`}
              >
                <i className={originUrl ? "ri-file-text-line" : "ri-external-link-line"}></i>
                {originUrl ? "알리오 공고" : "공고 사이트 바로가기"}
              </a>
            )}
            {applyUrl && (
              <a
                href={applyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <i className="ri-edit-line"></i>
                신청 페이지
              </a>
            )}
            {stdDocUrl && (
              <a
                href={stdDocUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-lg text-sm font-medium transition-colors"
              >
                <i className="ri-file-download-line"></i>
                표준공고서
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
    {/* 연결 공고는 바깥 오버레이의 자식이 아니라 형제로 — 클릭이 바깥 모달의 닫기로 번지지 않게 */}
    {linked && (
      <NoticeModal notice={linked} onClose={() => setLinked(null)} onTagChange={onTagChange} nested />
    )}
    </>
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
        {shown.map(([label, value], i) => (
          // 같은 이름의 행이 올 수 있다(필요 면허 "주" 둘 등) — 순번을 키에 섞는다
          <InfoRow key={`${label}-${i}`} label={label} value={value} />
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

  // 입찰 참가 판단용 — 값이 있는 것만. Y/N 플래그는 Y일 때만 보인다(N은 "제한 없음"이라 적을 게 없다)
  const kind = text(ex.ntceKindNm);
  const lwlt = text(ex.sucsfbidLwltRate);
  const briefing = [text(ex.dcmtgOprtnDt), text(ex.dcmtgOprtnPlce)].filter(Boolean).join(" · ");
  const conditions: Row[] = [
    ["공고 종류", kind && kind !== "등록공고" ? kind : null],
    ["변경·취소 사유", text(ex.chgNtceRsn)],
    // 실제 참가 가능 지역 목록은 별도 API라 없다 — 여기는 "소재지를 무엇으로 보나"의 기준
    ["지역제한 판단기준", text(ex.rgnLmtBidLocplcJdgmBssNm)],
    ["업종 제한", text(ex.indstrytyLmtYn) === "Y" ? "있음 (공고서 참고)" : null],
    ["공동수급", text(ex.cmmnSpldmdMethdNm)],
    ["낙찰하한율", lwlt ? `${lwlt}%` : null],
    ["설명회", briefing || null],
    ["공사 현장", text(ex.cnstrtsiteRgnNm)],
  ];

  return (
    <>
      <ExtraSection title="나라장터 상세" rows={rows} />
      <ExtraSection title="입찰 참가 조건" rows={conditions} />
    </>
  );
}

/* 자체조달 기관 — bid_no 접두사로 가린다(출처 이름은 바꿀 수 있어서). 키의 뜻: docs/source_fields.md 기관 출처 절 */
type Institution = "LH" | "KOGAS" | "D2B" | "KWATER";

function institutionOf(bidNo: string): Institution | null {
  const prefix = bidNo.split("-")[0];
  return (["LH", "KOGAS", "D2B", "KWATER"] as const).find((p) => p === prefix) ?? null;
}

/* 금액은 이름별로 늘 보인다 — 값이 없으면 "-" (2026-09-26 사용자 요청). budget은 bid-collectors가 비워 둔다 */
function amount(v: unknown): string {
  return formatPrice(v) ?? "-";
}

/* 국방 "202609281030"·"20260928" → "2026-09-28 10:30". 그 밖의 형식은 그대로 */
function dt(v: unknown): string | null {
  const s = text(v);
  if (!s) return null;
  const m = s.match(/^(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2}))?$/);
  if (!m) return s;
  return `${m[1]}-${m[2]}-${m[3]}` + (m[4] ? ` ${m[4]}:${m[5]}` : "");
}

/* LH 필요 면허 — req{n}Reqlic{k}Nm(면허 이름)·req{n}MvgbNm(주/부업종)·req{n}LicctNm(등록 조건) */
function lhLicenses(ex: Extra): Row[] {
  const rows: Row[] = [];
  for (let n = 1; n <= 5; n++) {
    const names = [1, 2, 3, 4, 5].map((k) => text(ex[`req${n}Reqlic${k}Nm`])).filter(Boolean);
    if (names.length === 0) continue;
    const cond = text(ex[`req${n}LicctNm`]);
    rows.push([`필요 면허 ${text(ex[`req${n}MvgbNm`]) ?? n}`, names.join(", ") + (cond ? ` — ${cond}` : "")]);
  }
  return rows;
}

/* 상세(fetch_detail, bid-collectors v1.5.0) 원문의 빈 표기 — 가스공사는 "()"·"~"·"%,"를 그대로 준다 */
function filled(v: unknown): string | null {
  const s = text(v);
  return s && !/^[\s()~%,.\-]*$/.test(s) ? s : null;
}

/* 담당자 이름 + 연락처 한 줄 */
function person(name: unknown, contact: unknown): string | null {
  return [filled(name), filled(contact)].filter(Boolean).join(" ") || null;
}

/* 국방 지역·면허 제한 목록 — 원문 구분자가 "^"(국내)와 "|"(시설) 둘 다 온다(2026-09-26 실측) */
function splitList(v: unknown): string | null {
  const s = text(v);
  return s ? s.split(/[\^|]/).map((x) => x.trim()).filter(Boolean).join(" · ") : null;
}

/* 수자원 입찰 일정 — tndrPrgsOrdrList [{prgsDivNm, strtDt, closDt}] (상세에만 있다) */
function kwaterSchedule(ex: Extra): Row[] {
  const list = Array.isArray(ex.tndrPrgsOrdrList) ? (ex.tndrPrgsOrdrList as Extra[]) : [];
  return list.map((step, i): Row => [
    text(step.prgsDivNm) ?? `단계 ${i + 1}`,
    [dt(step.strtDt), dt(step.closDt)].filter(Boolean).join(" ~ ") || null,
  ]);
}

/* LH 상세의 요구면허 표 — [{"주/부구분", "요구면허1", "업종"}]. 목록의 req{n}Reqlic 키가 없을 때만 쓴다 */
function lhDetailLicenses(ex: Extra): Row[] {
  const list = Array.isArray(ex["요구면허"]) ? (ex["요구면허"] as Extra[]) : [];
  return list.map((r, i): Row => [
    `필요 면허 ${text(r["주/부구분"]) ?? i + 1}`,
    [text(r["요구면허1"]), text(r["업종"])].filter(Boolean).join(" — ") || null,
  ]);
}

function InstitutionExtra({ ex, kind }: { ex: Extra; kind: Institution }) {
  let title: string;
  let amounts: Row[] = [];
  let rows: Row[];
  let schedule: Row[] = [];
  // 목록(수집 시) 키가 먼저, 없으면 상세(팝업을 처음 열 때 받는다) 키 — 상세 키 이름은 원문 그대로(handover v1.5.0 §1)
  if (kind === "LH") {
    title = "LH 상세";
    const d = (k: string) => ex[`공고일반정보/${k}`];
    amounts = [
      ["추정 가격", amount(text(ex.presmtPrc) ?? d("추정가격"))], ["설계가", amount(text(ex.designPrc) ?? d("설계가격"))],
      ["기초 금액", amount(text(ex.fdmtlAmt) ?? d("기초금액"))], ["부가세", amount(text(ex.addtTax) ?? d("부가가치세"))],
    ];
    const kindNm = text(ex.bidKind);
    const zones = [1, 2, 3, 4].map((i) => text(ex[`zoneRstrct${i}`]) ?? text(ex[`투찰제한정보/참가지역${i}`]))
      .filter(Boolean).join(", ");
    const licenses = lhLicenses(ex);
    rows = [
      ["공고 종류", kindNm && kindNm !== "일반공고" ? kindNm : null],
      ["업무 구분", text(ex.cstrtnJobGbNm) ?? text(d("업종유형"))],
      ["계약 방법", text(ex.tndrCtrctMedCd) ?? text(ex["계약및입찰방식정보/계약방법"])],
      ["낙찰자 선정", text(ex.sunjungNm) ?? text(ex["계약및입찰방식정보/낙찰자선정방법"])],
      ["공동수급", text(ex.gongdongNm) ?? text(ex["입찰진행정보/공동수급협정서 접수/구성 방식"])],
      ["지역 제한", zones || null],
      ["공고 부서", text(d("공고부서"))],
      ["담당 본부", text(ex.zoneHqCd)?.replace(/\s+/g, "") ?? null],
      ...(licenses.length > 0 ? licenses : lhDetailLicenses(ex)),
      ["업종 제한", text(ex.antbsncatRstrctFg)],
    ];
    schedule = [
      ["입찰서 접수",
        [dt(ex.tndrdocAcptBgninDtm) ?? text(ex["입찰진행정보/입찰서접수개시일시"]),
          dt(ex.tndrdocAcptEndDtm) ?? text(ex["입찰진행정보/입찰서접수마감일시"])].filter(Boolean).join(" ~ ") || null],
      ["개찰 일시", dt(ex.openDtm) ?? text(ex["입찰진행정보/개찰일시"])],
      ["재입찰", text(ex["입찰진행정보/재입찰"])],
    ];
  } else if (kind === "D2B") {
    title = "국방전자조달 상세";
    amounts = [
      ["추정 가격", amount(ex.estmPrce)],
      ["기초예비가격", amount(ex.bsicExpt)], ["기초 금액", amount(ex.baseAmnt)], ["예산", amount(ex.budgetAmount)],
    ];
    const lwlt = text(ex.scsbidLwltRt);
    const lo = text(ex.asessRtLwlt);
    const hi = text(ex.asessRtUplmt);
    const briefing = [dt(ex.bsnsDcMeetngDt), text(ex.bsnsDcMeetngPlace)].filter(Boolean).join(" · ");
    rows = [
      ["공고 구분", text(ex.pblancSe)],
      ["진행 상태", text(ex.progrsSttus)],
      ["계약 방법", text(ex.cntrctMth)],
      ["입찰 방법", text(ex.bidMth)],
      ["낙찰 방법", text(ex.sucbidrDecsnMth)],
      // 0은 "해당 없음"으로 온다(실측 — 최저가격제 공고의 하한율 0.000, 사정률 0.00~0.00)
      ["낙찰하한율", lwlt && Number(lwlt) !== 0 ? `${lwlt}%` : null],
      ["사정률", lo && hi && !(Number(lo) === 0 && Number(hi) === 0) ? `${lo}% ~ ${hi}%` : null],
      ["집행 유형", text(ex.excutTy)],
      ["공사 현장", text(ex.lc)],
      ["공사 기간", filled(ex.cntrwkPd)],
      ["지역 제한", splitList(ex.areaLmttList)],
      ["면허 제한", splitList(ex.lcnsLmttList)],
      ["입찰 장소", text(ex.bidPlace)],
      ["담당자", person(ex.chargerNm, ex.chargerCttpc)],
      ["기초가격 공개", text(ex.bsisPrdprcOthbcAt)],
    ];
    schedule = [
      ["참가등록 마감", dt(ex.bidPartcptRegistClosDt) ?? dt(ex.bidPartcptReqstClosDt)],
      ["입찰서 마감", dt(ex.biddocPresentnClosDt) ?? dt(ex.bidRegistClosDt)],
      ["견적서 마감", dt(ex.prqudoPresentnClosDt)],
      ["사업 설명회", briefing || null],
      ["협상 예정일", dt(ex.ntatPlanDate)],
      ["개찰 일시", dt(ex.opengDt)],
    ];
  } else if (kind === "KWATER") {
    title = "수자원공사 상세";
    // 예정가격 0은 "미공개"(2026-09-26 사용자 결정 — 실측 51건 중 41건이 0)
    const plan = text(ex.tndrPlnprc);
    amounts = [
      ["요청 금액", amount(ex.rqestAmt)],
      ["예정 가격", plan !== null && Number(plan) === 0 ? "미공개" : amount(plan)],
    ];
    rows = [
      ["계약 구분", text(ex.cntrctDivNm)],
      ["계약 방법", text(ex.ctrmthdCdNm)],
      ["제한 방법", text(ex.lmttMthCdNm)],
      ["입찰 방법", text(ex.tndrMthNm)],
      ["낙찰자 결정", text(ex.sucbidrDcsnMthCdNm)],
      ["진행 상태", text(ex.tndrStat)],
      ["계약 부서", text(ex.cntrctDeptNm)],
      ["담당자", person(ex.intnChargerNm, ex.intnChargerTelno)],
      ["담당자 이메일", text(ex.intnChargerEmail)?.toLowerCase() ?? null],
      ["입찰 장소", text(ex.tndrPlaceInfo)],
      ["참가 자격 유의", text(ex.tndrQualfAtpn)],
    ];
    schedule = kwaterSchedule(ex);
  } else {
    title = "가스공사 상세";
    // 금액은 상세에만 있다. 견적 공고의 추정가격은 1·30 같은 가짜 값("별도 산정 금액이 아님")이라 보이지 않는다
    // (handover v1.5.0 §1 — 표본 26건 중 13건). 견적 공고는 "견적방법" 키로 가린다
    const quote = filled(ex["견적방법"]);
    if (quote) {
      amounts = [["금액", "견적 공고 — 추정가격 없음"]];
    } else if (filled(ex["추정가격"]) || filled(ex["합계금액"])) {
      amounts = [
        ["추정 가격", amount(ex["추정가격"])], ["부가세", amount(ex["부가세"])], ["합계 금액", amount(ex["합계금액"])],
      ];
    }
    // 취소 공고는 진행상태가 "공고중"으로 남고 진행안내에만 취소가 적힌다(handover v1.5.0 §1)
    const guide = filled(ex["진행안내"]);
    const licenses = filled(ex["면허사항제한"]);
    rows = [
      ["업무 구분", text(ex.WORK_TYPE_NAME) ?? filled(ex["업무구분"])],
      ["계약 방법", text(ex.CONT_METHOD_NAME) ?? filled(ex["계약방법"])],
      ["입찰 방식", text(ex.BID_TYPE_NAME)],
      ["견적 방법", quote],
      ["진행 상태", guide?.includes("취소") ? "취소" : filled(ex["진행상태"])],
      ["예정가격 결정", filled(ex["예정가격결정방식"])],
      ["도급 형태", filled(ex["도급형태"])],
      ["지역 제한", filled(ex["지역제한"])],
      // 제한이 없으면 "업종그룹1 - 업종그룹2 - …" 빈 틀만 온다
      ["면허 제한", licenses && !/^(업종그룹\d\s*-\s*)+$/.test(licenses) ? licenses : null],
      ["납품 장소", filled(ex["납품장소"])],
      ["계약 기간", filled(ex["계약기간"])],
      ["계약 담당", person(ex["계약담당(공고등록,개찰)"], ex["계약담당 연락처"])],
      ["규격 담당", person(ex["규격담당(소요부서)"], ex["규격담당 연락처"])],
    ];
    schedule = [
      ["공고 일시", filled(ex["공고일시"])],
      // 공고 부류마다 마감 항목 이름이 다르다(handover v1.5.0 §1)
      ["입찰 마감", filled(ex["입찰신청및입찰마감일시"]) ?? filled(ex["입찰마감"])],
      ["개찰 일시", text(ex.OPEN_DT) ?? filled(ex["개찰일시"])],
      ["개찰 장소", filled(ex["개찰장소"])],
    ];
  }
  return (
    <>
      {amounts.length > 0 && <ExtraSection title="금액" rows={amounts} />}
      <ExtraSection title={title} rows={rows} />
      <ExtraSection title="입찰 일정" rows={schedule} />
    </>
  );
}

/* K-Startup / 기업마당 — 출처끼리 키가 겹치지 않아 한 목록으로 둔다 */
function GeneralExtra({ ex }: { ex: Extra }) {
  const rows: Row[] = [
    ["사업명", plain(ex.intg_pbanc_biz_nm)],
    ["지원 대상", plain(ex.aply_trgt_ctnt) ?? plain(ex.trgetNm)],
    ["신청 대상 유형", text(ex.aply_trgt)],
    ["대상 연령", text(ex.biz_trgt_age)],
    ["창업 기간", text(ex.biz_enyy)],
    ["제외 대상", plain(ex.aply_excl_trgt_ctnt)],
    ["접수 방법",
      plain(first(ex, "aply_mthd_onli_rcpt_istc", "aply_mthd_vst_rcpt_istc", "aply_mthd_etc_istc"))
      ?? plain(ex.reqstMthPapersCn)],
    ["이메일 접수", text(ex.aply_mthd_eml_rcpt_istc)],
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

/* 알리오 원문 링크 도메인 → 버튼에 붙일 사이트 이름 (실측 2026-09-25: 나라장터·온비드·한전·수자원·LH·한수원) */
const ORIGIN_SITES: [string, string][] = [
  ["g2b.go.kr", "나라장터"],
  ["onbid.co.kr", "온비드"],
  ["srm.kepco.net", "한전 전자입찰"],
  ["kwater.or.kr", "수자원공사 전자입찰"],
  ["lh.or.kr", "LH 전자조달"],
  ["khnp.co.kr", "한수원 전자입찰"],
  ["kogas.or.kr", "가스공사 전자입찰"],
];

/* 알리오 refrUrl 원문 → 링크 주소. 원문 전달 원칙이라 보정은 표시 쪽 몫(bid-collectors institution_sources.md §5 실측):
   LH는 "https://" 없이 오고, 가스공사는 "&amp;amp;"처럼 이중 이스케이프로 온다. http(s)가 아니면 버튼을 숨긴다 */
function originHref(raw: string | null): string | null {
  if (!raw) return null;
  let s = raw;
  while (s.includes("&amp;")) s = s.replace(/&amp;/g, "&");
  if (!/^[a-z][a-z0-9+.-]*:/i.test(s)) s = "https://" + s.replace(/^\/+/, "");
  try {
    const u = new URL(s);
    if (u.protocol === "http:" || u.protocol === "https:") return u.href;
  } catch {
    // 아래 경고로 넘어간다
  }
  console.warn("알리오 원문 링크를 주소로 못 읽어 버튼을 숨김:", raw);
  return null;
}

function originSiteName(url: string): string | null {
  let host: string;
  try {
    host = new URL(url).hostname;
  } catch {
    return null; // 주소 형식이 아니면 이름 없이 "원문 바로가기"만
  }
  return ORIGIN_SITES.find(([domain]) => host.endsWith(domain))?.[1] ?? null;
}

/* 나라장터 금액은 문자열("456714000")로 온다 */
function formatPrice(value: unknown): string | null {
  const s = text(value);
  if (!s) return null;
  const num = Number(s.replace(/[^0-9.]/g, ""));
  if (!s.match(/\d/) || isNaN(num)) return s;
  return Math.round(num).toLocaleString() + "원";
}

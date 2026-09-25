"use client";

import {
  useSystemSources,
  useSystemSubscriptions,
  useUrlSubscriptions,
} from "@/lib/queries/useSources";

/** 공공 출처는 source_id, 직접 추가한 사이트는 scraper_id, 묶음 전체는 category로 좁힌다(백엔드 /api/notices 규칙). */
export type SourceFilter = { source_id?: number; scraper_id?: number; category?: "bid" | "support" };

const encode = (f: SourceFilter) =>
  f.source_id ? `sys:${f.source_id}` : f.scraper_id ? `url:${f.scraper_id}` : f.category ? `cat:${f.category}` : "";

const decode = (v: string): SourceFilter => {
  const [kind, id] = v.split(":");
  if (kind === "sys") return { source_id: Number(id) };
  if (kind === "url") return { scraper_id: Number(id) };
  if (kind === "cat" && (id === "bid" || id === "support")) return { category: id };
  return {};
};

export default function SourceSelect({
  value,
  onChange,
  preSpec = false,
}: {
  value: SourceFilter;
  onChange: (f: SourceFilter) => void;
  /** 입찰 예고: 출처가 나라장터 사전규격으로 고정(F-008) — 구독과 무관하게 그 출처만 */
  preSpec?: boolean;
}) {
  const { data: systemSources } = useSystemSources();
  const { data: subscribedIds } = useSystemSubscriptions();
  const { data: urlSubs } = useUrlSubscriptions();

  const system = (systemSources || []).filter((s) =>
    preSpec ? s.collector_type === "nara_prespec" : subscribedIds?.includes(s.id)
  );
  // 공고 목록의 출처 이름과 같은 규칙: 사용자가 정한 이름 → 없으면 AI가 읽은 이름
  const sites = preSpec
    ? []
    : (urlSubs || []).filter((s) => s.is_active && s.scraper_status === "ready");

  return (
    <select
      value={encode(value)}
      onChange={(e) => onChange(decode(e.target.value))}
      className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent max-w-[14rem]"
    >
      <option value="">전체 출처</option>
      {/* 입찰 전문 + 지원사업 선택 구독(2026-09-25) — 묶음 전체. 직접 추가 사이트는 입찰 묶음 */}
      {!preSpec && <option value="cat:bid">전체 출처(입찰)</option>}
      {!preSpec && <option value="cat:support">전체 출처(지원)</option>}
      {system.length > 0 && (
        <optgroup label="공공 출처">
          {system.map((s) => (
            <option key={`sys:${s.id}`} value={`sys:${s.id}`}>
              {s.name}
            </option>
          ))}
        </optgroup>
      )}
      {sites.length > 0 && (
        <optgroup label="직접 추가한 사이트">
          {sites.map((s) => (
            <option key={`url:${s.scraper_id}`} value={`url:${s.scraper_id}`}>
              {s.custom_name || s.scraper_name}
            </option>
          ))}
        </optgroup>
      )}
    </select>
  );
}

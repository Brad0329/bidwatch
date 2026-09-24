"use client";

import {
  useSystemSources,
  useSystemSubscriptions,
  useUrlSubscriptions,
} from "@/lib/queries/useSources";

/** 공공 출처는 source_id, 직접 추가한 사이트는 scraper_id로 좁힌다(백엔드 /api/notices 규칙). */
export type SourceFilter = { source_id?: number; scraper_id?: number };

const encode = (f: SourceFilter) =>
  f.source_id ? `sys:${f.source_id}` : f.scraper_id ? `url:${f.scraper_id}` : "";

const decode = (v: string): SourceFilter => {
  const [kind, id] = v.split(":");
  if (kind === "sys") return { source_id: Number(id) };
  if (kind === "url") return { scraper_id: Number(id) };
  return {};
};

export default function SourceSelect({
  value,
  onChange,
}: {
  value: SourceFilter;
  onChange: (f: SourceFilter) => void;
}) {
  const { data: systemSources } = useSystemSources();
  const { data: subscribedIds } = useSystemSubscriptions();
  const { data: urlSubs } = useUrlSubscriptions();

  const system = (systemSources || []).filter((s) => subscribedIds?.includes(s.id));
  // 공고 목록의 출처 이름과 같은 규칙: 사용자가 정한 이름 → 없으면 AI가 읽은 이름
  const sites = (urlSubs || []).filter((s) => s.is_active && s.scraper_status === "ready");

  return (
    <select
      value={encode(value)}
      onChange={(e) => onChange(decode(e.target.value))}
      className="px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent max-w-[14rem]"
    >
      <option value="">전체 출처</option>
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

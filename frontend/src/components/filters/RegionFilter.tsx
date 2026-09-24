"use client";

import { useState, useRef, useEffect } from "react";
import { useRegionList } from "@/lib/queries/useRegions";

interface RegionFilterProps {
  selected: string[];
  onChange: (regions: string[]) => void;
}

export default function RegionFilter({ selected, onChange }: RegionFilterProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data: regions = [] } = useRegionList();

  // 외부 클릭 시 닫기
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const toggle = (region: string) => {
    if (selected.includes(region)) {
      onChange(selected.filter((r) => r !== region));
    } else {
      onChange([...selected, region]);
    }
  };

  const clearAll = () => {
    onChange([]);
  };

  const label =
    selected.length === 0
      ? "전체 지역"
      : selected.length <= 2
        ? selected.join(", ")
        : `${selected.slice(0, 2).join(", ")} 외 ${selected.length - 2}`;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
          selected.length > 0
            ? "bg-indigo-50 text-indigo-700 border-indigo-300"
            : "bg-white text-gray-500 border-gray-200 hover:border-gray-300"
        }`}
      >
        <i className="ri-map-pin-line"></i>
        {label}
        <i className={`ri-arrow-${open ? "up" : "down"}-s-line text-[10px]`}></i>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-3 w-72">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-600">지역 선택</span>
            {selected.length > 0 && (
              <button
                onClick={clearAll}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                전체 해제
              </button>
            )}
          </div>
          <div className="grid grid-cols-4 gap-1.5">
            {regions.map((r) => (
              <button
                key={r}
                onClick={() => toggle(r)}
                className={`text-xs px-2 py-1.5 rounded-md border transition-colors ${
                  selected.includes(r)
                    ? "bg-indigo-50 text-indigo-700 border-indigo-300 font-medium"
                    : "bg-white text-gray-600 border-gray-100 hover:border-gray-300"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

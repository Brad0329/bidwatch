"use client";

import { useState } from "react";
import { useRunCollection } from "@/lib/queries/useAdmin";
import { useQueryClient } from "@tanstack/react-query";

interface Props {
  sourceId: number;
  sourceName: string;
  lastCollectedAt: string | null;
}

function toLocalDateStr(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function calcDays(fromDate: string): number {
  const from = new Date(fromDate);
  const now = new Date();
  from.setHours(0, 0, 0, 0);
  now.setHours(0, 0, 0, 0);
  const diff = Math.ceil((now.getTime() - from.getTime()) / (1000 * 60 * 60 * 24));
  return Math.max(diff, 1);
}

export default function CollectionButton({
  sourceId,
  sourceName,
  lastCollectedAt,
}: Props) {
  const defaultDate = lastCollectedAt
    ? toLocalDateStr(new Date(lastCollectedAt))
    : toLocalDateStr(new Date(Date.now() - 86400000));

  const [fromDate, setFromDate] = useState(defaultDate);
  const [result, setResult] = useState<string | null>(null);
  const mutation = useRunCollection();
  const qc = useQueryClient();

  const handleCollect = () => {
    setResult(null);
    const days = calcDays(fromDate);
    mutation.mutate(
      { source_id: sourceId, days, sync: true },
      {
        onSuccess: (data) => {
          setResult(data.message);
          qc.invalidateQueries({ queryKey: ["system-sources"] });
        },
        onError: (err) => {
          setResult(`수집 실패: ${err.message}`);
        },
      }
    );
  };

  return (
    <div className="flex items-center gap-2 shrink-0">
      <span className="text-xs text-gray-500 whitespace-nowrap">등록일</span>
      <input
        type="date"
        value={fromDate}
        onChange={(e) => setFromDate(e.target.value)}
        className="px-2 py-1.5 border border-gray-200 rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <span className="text-xs text-gray-400">이후</span>
      <button
        onClick={handleCollect}
        disabled={mutation.isPending}
        className="px-4 py-1.5 bg-gray-900 hover:bg-gray-800 disabled:bg-gray-400 text-white rounded-lg text-xs font-medium transition-colors whitespace-nowrap"
      >
        {mutation.isPending ? (
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
            수집 중...
          </span>
        ) : (
          "수집"
        )}
      </button>
      {result && (
        <span
          className={`text-xs font-medium ${
            result.includes("실패") ? "text-red-500" : "text-green-600"
          }`}
        >
          {result}
        </span>
      )}
    </div>
  );
}

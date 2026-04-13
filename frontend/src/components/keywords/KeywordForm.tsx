"use client";

import { useState } from "react";
import { useCreateKeyword } from "@/lib/queries/useKeywords";

export default function KeywordForm() {
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const createMutation = useCreateKeyword();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const raw = input.trim();
    if (!raw) return;

    // 쉼표, 공백, 줄바꿈으로 분리하여 각각 키워드로 등록
    const keywords = raw
      .split(/[,\s\n]+/)
      .map((k) => k.trim())
      .filter((k) => k.length > 0);

    if (!keywords.length) return;

    for (const kw of keywords) {
      try {
        await createMutation.mutateAsync({ keyword: kw });
      } catch (err: unknown) {
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail || "";
        // 중복은 무시하고 계속 진행
        if (!detail.includes("이미 등록")) {
          setError(`"${kw}" 추가 실패: ${detail || "오류 발생"}`);
        }
      }
    }
    setInput("");
  };

  return (
    <div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="키워드 입력 (쉼표 또는 공백으로 여러 개 등록 가능)"
          className="flex-1 px-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <button
          type="submit"
          disabled={createMutation.isPending || !input.trim()}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-sm font-medium transition-colors whitespace-nowrap"
        >
          {createMutation.isPending ? "추가 중..." : "추가"}
        </button>
      </form>
      {error && (
        <p className="mt-2 text-sm text-red-500">{error}</p>
      )}
    </div>
  );
}

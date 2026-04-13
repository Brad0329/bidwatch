"use client";

import KeywordForm from "@/components/keywords/KeywordForm";
import KeywordList from "@/components/keywords/KeywordList";
import SourceList from "@/components/sources/SourceList";

export default function SettingsPage() {
  return (
    <div>
      <header className="bg-white border-b border-gray-200 px-8 py-4">
        <h1 className="text-xl font-bold text-gray-900">사용자설정</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          구독 출처와 키워드를 관리합니다
        </p>
      </header>

      <div className="p-8 space-y-8">
        {/* 구독 출처 */}
        <section className="bg-white rounded-xl border border-gray-100 shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <i className="ri-global-line text-green-500"></i>
              구독 출처
            </h2>
            <p className="text-xs text-gray-400 mt-1">
              구독한 출처의 공고만 공고 목록에 표시됩니다
            </p>
          </div>
          <div className="p-6">
            <SourceList />
          </div>
        </section>

        {/* 키워드 관리 */}
        <section className="bg-white rounded-xl border border-gray-100 shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <i className="ri-key-2-line text-blue-500"></i>
              키워드 관리
            </h2>
            <p className="text-xs text-gray-400 mt-1">
              등록한 키워드와 매칭되는 공고를 자동으로 필터링합니다
            </p>
          </div>
          <div className="p-6 space-y-4">
            <KeywordForm />
            <KeywordList />
          </div>
        </section>
      </div>
    </div>
  );
}

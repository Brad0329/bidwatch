"use client";

export default function DashboardPage() {
  return (
    <div>
      <header className="bg-white border-b border-gray-200 px-8 py-4">
        <h1 className="text-xl font-bold text-gray-900">대시보드</h1>
        <p className="text-sm text-gray-500 mt-0.5">준비 중입니다</p>
      </header>
      <div className="p-8">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-12 text-center">
          <i className="ri-dashboard-3-line text-5xl text-gray-300 mb-4 block"></i>
          <h2 className="text-lg font-semibold text-gray-600 mb-2">
            대시보드 준비 중
          </h2>
          <p className="text-sm text-gray-400">
            먼저{" "}
            <a href="/settings" className="text-blue-600 hover:underline">
              설정
            </a>
            에서 키워드를 등록하고 공고를 수집해보세요.
          </p>
        </div>
      </div>
    </div>
  );
}

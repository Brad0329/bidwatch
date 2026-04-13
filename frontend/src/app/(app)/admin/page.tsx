"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import SourceList from "@/components/sources/SourceList";

export default function AdminSettingsPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  useEffect(() => {
    if (user && !["owner", "admin"].includes(user.role)) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  if (!user || !["owner", "admin"].includes(user.role)) {
    return null;
  }

  return (
    <div>
      <header className="bg-white border-b border-gray-200 px-8 py-4">
        <h1 className="text-xl font-bold text-gray-900">관리자설정</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          수집 출처를 관리하고 데이터를 수집합니다
        </p>
      </header>

      <div className="p-8 space-y-8">
        {/* 수집 출처 */}
        <section className="bg-white rounded-xl border border-gray-100 shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <i className="ri-database-2-line text-orange-500"></i>
              수집 관리
            </h2>
            <p className="text-xs text-gray-400 mt-1">
              출처별 데이터를 수집합니다. 구독 체크 시 수집 버튼이 표시됩니다.
            </p>
          </div>
          <div className="p-6">
            <SourceList showCollection />
          </div>
        </section>
      </div>
    </div>
  );
}

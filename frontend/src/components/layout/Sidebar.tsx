"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";

const NAV_ITEMS = [
  { href: "/dashboard", icon: "ri-dashboard-3-line", label: "대시보드" },
  { href: "/notices", icon: "ri-file-list-3-line", label: "공고 목록" },
  { href: "/pre-notices", icon: "ri-calendar-todo-line", label: "입찰 예고" },
];

const USER_ITEMS = [
  { href: "/settings", icon: "ri-user-settings-line", label: "사용자설정" },
];

const ADMIN_ITEMS = [
  { href: "/admin", icon: "ri-admin-line", label: "관리자설정" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const isActive = (href: string) => pathname === href;

  const navLink = (item: { href: string; icon: string; label: string }) => (
    <Link
      key={item.href}
      href={item.href}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
        isActive(item.href)
          ? "bg-blue-600/20 text-blue-400"
          : "text-gray-300 hover:bg-white/[0.08]"
      }`}
    >
      <i className={`${item.icon} text-base`}></i>
      {item.label}
    </Link>
  );

  return (
    <aside className="w-60 bg-[#111827] text-gray-300 flex flex-col fixed h-full z-10">
      {/* Logo */}
      <div className="px-5 py-5 flex items-center gap-2.5 border-b border-gray-800">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
          <i className="ri-radar-line text-white text-lg"></i>
        </div>
        <span className="text-white font-bold text-lg tracking-tight">
          BidWatch
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {NAV_ITEMS.map(navLink)}

        <div className="pt-4 pb-1 px-3 text-xs text-gray-500 uppercase tracking-wider">
          설정
        </div>
        {USER_ITEMS.map(navLink)}
        {user?.role && ["owner", "admin"].includes(user.role) &&
          ADMIN_ITEMS.map(navLink)}
      </nav>

      {/* User */}
      <div className="border-t border-gray-800 px-4 py-3 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-semibold">
          {user?.name?.charAt(0) || "U"}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-white text-sm font-medium truncate">
            {user?.name || "사용자"}
          </div>
          <div className="text-gray-500 text-xs truncate">{user?.email}</div>
        </div>
        <button onClick={handleLogout} title="로그아웃">
          <i className="ri-logout-box-r-line text-gray-500 hover:text-white cursor-pointer"></i>
        </button>
      </div>
    </aside>
  );
}

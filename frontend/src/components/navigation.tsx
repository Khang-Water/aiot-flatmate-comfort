"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="top-nav" aria-label="Điều hướng chính">
      <Link className="brand" href="/">
        <span>FM</span>
        FlatMate Comfort
      </Link>
      <div>
        <Link aria-current={pathname === "/" ? "page" : undefined} href="/">
          Căn hộ 3D
        </Link>
        <Link aria-current={pathname === "/dashboard" ? "page" : undefined} href="/dashboard">
          Bảng điều khiển
        </Link>
        <Link aria-current={pathname === "/history" ? "page" : undefined} href="/history">
          Lịch sử
        </Link>
      </div>
    </nav>
  );
}

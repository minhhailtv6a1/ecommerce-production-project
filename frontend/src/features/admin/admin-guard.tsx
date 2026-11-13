"use client";
import Link from "next/link";
import { useAuth } from "@/features/auth/auth-provider";

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  if (!session) return <section className="admin-gate"><p className="eyebrow">Khu vực quản trị</p><h1>Đăng nhập để tiếp tục</h1><p>Phiên đăng nhập được giữ trong bộ nhớ và sẽ mất khi tải lại trang.</p><Link className="button button-primary" href="/login">Đăng nhập admin</Link></section>;
  if (session.user.role !== "admin") return <section className="admin-gate"><p className="eyebrow">Không đủ quyền</p><h1>Tài khoản customer không thể quản trị catalog</h1><Link className="button button-secondary" href="/">Về cửa hàng</Link></section>;
  return <>{children}</>;
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/features/auth/auth-provider";
import { useCart } from "@/features/commerce/cart-provider";
import { asApiError } from "@/lib/api/api-error";

const navigation = [
  { href: "/", label: "Trang chủ" },
  { href: "/products", label: "Sản phẩm" },
  { href: "/visual-search", label: "Tìm bằng ảnh" },
];

export function Header() {
  const pathname = usePathname();
  const { session, logout, verifySession } = useAuth();
  const { state: cartState } = useCart();
  const [feedback, setFeedback] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function handleVerify() {
    setChecking(true);
    setFeedback(null);
    try {
      const user = await verifySession();
      setFeedback(`Thông tin tài khoản đã được cập nhật: ${user.email}`);
    } catch (error) {
      setFeedback(asApiError(error).message);
    } finally {
      setChecking(false);
    }
  }

  return (
    <header className="site-header">
      <div className="announcement">
        <div className="container announcement-inner">
          <span>Ưu đãi mới được cập nhật mỗi ngày</span>
          <span>Tìm đúng món đồ bạn thích chỉ từ một bức ảnh</span>
        </div>
      </div>
      <div className="container header-main">
        <Link className="brand" href="/" aria-label="Lumi Market - Trang chủ">
          <span className="brand-mark" aria-hidden="true">
            LM
          </span>
          <span>
            <strong>Lumi</strong>
            <small>image market</small>
          </span>
        </Link>

        <nav className="main-nav" aria-label="Điều hướng chính">
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={
                item.href === "/"
                  ? pathname === "/"
                    ? "page"
                    : undefined
                  : pathname.startsWith(item.href)
                    ? "page"
                    : undefined
              }
            >
              {item.label}
            </Link>
          ))}
          {session ? (
            <Link
              href="/orders"
              aria-current={pathname.startsWith("/orders") ? "page" : undefined}
            >
              Đơn hàng
            </Link>
          ) : null}
        </nav>

        <div className="auth-nav">
          <Link
            className="cart-link"
            href="/cart"
            aria-current={pathname === "/cart" || pathname === "/checkout" ? "page" : undefined}
            aria-label={
              cartState.status === "ready"
                ? `Giỏ hàng, ${cartState.cart.item_count} sản phẩm`
                : "Giỏ hàng"
            }
          >
            <svg
              className="cart-icon"
              aria-hidden="true"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M3 4h2l2.15 10.05a2 2 0 0 0 1.96 1.58h7.96a2 2 0 0 0 1.95-1.55L21 7H6.05M9.5 20a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm9 0a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {cartState.status === "ready" ? (
              <strong aria-live="polite" aria-atomic="true">
                {cartState.cart.item_count}
              </strong>
            ) : null}
          </Link>
          {session ? (
            <div className="session-menu">
              <span className="session-email" title={session.user.email}>
                {session.user.email}
              </span>
              <button
                className="button button-ghost button-small"
                type="button"
                onClick={handleVerify}
                disabled={checking}
              >
                {checking ? "Đang cập nhật…" : "Làm mới"}
              </button>
              <button
                className="button button-secondary button-small"
                type="button"
                onClick={() => {
                  logout();
                  setFeedback("Bạn đã đăng xuất.");
                }}
              >
                Đăng xuất
              </button>
            </div>
          ) : (
            <>
              <Link className="text-link" href="/login">
                Đăng nhập
              </Link>
              <Link className="button button-dark button-small" href="/register">
                Đăng ký
              </Link>
            </>
          )}
        </div>
      </div>
      {feedback ? (
        <div className="session-feedback" role="status">
          <div className="container">{feedback}</div>
        </div>
      ) : null}
    </header>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { useAuth } from "@/features/auth/auth-provider";
import { asApiError, type ApiError } from "@/lib/api/api-error";
import { getOrders } from "@/lib/api/commerce.api";
import { formatPrice } from "@/lib/format";
import type { Order } from "@/types/commerce";
import { formatOrderDate } from "./commerce-utils";
import { OrderStatusBadge } from "./order-status-badge";

type OrdersState =
  | { status: "loading" }
  | { status: "ready"; orders: Order[]; userId: string }
  | { status: "error"; error: ApiError; userId: string };

export function OrdersView() {
  const { session } = useAuth();
  const [state, setState] = useState<OrdersState>({ status: "loading" });

  const load = useCallback(
    (signal?: AbortSignal) => {
      if (!session) return;
      getOrders(session.token, signal)
        .then((response) =>
          setState({
            status: "ready",
            orders: response.items,
            userId: session.user.id,
          }),
        )
        .catch((error: unknown) => {
          if (!signal?.aborted)
            setState({
              status: "error",
              error: asApiError(error),
              userId: session.user.id,
            });
        });
    },
    [session],
  );

  useEffect(() => {
    if (!session) return;
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, session]);

  if (!session) {
    return (
      <div className="container page-section commerce-gate">
        <p className="eyebrow">Đơn hàng</p>
        <h1>Đăng nhập để xem lịch sử</h1>
        <p>Chỉ tài khoản đã tạo đơn mới có thể xem thông tin giao nhận và trạng thái.</p>
        <Link className="button button-primary" href="/login">Đăng nhập</Link>
      </div>
    );
  }

  if (state.status === "loading" || state.userId !== session.user.id) {
    return <div className="container page-section commerce-loading" aria-busy="true"><div className="loader" /><p>Đang tải đơn hàng…</p></div>;
  }

  if (state.status === "error") {
    return <div className="container page-section narrow-state"><ApiErrorPanel error={state.error} onRetry={() => { setState({ status: "loading" }); load(); }} title="Không thể tải đơn hàng" /></div>;
  }

  return (
    <div className="container page-section">
      <div className="commerce-heading split-heading">
        <div><p className="eyebrow">Tài khoản của bạn</p><h1>Lịch sử đơn hàng</h1><p>Theo dõi các đơn COD đã được tạo từ giỏ hàng.</p></div>
        <Link className="button button-secondary" href="/products">Tiếp tục mua sắm</Link>
      </div>
      {state.orders.length === 0 ? (
        <div className="commerce-gate order-empty">
          <span className="commerce-gate-icon" aria-hidden="true">0</span>
          <h2>Chưa có đơn hàng</h2>
          <p>Đơn hàng đã đặt sẽ xuất hiện tại đây.</p>
          <Link className="button button-primary" href="/products">Khám phá sản phẩm</Link>
        </div>
      ) : (
        <div className="order-list">
          {state.orders.map((order) => (
            <article className="order-card" key={order.id}>
              <div className="order-card-head">
                <div><span>Mã đơn</span><strong>{order.id}</strong></div>
                <OrderStatusBadge status={order.status} />
              </div>
              <div className="order-card-body">
                <div><span>Ngày đặt</span><strong>{formatOrderDate(order.created_at)}</strong></div>
                <div><span>Sản phẩm</span><strong>{order.items.reduce((total, item) => total + item.quantity, 0)}</strong></div>
                <div><span>Thanh toán</span><strong>COD</strong></div>
                <div><span>Tổng tiền</span><strong>{formatPrice(order.total_amount, order.currency)}</strong></div>
              </div>
              <div className="order-card-foot">
                <span>{order.items.map((item) => item.product_name).join(", ")}</span>
                <Link className="arrow-link" href={`/orders/${encodeURIComponent(order.id)}`}>Xem chi tiết →</Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

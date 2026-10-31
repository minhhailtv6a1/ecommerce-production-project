"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { useAuth } from "@/features/auth/auth-provider";
import { asApiError, type ApiError } from "@/lib/api/api-error";
import { getOrder } from "@/lib/api/commerce.api";
import { formatPrice } from "@/lib/format";
import type { Order, OrderItem } from "@/types/commerce";
import { formatOrderDate, variantDescription } from "./commerce-utils";
import { OrderStatusBadge } from "./order-status-badge";
import { ProductThumbnail } from "./product-thumbnail";
import { useProductImages } from "./use-product-images";

const NO_ORDER_ITEMS: OrderItem[] = [];

type OrderState =
  | { status: "loading" }
  | { status: "ready"; order: Order; userId: string }
  | { status: "error"; error: ApiError; userId: string };

export function OrderDetailView({ orderId, justCreated }: { orderId: string; justCreated: boolean }) {
  const { session } = useAuth();
  const [state, setState] = useState<OrderState>({ status: "loading" });
  const imageItems =
    session && state.status === "ready" && state.userId === session.user.id
      ? state.order.items
      : NO_ORDER_ITEMS;
  const { images: productImages, loading: imagesLoading } =
    useProductImages(imageItems);

  const load = useCallback(
    (signal?: AbortSignal) => {
      if (!session) return;
      getOrder(session.token, orderId, signal)
        .then((order) =>
          setState({ status: "ready", order, userId: session.user.id }),
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
    [orderId, session],
  );

  useEffect(() => {
    if (!session) return;
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, session]);

  if (!session) {
    return <div className="container page-section commerce-gate"><p className="eyebrow">Chi tiết đơn hàng</p><h1>Bạn cần đăng nhập</h1><p>Đăng nhập bằng tài khoản đã tạo đơn để xem thông tin.</p><Link className="button button-primary" href="/login">Đăng nhập</Link></div>;
  }

  if (state.status === "loading" || state.userId !== session.user.id) {
    return <div className="container page-section commerce-loading" aria-busy="true"><div className="loader" /><p>Đang xác nhận đơn hàng với hệ thống…</p></div>;
  }

  if (state.status === "error") {
    return <div className="container page-section narrow-state"><ApiErrorPanel error={state.error} onRetry={() => { setState({ status: "loading" }); load(); }} title="Không thể mở đơn hàng" /><Link className="arrow-link" href="/orders">← Lịch sử đơn hàng</Link></div>;
  }

  const { order } = state;
  return (
    <div className="container page-section">
      {justCreated ? (
        <div className="order-created" role="status"><span aria-hidden="true">✓</span><div><strong>Đơn hàng đã được tạo</strong><p>Backend đã xác nhận đơn COD và cập nhật tồn kho thành công.</p></div></div>
      ) : null}
      <div className="order-detail-heading">
        <div><Link className="back-link" href="/orders">← Lịch sử đơn hàng</Link><p className="eyebrow">Chi tiết đơn hàng</p><h1>Đơn {order.id}</h1><p>Đặt lúc {formatOrderDate(order.created_at)}</p></div>
        <OrderStatusBadge status={order.status} />
      </div>

      <div className="order-detail-layout">
        <section className="order-products">
          <div className="section-title-row"><h2>Sản phẩm</h2><span>{order.items.reduce((total, item) => total + item.quantity, 0)} sản phẩm</span></div>
          {order.items.map((item) => (
            <div className="order-product-line" key={item.id}>
              <ProductThumbnail
                image={productImages[item.product_id]}
                loading={imagesLoading}
                productName={item.product_name}
                href={`/products/${encodeURIComponent(item.product_id)}`}
              />
              <div><strong>{item.product_name}</strong><span>{variantDescription(item.color, item.size, item.sku)}</span><span>{formatPrice(item.unit_price, order.currency)} × {item.quantity}</span></div>
              <strong>{formatPrice(item.line_total, order.currency)}</strong>
            </div>
          ))}
          <div className="order-total"><span>Tổng thanh toán</span><strong>{formatPrice(order.total_amount, order.currency)}</strong></div>
        </section>

        <aside className="delivery-card">
          <p className="eyebrow">Thông tin nhận hàng</p>
          <dl>
            <div><dt>Người nhận</dt><dd>{order.receiver_name}</dd></div>
            <div><dt>Số điện thoại</dt><dd>{order.phone}</dd></div>
            <div><dt>Địa chỉ</dt><dd>{order.shipping_address}</dd></div>
            <div><dt>Thanh toán</dt><dd>Thanh toán khi nhận hàng (COD)</dd></div>
            {order.note ? <div><dt>Ghi chú</dt><dd>{order.note}</dd></div> : null}
          </dl>
        </aside>
      </div>
    </div>
  );
}

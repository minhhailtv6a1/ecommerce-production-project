"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { useAuth } from "@/features/auth/auth-provider";
import { useCart } from "@/features/commerce/cart-provider";
import { canCheckout, variantDescription } from "./commerce-utils";
import { asApiError } from "@/lib/api/api-error";
import { formatPrice } from "@/lib/format";
import type { CartItem } from "@/types/commerce";
import { ProductThumbnail } from "./product-thumbnail";
import { useProductImages } from "./use-product-images";

const NO_CART_ITEMS: CartItem[] = [];

export function CartView() {
  const { session } = useAuth();
  const { state, pendingVariantIds, refresh, updateItem, removeItem } = useCart();
  const [announcement, setAnnouncement] = useState<string | null>(null);
  const imageItems = state.status === "ready" ? state.cart.items : NO_CART_ITEMS;
  const { images: productImages, loading: imagesLoading } =
    useProductImages(imageItems);

  async function changeQuantity(item: CartItem, quantity: number) {
    if (quantity < 1 || quantity > Math.min(99, item.inventory_quantity)) return;
    setAnnouncement(null);
    try {
      await updateItem(item.variant_id, quantity);
      setAnnouncement(`Đã cập nhật ${item.product_name} thành ${quantity} sản phẩm.`);
    } catch (error) {
      setAnnouncement(asApiError(error).message);
    }
  }

  async function remove(item: CartItem) {
    setAnnouncement(null);
    try {
      await removeItem(item.variant_id);
      setAnnouncement(`Đã xóa ${item.product_name} khỏi giỏ hàng.`);
    } catch (error) {
      setAnnouncement(asApiError(error).message);
    }
  }

  if (!session || state.status === "signed-out") {
    return (
      <div className="container page-section commerce-gate">
        <span className="commerce-gate-icon" aria-hidden="true">Giỏ</span>
        <p className="eyebrow">Giỏ hàng cá nhân</p>
        <h1>Đăng nhập để xem giỏ hàng</h1>
        <p>Giỏ hàng được lưu an toàn theo tài khoản của bạn trên hệ thống.</p>
        <div className="commerce-gate-actions">
          <Link className="button button-primary" href="/login">Đăng nhập</Link>
          <Link className="button button-secondary" href="/products">Tiếp tục mua sắm</Link>
        </div>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div className="container page-section" aria-busy="true">
        <div className="commerce-heading"><p className="eyebrow">Giỏ hàng</p><h1>Đang kiểm tra sản phẩm…</h1></div>
        <div className="cart-layout">
          <div className="cart-list"><div className="skeleton cart-line-skeleton" /><div className="skeleton cart-line-skeleton" /></div>
          <div className="skeleton cart-summary-skeleton" />
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="container page-section narrow-state">
        <ApiErrorPanel error={state.error} onRetry={() => void refresh()} title="Không thể tải giỏ hàng" />
      </div>
    );
  }

  const { cart } = state;
  if (cart.items.length === 0) {
    return (
      <div className="container page-section commerce-gate">
        <span className="commerce-gate-icon" aria-hidden="true">0</span>
        <p className="eyebrow">Giỏ hàng</p>
        <h1>Giỏ hàng đang trống</h1>
        <p>Khám phá catalog hoặc tìm sản phẩm tương tự từ một bức ảnh.</p>
        <div className="commerce-gate-actions">
          <Link className="button button-primary" href="/products">Xem sản phẩm</Link>
          <Link className="button button-secondary" href="/visual-search">Tìm bằng ảnh</Link>
        </div>
      </div>
    );
  }

  const readyForCheckout = canCheckout(cart);

  return (
    <div className="container page-section">
      <div className="commerce-heading split-heading">
        <div>
          <p className="eyebrow">Giỏ hàng của bạn</p>
          <h1>{cart.item_count} sản phẩm</h1>
          <p>Giá và tồn kho được đồng bộ từ hệ thống trước khi đặt hàng.</p>
        </div>
        <Link className="arrow-link" href="/products">Tiếp tục mua sắm →</Link>
      </div>

      <p className="sr-only" aria-live="polite">{announcement}</p>
      {announcement ? <div className="cart-announcement" role="status">{announcement}</div> : null}

      <div className="cart-layout">
        <section className="cart-list" aria-label="Sản phẩm trong giỏ">
          {cart.items.map((item) => {
            const pending = pendingVariantIds.has(item.variant_id);
            const maxQuantity = Math.min(99, item.inventory_quantity);
            return (
              <article className={`cart-line${item.available ? "" : " unavailable"}`} key={item.variant_id}>
                <ProductThumbnail
                  image={productImages[item.product_id]}
                  loading={imagesLoading}
                  productName={item.product_name}
                  href={`/products/${encodeURIComponent(item.product_slug)}`}
                />
                <div className="cart-line-copy">
                  <Link href={`/products/${encodeURIComponent(item.product_slug)}`}>
                    <h2>{item.product_name}</h2>
                  </Link>
                  <p>{variantDescription(item.color, item.size, item.sku)}</p>
                  <span>{formatPrice(item.unit_price, item.currency)} / sản phẩm</span>
                  {!item.available ? (
                    <strong className="availability-warning">
                      Phiên bản này không còn đủ hàng. Hiện còn {item.inventory_quantity}.
                    </strong>
                  ) : null}
                </div>
                <div className="quantity-control" aria-label={`Số lượng ${item.product_name}`}>
                  <button
                    type="button"
                    onClick={() => void changeQuantity(item, item.quantity - 1)}
                    disabled={pending || item.quantity <= 1}
                    aria-label={`Giảm số lượng ${item.product_name}`}
                  >−</button>
                  <output aria-live="off">{item.quantity}</output>
                  <button
                    type="button"
                    onClick={() => void changeQuantity(item, item.quantity + 1)}
                    disabled={pending || item.quantity >= maxQuantity}
                    aria-label={`Tăng số lượng ${item.product_name}`}
                  >+</button>
                </div>
                <div className="cart-line-total">
                  <strong>{formatPrice(item.line_total, item.currency)}</strong>
                  <button className="link-button" type="button" onClick={() => void remove(item)} disabled={pending}>
                    {pending ? "Đang cập nhật…" : "Xóa"}
                  </button>
                </div>
              </article>
            );
          })}
        </section>

        <aside className="cart-summary" aria-label="Tóm tắt giỏ hàng">
          <p className="eyebrow">Tóm tắt</p>
          <div className="summary-row"><span>Số lượng</span><strong>{cart.item_count}</strong></div>
          <div className="summary-row summary-total"><span>Tạm tính</span><strong>{cart.currency ? formatPrice(cart.subtotal, cart.currency) : "—"}</strong></div>
          <p className="summary-note">Thanh toán khi nhận hàng (COD). Hệ thống sẽ kiểm tra lại giá và tồn kho khi bạn đặt hàng.</p>
          {readyForCheckout ? (
            <Link className="button button-primary button-block button-large" href="/checkout">Tiến hành đặt hàng</Link>
          ) : (
            <p className="checkout-blocked" role="alert">Vui lòng cập nhật hoặc xóa sản phẩm không còn khả dụng trước khi đặt hàng.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

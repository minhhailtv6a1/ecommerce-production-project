"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useRef, useState } from "react";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { useAuth } from "@/features/auth/auth-provider";
import { useCart } from "@/features/commerce/cart-provider";
import { canCheckout, variantDescription } from "./commerce-utils";
import { asApiError, type ApiError } from "@/lib/api/api-error";
import { checkout } from "@/lib/api/commerce.api";
import { formatPrice } from "@/lib/format";

type CheckoutState =
  | { status: "editing" }
  | { status: "submitting" }
  | { status: "error"; error: ApiError }
  | { status: "uncertain"; error: ApiError };

export function CheckoutView() {
  const router = useRouter();
  const { session } = useAuth();
  const { state: cartState, refresh, clearAfterCheckout } = useCart();
  const [state, setState] = useState<CheckoutState>({ status: "editing" });
  const submitLock = useRef(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || cartState.status !== "ready" || !canCheckout(cartState.cart)) return;
    if (submitLock.current) return;

    const form = new FormData(event.currentTarget);
    submitLock.current = true;
    setState({ status: "submitting" });
    try {
      const order = await checkout(session.token, {
        receiver_name: String(form.get("receiver_name") ?? "").trim(),
        phone: String(form.get("phone") ?? "").trim(),
        shipping_address: String(form.get("shipping_address") ?? "").trim(),
        note: String(form.get("note") ?? "").trim() || null,
      });
      clearAfterCheckout();
      router.replace(`/orders/${encodeURIComponent(order.id)}?created=1`);
    } catch (error) {
      const apiError = asApiError(error);
      if (apiError.status === null) {
        setState({ status: "uncertain", error: apiError });
        return;
      }
      if (apiError.status === 409) await refresh();
      submitLock.current = false;
      setState({ status: "error", error: apiError });
    }
  }

  if (!session || cartState.status === "signed-out") {
    return (
      <div className="container page-section commerce-gate">
        <p className="eyebrow">Đặt hàng</p>
        <h1>Bạn cần đăng nhập</h1>
        <p>Đăng nhập để tiếp tục với giỏ hàng được lưu trên tài khoản.</p>
        <Link className="button button-primary" href="/login">Đăng nhập</Link>
      </div>
    );
  }

  if (cartState.status === "loading") {
    return <div className="container page-section commerce-loading" aria-busy="true"><div className="loader" /><p>Đang kiểm tra lại giỏ hàng…</p></div>;
  }

  if (cartState.status === "error") {
    return <div className="container page-section narrow-state"><ApiErrorPanel error={cartState.error} onRetry={() => void refresh()} title="Không thể chuẩn bị đơn hàng" /></div>;
  }

  const { cart } = cartState;
  if (!canCheckout(cart)) {
    return (
      <div className="container page-section commerce-gate">
        <p className="eyebrow">Đặt hàng</p>
        <h1>Giỏ hàng chưa sẵn sàng</h1>
        <p>Giỏ đang trống hoặc có sản phẩm không còn khả dụng. Hãy kiểm tra lại trước khi tiếp tục.</p>
        <Link className="button button-primary" href="/cart">Quay lại giỏ hàng</Link>
      </div>
    );
  }

  const submitting = state.status === "submitting";

  return (
    <div className="container page-section">
      <div className="commerce-heading">
        <Link className="back-link" href="/cart">← Quay lại giỏ hàng</Link>
        <p className="eyebrow">Thanh toán khi nhận hàng</p>
        <h1>Thông tin đặt hàng</h1>
        <p>Thông tin liên hệ được gửi trực tiếp tới backend để tạo đơn COD.</p>
      </div>

      {state.status === "uncertain" ? (
        <section className="uncertain-panel" role="alert">
          <h2>Chưa xác định được kết quả đặt hàng</h2>
          <p>Kết nối bị gián đoạn sau khi gửi yêu cầu. Để tránh tạo đơn trùng, hãy kiểm tra lịch sử đơn hàng trước khi thử lại.</p>
          {state.error.requestId ? <p className="request-id">Mã hỗ trợ: {state.error.requestId}</p> : null}
          <div className="commerce-gate-actions">
            <Link className="button button-primary" href="/orders">Kiểm tra đơn hàng</Link>
            <Link className="button button-secondary" href="/cart">Quay lại giỏ</Link>
          </div>
        </section>
      ) : (
        <form className="checkout-layout" onSubmit={submit}>
          <section className="checkout-form-card">
            <div className="checkout-section-heading"><span>1</span><div><h2>Người nhận</h2><p>Nhập thông tin giao hàng chính xác.</p></div></div>
            <div className="checkout-fields">
              <label htmlFor="receiver-name">Họ và tên</label>
              <input id="receiver-name" name="receiver_name" autoComplete="name" minLength={1} maxLength={100} required disabled={submitting} />
              <label htmlFor="receiver-phone">Số điện thoại</label>
              <input id="receiver-phone" name="phone" type="tel" autoComplete="tel" minLength={8} maxLength={20} required disabled={submitting} aria-describedby="phone-help" />
              <small id="phone-help">Từ 8 đến 20 ký tự theo giới hạn của hệ thống.</small>
              <label htmlFor="shipping-address">Địa chỉ giao hàng</label>
              <textarea id="shipping-address" name="shipping_address" autoComplete="street-address" minLength={5} maxLength={500} rows={4} required disabled={submitting} />
              <label htmlFor="order-note">Ghi chú <span>(không bắt buộc)</span></label>
              <textarea id="order-note" name="note" maxLength={500} rows={3} disabled={submitting} />
            </div>

            <div className="checkout-section-heading payment-heading"><span>2</span><div><h2>Thanh toán</h2><p>Phương thức đang được backend hỗ trợ.</p></div></div>
            <div className="payment-option" aria-label="Phương thức thanh toán đã chọn">
              <span aria-hidden="true">COD</span>
              <div><strong>Thanh toán khi nhận hàng</strong><p>Thanh toán trực tiếp khi đơn hàng được giao.</p></div>
              <span className="selected-check" aria-hidden="true">✓</span>
            </div>

            {state.status === "error" ? (
              <div className="inline-error" role="alert">
                <strong>Chưa thể tạo đơn hàng</strong>
                <span>{state.error.message}</span>
                {state.error.requestId ? <span>Mã hỗ trợ: {state.error.requestId}</span> : null}
              </div>
            ) : null}
          </section>

          <aside className="checkout-review">
            <p className="eyebrow">Đơn hàng</p>
            <h2>{cart.item_count} sản phẩm</h2>
            <div className="checkout-items">
              {cart.items.map((item) => (
                <div className="checkout-item" key={item.variant_id}>
                  <div><strong>{item.product_name}</strong><span>{variantDescription(item.color, item.size, item.sku)} · SL {item.quantity}</span></div>
                  <strong>{formatPrice(item.line_total, item.currency)}</strong>
                </div>
              ))}
            </div>
            <div className="summary-row summary-total"><span>Tổng tiền hàng</span><strong>{formatPrice(cart.subtotal, cart.currency!)}</strong></div>
            <p className="summary-note">Backend sẽ kiểm tra lại giá và tồn kho trong transaction trước khi xác nhận đơn.</p>
            <button className="button button-primary button-block button-large" type="submit" disabled={submitting}>
              {submitting ? "Đang tạo đơn…" : "Đặt hàng COD"}
            </button>
            <p className="checkout-consent">Khi đặt hàng, bạn xác nhận thông tin nhận hàng ở trên là chính xác.</p>
          </aside>
        </form>
      )}
    </div>
  );
}

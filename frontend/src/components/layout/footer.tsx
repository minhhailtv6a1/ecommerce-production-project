import Link from "next/link";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <p className="footer-brand">Lumi Market</p>
          <p className="muted">
            Không gian mua sắm trực tuyến giúp bạn tìm và lựa chọn sản phẩm dễ
            dàng hơn từ hình ảnh.
          </p>
        </div>
        <div>
          <p className="footer-title">Mua sắm</p>
          <Link href="/products">Tất cả sản phẩm</Link>
          <Link href="/visual-search">Tìm sản phẩm bằng ảnh</Link>
          <Link href="/cart">Giỏ hàng</Link>
        </div>
        <div>
          <p className="footer-title">Tài khoản</p>
          <Link href="/orders">Đơn hàng của tôi</Link>
          <Link href="/login">Đăng nhập</Link>
          <Link href="/register">Đăng ký</Link>
        </div>
        <div>
          <p className="footer-title">Thanh toán</p>
          <p className="muted">
            Đơn hàng hiện hỗ trợ thanh toán khi nhận hàng (COD). Chưa hỗ trợ
            thanh toán trực tuyến, voucher hoặc phí vận chuyển.
          </p>
        </div>
      </div>
      <div className="container footer-bottom">
        <span>© 2026 Lumi Market.</span>
        <span>Giá và tồn kho được xác nhận lại khi đặt hàng.</span>
      </div>
    </footer>
  );
}

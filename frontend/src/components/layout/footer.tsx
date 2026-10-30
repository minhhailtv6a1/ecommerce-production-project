import Link from "next/link";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <p className="footer-brand">Lumi Market</p>
          <p className="muted">
            Không gian mua sắm trực tuyến dành cho những món đồ hợp gu, dễ tìm
            và dễ lựa chọn hơn từ hình ảnh.
          </p>
        </div>
        <div>
          <p className="footer-title">Mua sắm</p>
          <Link href="/products">Tất cả sản phẩm</Link>
          <Link href="/visual-search">Tìm sản phẩm bằng ảnh</Link>
        </div>
        <div>
          <p className="footer-title">Về Lumi</p>
          <p className="muted">Sản phẩm được trình bày với giá, hình ảnh và lựa chọn hiện có.</p>
          <p className="muted">Thông tin doanh nghiệp đang được hoàn thiện trước ngày mở bán.</p>
        </div>
        <div>
          <p className="footer-title">Chăm sóc khách hàng</p>
          <p className="muted">Chính sách vận chuyển, đổi trả và bảo mật sẽ được công bố trước khi cửa hàng chính thức nhận đơn.</p>
        </div>
      </div>
      <div className="container footer-bottom">
        <span>© 2026 Lumi Market.</span>
        <span>Giai đoạn giới thiệu sản phẩm — chưa nhận thanh toán trực tuyến.</span>
      </div>
    </footer>
  );
}

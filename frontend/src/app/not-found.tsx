import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container page-section narrow-state">
      <div className="state-panel state-empty">
        <span className="state-icon" aria-hidden="true">404</span>
        <div><h1>Không tìm thấy trang</h1><p>Trang bạn đang tìm có thể đã được di chuyển hoặc không còn tồn tại.</p><Link className="button button-primary" href="/">Về trang chủ</Link></div>
      </div>
    </div>
  );
}

export function LoadingGrid({ count = 8 }: { count?: number }) {
  return (
    <div className="product-grid" aria-busy="true" aria-label="Đang tải sản phẩm">
      {Array.from({ length: count }, (_, index) => (
        <div className="product-card skeleton-card" key={index} aria-hidden="true">
          <div className="skeleton skeleton-image" />
          <div className="product-card-body">
            <div className="skeleton skeleton-line short" />
            <div className="skeleton skeleton-line" />
            <div className="skeleton skeleton-line medium" />
          </div>
        </div>
      ))}
    </div>
  );
}

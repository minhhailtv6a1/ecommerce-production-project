import type { ProductCardData } from "@/types/product";
import { ProductCard } from "./product-card";

export function ProductGrid({
  products,
  emptyTitle = "Chưa tìm thấy sản phẩm",
  emptyMessage = "Hãy thử thay đổi bộ lọc hoặc chọn danh mục khác.",
}: {
  products: ProductCardData[];
  emptyTitle?: string;
  emptyMessage?: string;
}) {
  if (products.length === 0) {
    return (
      <div className="state-panel state-empty">
        <span className="state-icon" aria-hidden="true">
          0
        </span>
        <div>
          <h3>{emptyTitle}</h3>
          <p>{emptyMessage}</p>
        </div>
      </div>
    );
  }
  return (
    <div className="product-grid">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}

import Link from "next/link";
import { categoryLabel } from "@/domain/categories";
import { SHOW_TEST_CATEGORIES } from "@/lib/env";
import { formatPrice } from "@/lib/format";
import type { ProductCardData } from "@/types/product";

export function ProductCard({ product }: { product: ProductCardData }) {
  return (
    <article className="product-card">
      <Link
        className="product-image-link"
        href={`/products/${encodeURIComponent(product.slug)}`}
        aria-label={`Xem ${product.name}`}
      >
        {/* Product image hosts vary by environment, so this app uses the supplied URL. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          className="product-image"
          src={product.primary_image.url}
          alt={product.primary_image.alt}
          loading="lazy"
        />
        <span className={product.in_stock ? "stock-badge" : "stock-badge sold-out"}>
          {product.in_stock ? "Còn hàng" : "Hết hàng"}
        </span>
      </Link>
      <div className="product-card-body">
        {SHOW_TEST_CATEGORIES ? (
          <p className="product-category">{categoryLabel(product.category_id)}</p>
        ) : null}
        <h3>
          <Link href={`/products/${encodeURIComponent(product.slug)}`}>
            {product.name}
          </Link>
        </h3>
        {product.brand ? <p className="product-brand">{product.brand}</p> : null}
        <div className="product-price-row">
          <strong>{formatPrice(product.price, product.currency)}</strong>
          {product.compare_at_price !== null ? (
            <del>{formatPrice(product.compare_at_price, product.currency)}</del>
          ) : null}
        </div>
        {(product.available_sizes.length > 0 ||
          product.available_colors.length > 0) && (
          <p className="product-options">
            {product.available_colors.length > 0
              ? `${product.available_colors.slice(0, 2).join(", ")}`
              : ""}
            {product.available_colors.length > 0 && product.available_sizes.length > 0
              ? " · "
              : ""}
            {product.available_sizes.length > 0
              ? `Size ${product.available_sizes.slice(0, 3).join(", ")}`
              : ""}
          </p>
        )}
      </div>
    </article>
  );
}

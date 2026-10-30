"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { categoryLabel } from "@/domain/categories";
import { asApiError, type ApiError } from "@/lib/api/api-error";
import { getProduct } from "@/lib/api/products.api";
import { SHOW_TEST_CATEGORIES } from "@/lib/env";
import { formatPrice } from "@/lib/format";
import type { ProductDetail } from "@/types/product";

type DetailState =
  | { status: "loading" }
  | { status: "ready"; product: ProductDetail }
  | { status: "error"; error: ApiError };

export function ProductDetailView({ identifier }: { identifier: string }) {
  const [state, setState] = useState<DetailState>({ status: "loading" });
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);

  const load = useCallback(
    (signal?: AbortSignal) => {
      getProduct(identifier, signal)
        .then((product) => {
          setSelectedImageId(product.images[0]?.id ?? product.primary_image.id);
          setState({ status: "ready", product });
        })
        .catch((error: unknown) => {
          if (!signal?.aborted)
            setState({ status: "error", error: asApiError(error) });
        });
    },
    [identifier],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (state.status === "loading") {
    return (
      <div className="container page-section" aria-busy="true">
        <div className="detail-layout detail-skeleton">
          <div className="skeleton detail-image-skeleton" />
          <div><div className="skeleton skeleton-line short" /><div className="skeleton skeleton-line" /><div className="skeleton skeleton-line medium" /></div>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="container page-section narrow-state">
        <ApiErrorPanel error={state.error} onRetry={() => { setState({ status: "loading" }); load(); }} title="Không thể mở sản phẩm" />
        <Link className="arrow-link" href="/products">← Quay lại catalog</Link>
      </div>
    );
  }

  const { product } = state;
  const gallery = product.images.length > 0 ? product.images : [product.primary_image];
  const selectedImage = gallery.find((image) => image.id === selectedImageId) ?? gallery[0];

  return (
    <div className="container page-section">
      <Link className="back-link" href="/products">← Quay lại catalog</Link>
      <div className="detail-layout">
        <section className="product-gallery" aria-label="Ảnh sản phẩm">
          <div className="gallery-main">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={selectedImage.url} alt={selectedImage.alt} />
          </div>
          {gallery.length > 1 ? (
            <div className="gallery-thumbnails">
              {gallery.map((image) => (
                <button
                  className={image.id === selectedImage.id ? "gallery-thumb active" : "gallery-thumb"}
                  type="button"
                  key={image.id}
                  onClick={() => setSelectedImageId(image.id)}
                  aria-label={`Xem ảnh: ${image.alt}`}
                  aria-pressed={image.id === selectedImage.id}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={image.url} alt="" />
                </button>
              ))}
            </div>
          ) : null}
        </section>

        <section className="product-information">
          {SHOW_TEST_CATEGORIES ? (
            <p className="product-category">{categoryLabel(product.category_id)} · {product.category_id}</p>
          ) : null}
          <h1>{product.name}</h1>
          {product.brand ? <p className="detail-brand">Thương hiệu: <strong>{product.brand}</strong></p> : null}
          <div className="detail-price">
            <strong>{formatPrice(product.price, product.currency)}</strong>
            {product.compare_at_price !== null ? <del>{formatPrice(product.compare_at_price, product.currency)}</del> : null}
          </div>
          <div className={product.in_stock ? "detail-stock in-stock" : "detail-stock out-stock"}>
            <span aria-hidden="true" />{product.in_stock ? "Sản phẩm đang còn hàng" : "Sản phẩm hiện hết hàng"}
          </div>
          <div className="detail-description">
            <h2>Mô tả sản phẩm</h2>
            <p>{product.description ?? "Thông tin mô tả cho sản phẩm này đang được cập nhật."}</p>
          </div>
          <div className="scope-note">
            <strong>Chọn đúng phiên bản bạn cần</strong>
            <p>Tham khảo bảng màu sắc, kích thước và số lượng còn lại bên dưới trước khi lựa chọn.</p>
          </div>
        </section>
      </div>

      <section className="variant-section">
        <div className="section-heading">
          <p className="eyebrow">Thông tin lựa chọn</p>
          <h2>Màu sắc và kích thước hiện có</h2>
          <p>Mỗi lựa chọn đi kèm giá và số lượng còn lại để bạn dễ so sánh.</p>
        </div>
        {product.variants.length === 0 ? (
          <div className="state-panel state-empty"><div><h3>Thông tin đang cập nhật</h3><p>Sản phẩm chưa có lựa chọn màu sắc hoặc kích thước.</p></div></div>
        ) : (
          <div className="table-scroll">
            <table className="variant-table">
              <thead><tr><th>SKU</th><th>Màu</th><th>Size</th><th>Giá</th><th>Tồn kho</th><th>Trạng thái</th></tr></thead>
              <tbody>
                {product.variants.map((variant) => (
                  <tr key={variant.id}>
                    <td><code>{variant.sku}</code></td>
                    <td>{variant.color ?? "—"}</td>
                    <td>{variant.size ?? "—"}</td>
                    <td>{formatPrice(variant.price, product.currency)}</td>
                    <td>{variant.inventory_quantity}</td>
                    <td>{variant.is_active ? "Đang hoạt động" : "Tạm ẩn"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

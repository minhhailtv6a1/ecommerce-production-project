"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ProductGrid } from "@/components/products/product-grid";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { LoadingGrid } from "@/components/ui/loading-grid";
import { asApiError, type ApiError } from "@/lib/api/api-error";
import { getCategories } from "@/lib/api/categories.api";
import { SHOW_TEST_CATEGORIES } from "@/lib/env";
import { getProducts } from "@/lib/api/products.api";
import type { Category } from "@/types/category";
import type { ProductCardData } from "@/types/product";

type ResourceState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: ApiError };

export function HomeOverview() {
  const [categories, setCategories] = useState<ResourceState<Category[]>>({
    status: "loading",
  });
  const [products, setProducts] = useState<ResourceState<ProductCardData[]>>({
    status: "loading",
  });

  const loadCategories = useCallback((signal?: AbortSignal) => {
    getCategories(signal)
      .then((response) => setCategories({ status: "ready", data: response.items }))
      .catch((error: unknown) => {
        if (!signal?.aborted)
          setCategories({ status: "error", error: asApiError(error) });
      });
  }, []);

  const loadProducts = useCallback((signal?: AbortSignal) => {
    getProducts({ page: 1, limit: 4, sort: "newest" }, signal)
      .then((response) => setProducts({ status: "ready", data: response.items }))
      .catch((error: unknown) => {
        if (!signal?.aborted)
          setProducts({ status: "error", error: asApiError(error) });
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    if (SHOW_TEST_CATEGORIES) loadCategories(controller.signal);
    loadProducts(controller.signal);
    return () => controller.abort();
  }, [loadCategories, loadProducts]);

  return (
    <>
      <section className="hero-section">
        <div className="container hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Tìm đúng món đồ · Chỉ từ một bức ảnh</p>
            <h1>
              Thấy món bạn thích. <em>Tìm ngay bằng ảnh.</em>
            </h1>
            <p className="hero-lead">
              Tải một bức ảnh tham khảo và khám phá những sản phẩm có kiểu dáng,
              màu sắc hoặc phong cách gần với điều bạn đang tìm kiếm.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary button-large" href="/visual-search">
                Tải ảnh để tìm kiếm
                <span aria-hidden="true">→</span>
              </Link>
              <Link className="button button-secondary button-large" href="/products">
                Xem tất cả sản phẩm
              </Link>
            </div>
            <div className="hero-notes" aria-label="Điểm nổi bật">
              <span>Tìm nhanh theo hình ảnh</span>
              <span>Nhiều lựa chọn sản phẩm</span>
              <span>Giá và tình trạng rõ ràng</span>
            </div>
          </div>

          <div className="hero-visual" aria-hidden="true">
            <div className="visual-frame visual-main">
              <span className="visual-symbol">⌁</span>
              <p>Ảnh bạn thích</p>
            </div>
            <div className="visual-frame visual-result one">
              <span>01</span>
              <p>Gợi ý phù hợp</p>
            </div>
            <div className="visual-frame visual-result two">
              <span>02</span>
              <p>Thêm lựa chọn</p>
            </div>
            <div className="scan-line" />
          </div>
        </div>
      </section>

      <section className="promo-section">
        <div className="container promo-banner">
          <div className="promo-copy">
            <p className="eyebrow">Lumi seasonal edit</p>
            <h2>Giá tốt cho những lựa chọn hợp gu.</h2>
            <p>
              Khám phá các sản phẩm đang có giá so sánh và ưu đãi được cập nhật
              trực tiếp trên từng sản phẩm.
            </p>
            <Link className="button button-light button-large" href="/products?sort=price_asc">
              Khám phá ưu đãi <span aria-hidden="true">→</span>
            </Link>
          </div>
          <div className="promo-art" aria-hidden="true">
            <span className="promo-kicker">SALE</span>
            <strong>THE<br />LUMI<br />EDIT</strong>
            <small>Selected styles · limited highlights</small>
          </div>
        </div>
      </section>

      <section className="content-section">
        <div className="container">
          <div className="section-heading split-heading">
            <div>
              <p className="eyebrow">Gợi ý hôm nay</p>
              <h2>Sản phẩm mới cập nhật</h2>
            </div>
            <Link className="arrow-link" href="/products">
              Xem tất cả <span aria-hidden="true">→</span>
            </Link>
          </div>
          {products.status === "loading" ? (
            <LoadingGrid count={4} />
          ) : products.status === "error" ? (
            <ApiErrorPanel
              error={products.error}
              onRetry={() => {
                setProducts({ status: "loading" });
                loadProducts();
              }}
              title="Chưa thể tải sản phẩm"
            />
          ) : (
            <ProductGrid products={products.data} />
          )}
        </div>
      </section>

      {SHOW_TEST_CATEGORIES ? (
        <section className="content-section test-category-section border-section">
          <div className="container">
            <div className="section-heading split-heading">
              <div>
                <p className="eyebrow">Khám phá theo nhu cầu</p>
                <h2>Sản phẩm theo danh mục</h2>
                <p>Chọn nhanh nhóm sản phẩm bạn quan tâm để bắt đầu khám phá.</p>
              </div>
            </div>
            {categories.status === "loading" ? (
              <div className="category-strip" aria-busy="true">
                {Array.from({ length: 8 }, (_, index) => (
                  <div className="category-tile skeleton" key={index} />
                ))}
              </div>
            ) : categories.status === "error" ? (
              <ApiErrorPanel
                error={categories.error}
                onRetry={() => {
                  setCategories({ status: "loading" });
                  loadCategories();
                }}
                title="Chưa thể tải danh mục"
              />
            ) : categories.data.length === 0 ? (
              <div className="state-panel state-empty">
                <div><h3>Chưa có danh mục</h3><p>Danh mục sản phẩm đang được cập nhật.</p></div>
              </div>
            ) : (
              <div className="category-strip">
                {categories.data.slice(0, 8).map((category) => (
                  <Link
                    className="category-tile"
                    href={`/products?category_ids=${category.id}`}
                    key={category.id}
                  >
                    <span className="category-number">{category.id}</span>
                    <strong>{category.name}</strong>
                    <small>{category.product_count} sản phẩm</small>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </section>
      ) : null}

      <section className="assurance-section">
        <div className="container">
          <div className="section-heading centered-heading">
            <p className="eyebrow">Mua sắm dễ dàng hơn</p>
            <h2>Thông tin vừa đủ để bạn lựa chọn.</h2>
          </div>
          <div className="assurance-grid">
            <article><span>01</span><h3>Giá rõ ràng</h3><p>Giá hiện tại và giá so sánh được trình bày ngay trên từng sản phẩm.</p></article>
            <article><span>02</span><h3>Hình ảnh trực quan</h3><p>Xem ảnh chính và bộ sưu tập ảnh trước khi đi sâu vào thông tin chi tiết.</p></article>
            <article><span>03</span><h3>Lựa chọn cụ thể</h3><p>Màu sắc, kích thước và số lượng còn lại được hiển thị theo từng phiên bản.</p></article>
          </div>
        </div>
      </section>

      <section className="how-section">
        <div className="container">
          <div className="section-heading centered-heading">
            <p className="eyebrow">Ba bước đơn giản</p>
            <h2>Từ cảm hứng đến món đồ phù hợp</h2>
          </div>
          <ol className="steps-grid">
            <li><span>01</span><h3>Chọn ảnh</h3><p>Dùng ảnh rõ sản phẩm để nhận được gợi ý phù hợp hơn.</p></li>
            <li><span>02</span><h3>Tinh chỉnh</h3><p>Trong giai đoạn thử nghiệm, bạn có thể chọn thêm danh mục muốn tìm.</p></li>
            <li><span>03</span><h3>Khám phá</h3><p>So sánh hình ảnh, giá và các lựa chọn hiện có của từng sản phẩm.</p></li>
          </ol>
        </div>
      </section>

      <section className="company-section">
        <div className="container company-grid">
          <div>
            <p className="eyebrow">Về Lumi Market</p>
            <h2>Khơi nguồn cảm hứng mua sắm từ hình ảnh.</h2>
          </div>
          <div className="company-copy">
            <p>Lumi Market được xây dựng với mong muốn giúp khách hàng đi từ “mình thích món này” đến những lựa chọn có thể khám phá chỉ trong vài bước.</p>
            <p>Chúng tôi ưu tiên hình ảnh dễ xem, thông tin sản phẩm rõ ràng và trải nghiệm tìm kiếm tự nhiên. Các chính sách vận chuyển, đổi trả và bảo mật đang được hoàn thiện trước khi cửa hàng chính thức nhận đơn.</p>
            <Link className="arrow-link" href="/products">Khám phá bộ sưu tập <span aria-hidden="true">→</span></Link>
          </div>
        </div>
      </section>
    </>
  );
}

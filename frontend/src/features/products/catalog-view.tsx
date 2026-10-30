"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { CategoryMultiSelect } from "@/components/categories/category-multi-select";
import { ProductGrid } from "@/components/products/product-grid";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { LoadingGrid } from "@/components/ui/loading-grid";
import { isCategoryId } from "@/domain/categories";
import { asApiError, type ApiError } from "@/lib/api/api-error";
import { getCategories } from "@/lib/api/categories.api";
import { SHOW_TEST_CATEGORIES } from "@/lib/env";
import { getProducts } from "@/lib/api/products.api";
import type { Category } from "@/types/category";
import type { ProductListResponse, ProductSort } from "@/types/product";

interface FilterDraft {
  categoryIds: string[];
  size: string;
  color: string;
  brand: string;
  minPrice: string;
  maxPrice: string;
  inStock: "" | "true" | "false";
  sort: ProductSort;
}

type ProductState =
  | { status: "loading" }
  | { status: "ready"; data: ProductListResponse }
  | { status: "error"; error: ApiError };

function draftFromParams(params: URLSearchParams): FilterDraft {
  const sort = params.get("sort");
  return {
    categoryIds: params.getAll("category_ids").filter(isCategoryId),
    size: params.get("size") ?? "",
    color: params.get("color") ?? "",
    brand: params.get("brand") ?? "",
    minPrice: params.get("min_price") ?? "",
    maxPrice: params.get("max_price") ?? "",
    inStock:
      params.get("in_stock") === "true"
        ? "true"
        : params.get("in_stock") === "false"
          ? "false"
          : "",
    sort:
      sort === "price_asc" || sort === "price_desc" || sort === "newest"
        ? sort
        : "newest",
  };
}

function optionalInteger(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined;
}

export function CatalogView() {
  const searchParams = useSearchParams();
  const queryKey = searchParams.toString();

  return <CatalogViewContent key={queryKey} queryKey={queryKey} />;
}

function CatalogViewContent({ queryKey }: { queryKey: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useMemo(() => new URLSearchParams(queryKey), [queryKey]);
  const [draft, setDraft] = useState<FilterDraft>(() => draftFromParams(params));
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryError, setCategoryError] = useState<ApiError | null>(null);
  const [state, setState] = useState<ProductState>({ status: "loading" });

  useEffect(() => {
    if (!SHOW_TEST_CATEGORIES) return;
    const controller = new AbortController();
    getCategories(controller.signal)
      .then((response) => setCategories(response.items))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setCategoryError(asApiError(error));
      });
    return () => controller.abort();
  }, []);

  const loadProducts = useCallback(
    (signal?: AbortSignal) => {
      const current = draftFromParams(params);
      getProducts(
        {
          categoryIds: current.categoryIds,
          size: current.size || undefined,
          color: current.color || undefined,
          brand: current.brand || undefined,
          minPrice: optionalInteger(current.minPrice),
          maxPrice: optionalInteger(current.maxPrice),
          inStock:
            current.inStock === "" ? undefined : current.inStock === "true",
          sort: current.sort,
          page: Math.max(1, Number(params.get("page")) || 1),
          limit: 20,
        },
        signal,
      )
        .then((data) => setState({ status: "ready", data }))
        .catch((error: unknown) => {
          if (!signal?.aborted)
            setState({ status: "error", error: asApiError(error) });
        });
    },
    [params],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadProducts(controller.signal);
    return () => controller.abort();
  }, [loadProducts]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = new URLSearchParams();
    draft.categoryIds.forEach((id) => next.append("category_ids", id));
    if (draft.size.trim()) next.set("size", draft.size.trim());
    if (draft.color.trim()) next.set("color", draft.color.trim());
    if (draft.brand.trim()) next.set("brand", draft.brand.trim());
    if (draft.minPrice.trim()) next.set("min_price", draft.minPrice.trim());
    if (draft.maxPrice.trim()) next.set("max_price", draft.maxPrice.trim());
    if (draft.inStock) next.set("in_stock", draft.inStock);
    next.set("sort", draft.sort);
    next.set("page", "1");
    router.push(`${pathname}?${next.toString()}`);
  }

  function goToPage(page: number) {
    const next = new URLSearchParams(queryKey);
    next.set("page", String(page));
    router.push(`${pathname}?${next.toString()}`);
  }

  return (
    <div className="container page-section">
      <div className="page-heading catalog-heading">
        <div>
          <p className="eyebrow">Bộ sưu tập Lumi</p>
          <h1>Tìm món đồ dành cho bạn</h1>
          <p>Lọc theo phong cách, mức giá và lựa chọn phù hợp để khám phá nhanh hơn.</p>
        </div>
        {state.status === "ready" ? (
          <div className="result-count"><strong>{state.data.total}</strong><span>sản phẩm</span></div>
        ) : null}
      </div>

      <div className="catalog-layout">
        <aside className="filter-panel" aria-label="Bộ lọc sản phẩm">
          <form onSubmit={applyFilters}>
            <div className="filter-header">
              <h2>Bộ lọc</h2>
              <button className="link-button" type="button" onClick={() => router.push(pathname)}>
                Xóa tất cả
              </button>
            </div>

            {SHOW_TEST_CATEGORIES ? (
              <fieldset className="filter-group">
                <legend>Danh mục</legend>
                {categoryError ? (
                  <p className="field-error">{categoryError.message}</p>
                ) : categories.length === 0 ? (
                  <p className="muted">Đang tải danh mục…</p>
                ) : (
                  <CategoryMultiSelect
                    categories={categories}
                    selected={draft.categoryIds}
                    onChange={(categoryIds) => setDraft((value) => ({ ...value, categoryIds }))}
                    compact
                  />
                )}
              </fieldset>
            ) : null}

            <div className="filter-group field-stack">
              <label htmlFor="filter-brand">Thương hiệu</label>
              <input id="filter-brand" value={draft.brand} onChange={(event) => setDraft((value) => ({ ...value, brand: event.target.value }))} placeholder="Ví dụ: Demo Brand A" />
              <label htmlFor="filter-size">Kích thước</label>
              <input id="filter-size" value={draft.size} onChange={(event) => setDraft((value) => ({ ...value, size: event.target.value }))} placeholder="S, M, L…" />
              <label htmlFor="filter-color">Màu sắc</label>
              <input id="filter-color" value={draft.color} onChange={(event) => setDraft((value) => ({ ...value, color: event.target.value }))} placeholder="Đen, Trắng…" />
            </div>

            <fieldset className="filter-group price-fields">
              <legend>Khoảng giá (VND)</legend>
              <label><span>Từ</span><input type="number" min="0" inputMode="numeric" value={draft.minPrice} onChange={(event) => setDraft((value) => ({ ...value, minPrice: event.target.value }))} /></label>
              <label><span>Đến</span><input type="number" min="0" inputMode="numeric" value={draft.maxPrice} onChange={(event) => setDraft((value) => ({ ...value, maxPrice: event.target.value }))} /></label>
            </fieldset>

            <div className="filter-group field-stack">
              <label htmlFor="filter-stock">Tình trạng</label>
              <select id="filter-stock" value={draft.inStock} onChange={(event) => setDraft((value) => ({ ...value, inStock: event.target.value as FilterDraft["inStock"] }))}>
                <option value="">Tất cả</option><option value="true">Còn hàng</option><option value="false">Hết hàng</option>
              </select>
              <label htmlFor="filter-sort">Sắp xếp</label>
              <select id="filter-sort" value={draft.sort} onChange={(event) => setDraft((value) => ({ ...value, sort: event.target.value as ProductSort }))}>
                <option value="newest">Mới nhất</option><option value="price_asc">Giá tăng dần</option><option value="price_desc">Giá giảm dần</option>
              </select>
            </div>

            <button className="button button-primary button-block" type="submit">Áp dụng bộ lọc</button>
          </form>
        </aside>

        <section className="catalog-results" aria-live="polite">
          {state.status === "loading" ? (
            <LoadingGrid />
          ) : state.status === "error" ? (
            <ApiErrorPanel error={state.error} onRetry={() => { setState({ status: "loading" }); loadProducts(); }} />
          ) : (
            <>
              <ProductGrid products={state.data.items} />
              {state.data.pages > 1 ? (
                <nav className="pagination" aria-label="Phân trang catalog">
                  <button className="button button-secondary" type="button" disabled={state.data.page <= 1} onClick={() => goToPage(state.data.page - 1)}>← Trang trước</button>
                  <span>Trang <strong>{state.data.page}</strong> / {state.data.pages}</span>
                  <button className="button button-secondary" type="button" disabled={state.data.page >= state.data.pages} onClick={() => goToPage(state.data.page + 1)}>Trang sau →</button>
                </nav>
              ) : null}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

import type {
  ProductDetail,
  ProductFilters,
  ProductListResponse,
} from "@/types/product";
import { requestJson } from "./http-client";
import { arrayValue, numberValue, record } from "./parse";
import { parseProductCard, parseProductDetail } from "./product-parser";

export function buildProductQuery(filters: ProductFilters): string {
  const query = new URLSearchParams();
  filters.categoryIds?.forEach((id) => query.append("category_ids", id));
  if (filters.size) query.set("size", filters.size);
  if (filters.color) query.set("color", filters.color);
  if (filters.brand) query.set("brand", filters.brand);
  if (filters.minPrice !== undefined)
    query.set("min_price", String(filters.minPrice));
  if (filters.maxPrice !== undefined)
    query.set("max_price", String(filters.maxPrice));
  if (filters.inStock !== undefined)
    query.set("in_stock", String(filters.inStock));
  if (filters.sort) query.set("sort", filters.sort);
  if (filters.page !== undefined) query.set("page", String(filters.page));
  if (filters.limit !== undefined) query.set("limit", String(filters.limit));
  return query.toString();
}

export async function getProducts(
  filters: ProductFilters,
  signal?: AbortSignal,
): Promise<ProductListResponse> {
  const query = buildProductQuery(filters);
  const payload = record(
    await requestJson(`/products${query ? `?${query}` : ""}`, { signal }),
    "danh sách sản phẩm",
  );
  return {
    items: arrayValue(payload.items, "products.items").map(parseProductCard),
    total: numberValue(payload.total, "products.total"),
    page: numberValue(payload.page, "products.page"),
    page_size: numberValue(payload.page_size, "products.page_size"),
    pages: numberValue(payload.pages, "products.pages"),
  };
}

export async function getProduct(
  identifier: string,
  signal?: AbortSignal,
): Promise<ProductDetail> {
  const payload = await requestJson(`/products/${encodeURIComponent(identifier)}`, {
    signal,
  });
  return parseProductDetail(payload);
}

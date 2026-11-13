import { isCategoryId } from "@/domain/categories";
import type { AdminImage, AdminProduct, AdminProductList, AdminVariant, ProductDraftInput, VariantInput } from "@/types/admin-catalog";
import { requestJson } from "./http-client";
import { arrayValue, booleanValue, invalidResponse, nullableString, numberValue, record, stringValue } from "./parse";

const statuses = new Set(["draft", "published", "archived"]);
const indexStatuses = new Set(["pending", "indexing", "indexed", "failed", "removed"]);
const nullableNumber = (value: unknown, field: string) => value === null ? null : numberValue(value, field);

function variant(value: unknown): AdminVariant {
  const item = record(value, "variant");
  return { id: stringValue(item.id, "variant.id"), sku: stringValue(item.sku, "variant.sku"), color: nullableString(item.color, "variant.color"), size: nullableString(item.size, "variant.size"), price: numberValue(item.price, "variant.price"), compare_at_price: nullableNumber(item.compare_at_price, "variant.compare_at_price"), inventory_quantity: numberValue(item.inventory_quantity, "variant.inventory_quantity"), is_active: booleanValue(item.is_active, "variant.is_active"), created_at: stringValue(item.created_at, "variant.created_at"), updated_at: stringValue(item.updated_at, "variant.updated_at") };
}

function image(value: unknown): AdminImage {
  const item = record(value, "image");
  const indexStatus = stringValue(item.index_status, "image.index_status");
  if (!indexStatuses.has(indexStatus)) return invalidResponse("Trạng thái index không hợp lệ.");
  return { id: stringValue(item.id, "image.id"), storage_path: stringValue(item.storage_path, "image.storage_path"), url: nullableString(item.url, "image.url"), alt_text: stringValue(item.alt_text, "image.alt_text"), sort_order: numberValue(item.sort_order, "image.sort_order"), is_primary: booleanValue(item.is_primary, "image.is_primary"), index_status: indexStatus as AdminImage["index_status"], indexed_at: nullableString(item.indexed_at, "image.indexed_at"), index_error: nullableString(item.index_error, "image.index_error"), created_at: stringValue(item.created_at, "image.created_at"), updated_at: stringValue(item.updated_at, "image.updated_at") };
}

export function parseAdminProduct(value: unknown): AdminProduct {
  const item = record(value, "admin product");
  const categoryId = stringValue(item.category_id, "product.category_id");
  const status = stringValue(item.status, "product.status");
  if (!isCategoryId(categoryId) || !statuses.has(status)) return invalidResponse("Sản phẩm admin không hợp lệ.");
  return { id: stringValue(item.id, "product.id"), slug: stringValue(item.slug, "product.slug"), name: stringValue(item.name, "product.name"), description: nullableString(item.description, "product.description"), category_id: categoryId, brand: nullableString(item.brand, "product.brand"), status: status as AdminProduct["status"], currency: stringValue(item.currency, "product.currency"), version: numberValue(item.version, "product.version"), created_by: nullableString(item.created_by, "product.created_by"), updated_by: nullableString(item.updated_by, "product.updated_by"), created_at: stringValue(item.created_at, "product.created_at"), updated_at: stringValue(item.updated_at, "product.updated_at"), variants: arrayValue(item.variants, "product.variants").map(variant), images: arrayValue(item.images, "product.images").map(image) };
}

export async function listAdminProducts(token: string, query = "", signal?: AbortSignal): Promise<AdminProductList> {
  const payload = record(await requestJson(`/admin/products${query}`, { token, signal }), "admin product list");
  return { items: arrayValue(payload.items, "items").map((value) => { const item = record(value, "summary"); const categoryId = stringValue(item.category_id, "category_id"); const status = stringValue(item.status, "status"); if (!isCategoryId(categoryId) || !statuses.has(status)) return invalidResponse("Product summary không hợp lệ."); return { id: stringValue(item.id, "id"), slug: stringValue(item.slug, "slug"), name: stringValue(item.name, "name"), category_id: categoryId, brand: nullableString(item.brand, "brand"), status: status as AdminProduct["status"], currency: stringValue(item.currency, "currency"), version: numberValue(item.version, "version"), price_from: nullableNumber(item.price_from, "price_from"), inventory_total: numberValue(item.inventory_total, "inventory_total"), index_status: item.index_status === null ? null : stringValue(item.index_status, "index_status") as AdminImage["index_status"], primary_image_url: nullableString(item.primary_image_url, "primary_image_url"), primary_image_alt: nullableString(item.primary_image_alt, "primary_image_alt"), updated_at: stringValue(item.updated_at, "updated_at") }; }), total: numberValue(payload.total, "total"), page: numberValue(payload.page, "page"), page_size: numberValue(payload.page_size, "page_size"), pages: numberValue(payload.pages, "pages") };
}
export async function getAdminProduct(token: string, id: string) { return parseAdminProduct(await requestJson(`/admin/products/${id}`, { token })); }
export async function createAdminProduct(token: string, input: ProductDraftInput) { return parseAdminProduct(await requestJson("/admin/products", { method: "POST", token, body: input })); }
export async function updateAdminProduct(token: string, id: string, version: number, input: ProductDraftInput) { return parseAdminProduct(await requestJson(`/admin/products/${id}`, { method: "PATCH", token, body: { expected_version: version, ...input } })); }
export async function lifecycleAdminProduct(token: string, id: string, action: "publish" | "restore" | "archive") { return parseAdminProduct(await requestJson(action === "archive" ? `/admin/products/${id}` : `/admin/products/${id}/${action}`, { method: action === "archive" ? "DELETE" : "POST", token })); }
export async function indexAdminProduct(token: string, id: string) { return parseAdminProduct(await requestJson(`/admin/products/${id}/index`, { method: "POST", token })); }
export async function addAdminVariant(token: string, id: string, input: VariantInput) { return variant(await requestJson(`/admin/products/${id}/variants`, { method: "POST", token, body: input })); }
export async function deactivateAdminVariant(token: string, productId: string, variantId: string) { return variant(await requestJson(`/admin/products/${productId}/variants/${variantId}`, { method: "DELETE", token })); }
export async function uploadAdminImage(token: string, id: string, file: File, altText: string, primary: boolean) { const body = new FormData(); body.append("image", file); body.append("alt_text", altText); body.append("is_primary", String(primary)); return image(await requestJson(`/admin/products/${id}/images`, { method: "POST", token, body })); }
export async function updateAdminImage(token: string, productId: string, imageId: string, body: { is_primary?: boolean; alt_text?: string }) { return image(await requestJson(`/admin/products/${productId}/images/${imageId}`, { method: "PATCH", token, body })); }
export async function deleteAdminImage(token: string, productId: string, imageId: string) { await requestJson(`/admin/products/${productId}/images/${imageId}`, { method: "DELETE", token }); }

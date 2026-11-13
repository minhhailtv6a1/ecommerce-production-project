import type { CategoryId } from "@/domain/categories";

export type ProductStatus = "draft" | "published" | "archived";
export type ImageIndexStatus = "pending" | "indexing" | "indexed" | "failed" | "removed";

export interface AdminVariant { id: string; sku: string; color: string | null; size: string | null; price: number; compare_at_price: number | null; inventory_quantity: number; is_active: boolean; created_at: string; updated_at: string; }
export interface AdminImage { id: string; storage_path: string; url: string | null; alt_text: string; sort_order: number; is_primary: boolean; index_status: ImageIndexStatus; indexed_at: string | null; index_error: string | null; created_at: string; updated_at: string; }
export interface AdminProduct { id: string; slug: string; name: string; description: string | null; category_id: CategoryId; brand: string | null; status: ProductStatus; currency: string; version: number; created_by: string | null; updated_by: string | null; created_at: string; updated_at: string; variants: AdminVariant[]; images: AdminImage[]; }
export interface AdminProductSummary { id: string; slug: string; name: string; category_id: CategoryId; brand: string | null; status: ProductStatus; currency: string; version: number; price_from: number | null; inventory_total: number; index_status: ImageIndexStatus | null; primary_image_url: string | null; primary_image_alt: string | null; updated_at: string; }
export interface AdminProductList { items: AdminProductSummary[]; total: number; page: number; page_size: number; pages: number; }

export interface ProductDraftInput { name: string; slug: string; description?: string | null; category_id: CategoryId; brand?: string | null; currency?: string; }
export interface VariantInput { sku: string; color?: string | null; size?: string | null; price: number; compare_at_price?: number | null; inventory_quantity: number; is_active: boolean; }

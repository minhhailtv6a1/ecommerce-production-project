import type { CategoryId } from "@/domain/categories";

export interface ProductImage {
  id: string;
  url: string;
  alt: string;
  sort_order: number;
  is_primary: boolean;
}

export interface ProductVariant {
  id: string;
  sku: string;
  color: string | null;
  size: string | null;
  price: number;
  compare_at_price: number | null;
  inventory_quantity: number;
  is_active: boolean;
}

export interface ProductCardData {
  id: string;
  slug: string;
  name: string;
  category_id: CategoryId;
  brand: string | null;
  price: number;
  compare_at_price: number | null;
  currency: string;
  primary_image: ProductImage;
  available_sizes: string[];
  available_colors: string[];
  in_stock: boolean;
}

export interface ProductDetail extends ProductCardData {
  description: string | null;
  status: "published";
  created_at: string;
  images: ProductImage[];
  variants: ProductVariant[];
}

export type ProductSort = "newest" | "price_asc" | "price_desc";

export interface ProductFilters {
  categoryIds?: string[];
  size?: string;
  color?: string;
  brand?: string;
  minPrice?: number;
  maxPrice?: number;
  inStock?: boolean;
  sort?: ProductSort;
  page?: number;
  limit?: number;
}

export interface ProductListResponse {
  items: ProductCardData[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

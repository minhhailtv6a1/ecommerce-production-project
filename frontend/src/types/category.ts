import type { CategoryId } from "@/domain/categories";

export interface Category {
  id: CategoryId;
  slug: string;
  name: string;
  description: string | null;
  product_count: number;
}

export interface CategoryListResponse {
  items: Category[];
}

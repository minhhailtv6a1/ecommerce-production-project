import { isCategoryId } from "@/domain/categories";
import type { CategoryListResponse } from "@/types/category";
import { requestJson } from "./http-client";
import {
  arrayValue,
  invalidResponse,
  nullableString,
  numberValue,
  record,
  stringValue,
} from "./parse";

export async function getCategories(
  signal?: AbortSignal,
): Promise<CategoryListResponse> {
  const payload = record(
    await requestJson("/categories", { signal }),
    "danh mục",
  );
  return {
    items: arrayValue(payload.items, "categories.items").map((value) => {
      const item = record(value, "danh mục");
      const id = stringValue(item.id, "category.id");
      if (!isCategoryId(id)) {
        return invalidResponse(`Backend trả về category_id không xác định: ${id}`);
      }
      return {
        id,
        slug: stringValue(item.slug, "category.slug"),
        name: stringValue(item.name, "category.name"),
        description: nullableString(item.description, "category.description"),
        product_count: numberValue(item.product_count, "category.product_count"),
      };
    }),
  };
}

import type { VisualSearchResponse } from "@/types/visual-search";
import { requestJson } from "./http-client";
import { arrayValue, numberValue, record } from "./parse";
import { parseProductCard } from "./product-parser";

export interface VisualSearchRequest {
  image: File;
  categoryIds?: string[];
  limit?: number;
}

export function buildVisualSearchFormData(
  request: VisualSearchRequest,
): FormData {
  const form = new FormData();
  form.append("image", request.image);
  request.categoryIds?.forEach((id) => form.append("category_ids", id));
  if (request.limit !== undefined) form.append("limit", String(request.limit));
  return form;
}

export async function searchByImage(
  input: VisualSearchRequest,
  signal?: AbortSignal,
): Promise<VisualSearchResponse> {
  return parseVisualSearchResponse(
    await requestJson("/image-search/search", {
      method: "POST",
      body: buildVisualSearchFormData(input),
      signal,
    }),
  );
}

export function parseVisualSearchResponse(value: unknown): VisualSearchResponse {
  const payload = record(value, "kết quả tìm kiếm ảnh");
  return {
    items: arrayValue(payload.items, "image-search.items").map((value) => {
      const item = record(value, "kết quả tìm kiếm ảnh");
      return {
        similarity_score: numberValue(
          item.similarity_score,
          "image-search.similarity_score",
        ),
        product: parseProductCard(item.product),
      };
    }),
    retrieval_time_ms: numberValue(
      payload.retrieval_time_ms,
      "image-search.retrieval_time_ms",
    ),
  };
}

import type { ProductCardData } from "./product";

export interface VisualSearchItem {
  similarity_score: number;
  product: ProductCardData;
}

export interface VisualSearchResponse {
  items: VisualSearchItem[];
  retrieval_time_ms: number;
}

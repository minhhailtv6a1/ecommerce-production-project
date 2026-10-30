import type { CategoryId } from "@/domain/categories";

export type BackendClassifierId = "alexnet" | "resnet50" | "vit";
export type ClassifierModelId = "none" | BackendClassifierId;

export interface ClassifierCapability {
  id: BackendClassifierId;
  display_name: string;
  available: boolean;
  version: string | null;
  input_size: [number, number] | null;
}

export interface ClassifierListResponse {
  items: ClassifierCapability[];
}

export interface ClassificationPrediction {
  rank: number;
  category_id: CategoryId;
  label: string;
  logit: number;
  probability: number;
}

export interface ClassificationTiming {
  preprocess_ms: number;
  inference_ms: number;
  postprocess_ms: number;
  total_ms: number;
}

export interface ImageClassificationResponse {
  model: {
    id: BackendClassifierId;
    display_name: string;
    version: string;
  };
  predictions: ClassificationPrediction[];
  suggested_category_id: CategoryId;
  timing: ClassificationTiming;
}


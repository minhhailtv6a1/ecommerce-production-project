import { isCategoryId } from "@/domain/categories";
import type {
  BackendClassifierId,
  ClassifierListResponse,
  ImageClassificationResponse,
} from "@/types/classification";
import { requestJson } from "./http-client";
import {
  arrayValue,
  booleanValue,
  invalidResponse,
  nullableString,
  numberValue,
  record,
  stringValue,
} from "./parse";

const CLASSIFIER_IDS = new Set<BackendClassifierId>([
  "alexnet",
  "resnet50",
  "vit",
]);

function classifierId(value: unknown, field: string): BackendClassifierId {
  const id = stringValue(value, field) as BackendClassifierId;
  if (!CLASSIFIER_IDS.has(id)) {
    return invalidResponse(`Backend trả về classifier không xác định: ${id}`);
  }
  return id;
}

function nullableInputSize(
  value: unknown,
  field: string,
): [number, number] | null {
  if (value === null) return null;
  const items = arrayValue(value, field);
  if (items.length !== 2) {
    return invalidResponse(`Trường ${field} phải gồm chiều cao và chiều rộng.`);
  }
  const height = numberValue(items[0], `${field}.0`);
  const width = numberValue(items[1], `${field}.1`);
  if (!Number.isInteger(height) || !Number.isInteger(width) || height <= 0 || width <= 0) {
    return invalidResponse(`Trường ${field} không hợp lệ.`);
  }
  return [height, width];
}

export async function getClassifiers(
  signal?: AbortSignal,
): Promise<ClassifierListResponse> {
  const payload = record(
    await requestJson("/image-search/classifiers", { signal }),
    "danh sách model",
  );
  return {
    items: arrayValue(payload.items, "classifiers.items").map((value) => {
      const item = record(value, "classifier");
      return {
        id: classifierId(item.id, "classifier.id"),
        display_name: stringValue(item.display_name, "classifier.display_name"),
        available: booleanValue(item.available, "classifier.available"),
        version: nullableString(item.version, "classifier.version"),
        input_size: nullableInputSize(item.input_size, "classifier.input_size"),
      };
    }),
  };
}

export interface ClassifyImageRequest {
  image: File;
  modelId: BackendClassifierId;
  topK?: number;
}

export function buildClassificationFormData(
  input: ClassifyImageRequest,
): FormData {
  const form = new FormData();
  form.append("image", input.image);
  form.append("model_id", input.modelId);
  if (input.topK !== undefined) form.append("top_k", String(input.topK));
  return form;
}

export async function classifyImage(
  input: ClassifyImageRequest,
  signal?: AbortSignal,
): Promise<ImageClassificationResponse> {
  return parseImageClassificationResponse(
    await requestJson("/image-search/classify", {
      method: "POST",
      body: buildClassificationFormData(input),
      signal,
    }),
  );
}

export function parseImageClassificationResponse(
  value: unknown,
): ImageClassificationResponse {
  const payload = record(value, "kết quả phân loại");
  const model = record(payload.model, "classification.model");
  const timing = record(payload.timing, "classification.timing");
  const predictions = arrayValue(
    payload.predictions,
    "classification.predictions",
  ).map((value, index) => {
    const prediction = record(value, "classification.prediction");
    const categoryId = stringValue(
      prediction.category_id,
      "classification.category_id",
    );
    if (!isCategoryId(categoryId)) {
      return invalidResponse(`Category dự đoán không xác định: ${categoryId}`);
    }
    const rank = numberValue(prediction.rank, "classification.rank");
    const probability = numberValue(
      prediction.probability,
      "classification.probability",
    );
    if (!Number.isInteger(rank) || rank !== index + 1) {
      return invalidResponse("Thứ hạng dự đoán không hợp lệ.");
    }
    if (probability < 0 || probability > 1) {
      return invalidResponse("Xác suất dự đoán không hợp lệ.");
    }
    return {
      rank,
      category_id: categoryId,
      label: stringValue(prediction.label, "classification.label"),
      logit: numberValue(prediction.logit, "classification.logit"),
      probability,
    };
  });

  if (predictions.length === 0 || predictions.length > 5) {
    return invalidResponse("Backend phải trả từ 1 đến 5 dự đoán.");
  }
  if (new Set(predictions.map((item) => item.category_id)).size !== predictions.length) {
    return invalidResponse("Backend trả category dự đoán bị trùng.");
  }
  if (predictions.some((item, index) => index > 0 && item.probability > predictions[index - 1].probability)) {
    return invalidResponse("Dự đoán không được sắp xếp giảm dần.");
  }
  const suggestedCategoryId = stringValue(
    payload.suggested_category_id,
    "classification.suggested_category_id",
  );
  if (!isCategoryId(suggestedCategoryId) || suggestedCategoryId !== predictions[0].category_id) {
    return invalidResponse("Category được gợi ý không khớp dự đoán hạng nhất.");
  }

  return {
    model: {
      id: classifierId(model.id, "classification.model.id"),
      display_name: stringValue(model.display_name, "classification.model.display_name"),
      version: stringValue(model.version, "classification.model.version"),
    },
    predictions,
    suggested_category_id: suggestedCategoryId,
    timing: {
      preprocess_ms: numberValue(timing.preprocess_ms, "classification.timing.preprocess_ms"),
      inference_ms: numberValue(timing.inference_ms, "classification.timing.inference_ms"),
      postprocess_ms: numberValue(timing.postprocess_ms, "classification.timing.postprocess_ms"),
      total_ms: numberValue(timing.total_ms, "classification.timing.total_ms"),
    },
  };
}


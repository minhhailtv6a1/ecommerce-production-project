import type { ClassificationPrediction } from "@/types/classification";
import type { Category } from "@/types/category";

export const CLASSIFICATION_TOAST_DURATION_MS = 3000;

export function orderCategoriesByPredictions(
  categories: Category[],
  predictions: ClassificationPrediction[],
): Category[] {
  if (predictions.length === 0) return categories;
  const byId = new Map(categories.map((category) => [category.id, category]));
  const predicted = predictions.flatMap((prediction) => {
    const category = byId.get(prediction.category_id);
    return category ? [category] : [];
  });
  const predictedIds = new Set(predicted.map((category) => category.id));
  return [
    ...predicted,
    ...categories.filter((category) => !predictedIds.has(category.id)),
  ];
}


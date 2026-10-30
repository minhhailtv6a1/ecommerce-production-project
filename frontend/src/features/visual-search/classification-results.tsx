import { formatRetrievalTime, formatSimilarity } from "@/lib/format";
import type { ImageClassificationResponse } from "@/types/classification";

interface ClassificationResultsProps {
  data: ImageClassificationResponse;
  selectedCategories: string[];
  onToggleCategory: (categoryId: string) => void;
}

export function ClassificationResults({
  data,
  selectedCategories,
  onToggleCategory,
}: ClassificationResultsProps) {
  return (
    <section className="prediction-panel" aria-labelledby="prediction-title">
      <header className="prediction-header">
        <span className="prediction-success-mark" aria-hidden="true">✓</span>
        <div>
          <span className="prediction-eyebrow">Phân loại hoàn tất</span>
          <h3 id="prediction-title">Ảnh của bạn được dự đoán thuộc các nhóm sau</h3>
        </div>
      </header>

      <div className="prediction-meta" aria-label="Thông tin lần phân loại">
        <span><strong>{data.model.display_name}</strong> · v{data.model.version}</span>
        <span>{data.predictions.length} gợi ý</span>
        <span>{formatRetrievalTime(data.timing.total_ms)}</span>
      </div>

      <p className="prediction-intro">
        Mức phần trăm là độ tin cậy của model. Bạn có thể chọn hoặc bỏ chọn bất kỳ nhóm nào trước khi tìm sản phẩm.
      </p>

      <div className="prediction-list" role="group" aria-label="Các nhóm sản phẩm được gợi ý">
        {data.predictions.map((prediction) => {
          const selected = selectedCategories.includes(prediction.category_id);
          const topPrediction = prediction.rank === 1;
          return (
            <label
              className={`prediction-item${selected ? " selected" : ""}${topPrediction ? " top" : ""}`}
              key={prediction.category_id}
            >
              <input
                checked={selected}
                onChange={() => onToggleCategory(prediction.category_id)}
                type="checkbox"
              />
              <span className="prediction-rank" aria-hidden="true">
                {String(prediction.rank).padStart(2, "0")}
              </span>
              <span className="prediction-content">
                <span className="prediction-title-row">
                  <strong>{prediction.label}</strong>
                  <span className="prediction-confidence">
                    <b>{formatSimilarity(prediction.probability)}</b>
                    <small>độ tin cậy</small>
                  </span>
                </span>
                <span className="prediction-category-note">
                  Danh mục {prediction.category_id}{topPrediction ? " · Gợi ý phù hợp nhất" : ""}
                </span>
                <progress
                  aria-label={`${prediction.label}: ${formatSimilarity(prediction.probability)} độ tin cậy`}
                  max={1}
                  value={prediction.probability}
                />
              </span>
            </label>
          );
        })}
      </div>

      <footer className="prediction-footer">
        <span aria-hidden="true">i</span>
        <p>Nhóm đầu tiên được chọn sẵn để hỗ trợ lọc vector database, nhưng bạn luôn có quyền thay đổi.</p>
      </footer>
    </section>
  );
}

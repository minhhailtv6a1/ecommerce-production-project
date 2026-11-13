import { formatRetrievalTime, formatSimilarity } from "@/lib/format";
import type { ImageClassificationResponse } from "@/types/classification";

interface ClassificationResultsProps {
  data: ImageClassificationResponse;
  selectedCategory: string | null;
  onSelectCategory: (categoryId: string) => void;
}

export function ClassificationResults({
  data,
  selectedCategory,
  onSelectCategory,
}: ClassificationResultsProps) {
  return (
    <section className="prediction-panel" aria-labelledby="prediction-title">
      <header className="prediction-header">
        <span className="prediction-success-mark" aria-hidden="true">✓</span>
        <div>
          <span className="prediction-eyebrow">Phân loại hoàn tất</span>
          <h3 id="prediction-title">Ảnh sản phẩm được dự đoán thuộc các nhóm sau</h3>
        </div>
      </header>

      <div className="prediction-meta" aria-label="Thông tin lần phân loại">
        <span><strong>{data.model.display_name}</strong> · v{data.model.version}</span>
        <span>{data.predictions.length} gợi ý</span>
        <span>{formatRetrievalTime(data.timing.total_ms)}</span>
      </div>

      <p className="prediction-intro">
        Mức phần trăm là độ tin cậy của model. Admin cần xác nhận danh mục chính xác trước khi lưu sản phẩm.
      </p>

      <div className="prediction-list" role="group" aria-label="Các nhóm sản phẩm được gợi ý">
        {data.predictions.map((prediction) => {
          const selected = selectedCategory === prediction.category_id;
          const topPrediction = prediction.rank === 1;
          return (
            <label
              className={`prediction-item${selected ? " selected" : ""}${topPrediction ? " top" : ""}`}
              key={prediction.category_id}
            >
              <input
                checked={selected}
                name="admin-category-suggestion"
                onChange={() => onSelectCategory(prediction.category_id)}
                type="radio"
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
        <p>Nhóm đầu tiên chỉ là gợi ý được chọn sẵn. Danh mục do admin xác nhận mới là dữ liệu chính thức của sản phẩm.</p>
      </footer>
    </section>
  );
}

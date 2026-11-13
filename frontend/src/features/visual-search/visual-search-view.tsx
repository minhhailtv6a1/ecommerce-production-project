"use client";

import { ChangeEvent, DragEvent, FormEvent, useEffect, useRef, useState } from "react";
import { ProductCard } from "@/components/products/product-card";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { asApiError, type ApiError } from "@/lib/api/api-error";
import { searchByImage } from "@/lib/api/visual-search.api";
import { formatRetrievalTime, formatSimilarity } from "@/lib/format";
import type { VisualSearchItem } from "@/types/visual-search";
import { validateImageFile } from "./image-validation";
import { paginateVisualSearchItems } from "./visual-search-pagination";

type SearchState =
  | { status: "idle" }
  | { status: "image-selected"; file: File; previewUrl: string }
  | { status: "searching"; file: File; previewUrl: string }
  | { status: "success"; file: File; previewUrl: string; items: VisualSearchItem[]; retrievalTimeMs: number; responseTimeMs: number }
  | { status: "empty"; file: File; previewUrl: string; retrievalTimeMs: number; responseTimeMs: number }
  | { status: "error"; file: File; previewUrl: string; error: ApiError };

function hasImage(state: SearchState): state is Exclude<SearchState, { status: "idle" }> {
  return state.status !== "idle";
}

export function VisualSearchView() {
  const [state, setState] = useState<SearchState>({ status: "idle" });
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const previewUrlRef = useRef<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const requestSequence = useRef(0);

  useEffect(
    () => () => {
      requestRef.current?.abort();
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    },
    [],
  );

  function selectFile(file: File) {
    const error = validateImageFile(file);
    if (error) {
      setValidationError(error);
      return;
    }
    requestRef.current?.abort();
    requestSequence.current += 1;
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    const previewUrl = URL.createObjectURL(file);
    previewUrlRef.current = previewUrl;
    setValidationError(null);
    setCurrentPage(1);
    setState({ status: "image-selected", file, previewUrl });
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) selectFile(file);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) selectFile(file);
  }

  function removeImage() {
    requestRef.current?.abort();
    requestSequence.current += 1;
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
    setValidationError(null);
    setCurrentPage(1);
    setState({ status: "idle" });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasImage(state) || state.status === "searching") return;
    const requestStartedAt = performance.now();
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    const sequence = ++requestSequence.current;
    const { file, previewUrl } = state;
    setCurrentPage(1);
    setState({ status: "searching", file, previewUrl });
    try {
      const response = await searchByImage(
        { image: file, limit: 50 },
        controller.signal,
      );
      if (controller.signal.aborted || sequence !== requestSequence.current) return;
      const responseTimeMs = performance.now() - requestStartedAt;
      setState(
        response.items.length === 0
          ? { status: "empty", file, previewUrl, retrievalTimeMs: response.retrieval_time_ms, responseTimeMs }
          : { status: "success", file, previewUrl, items: response.items, retrievalTimeMs: response.retrieval_time_ms, responseTimeMs },
      );
    } catch (error) {
      if (controller.signal.aborted || sequence !== requestSequence.current) return;
      setState({ status: "error", file, previewUrl, error: asApiError(error) });
    }
  }

  const searchStepState =
    state.status === "idle"
      ? ""
      : state.status === "image-selected" || state.status === "searching"
        ? "active"
        : "done";
  const resultStepState =
    state.status === "searching"
      ? "active"
      : state.status === "success" ||
          state.status === "empty" ||
          state.status === "error"
        ? "done"
        : "";
  const resultPage = state.status === "success"
    ? paginateVisualSearchItems(state.items, currentPage)
    : null;

  return (
    <div className="visual-search-page">
      <section className="visual-search-hero">
        <div className="container page-heading visual-heading">
          <div>
            <p className="eyebrow">Tìm kiếm bằng hình ảnh</p>
            <h1>Thấy món bạn thích? Tìm ngay món tương tự.</h1>
            <p>Tải ảnh tham khảo lên và Lumi sẽ gợi ý những sản phẩm có phong cách gần nhất.</p>
          </div>
          <div className="flow-badges" aria-label="Luồng tìm kiếm">
            <span className={state.status === "idle" ? "active" : "done"}>1 · Chọn ảnh</span>
            <span className={searchStepState}>2 · Tìm kiếm</span>
            <span className={resultStepState}>3 · Kết quả</span>
          </div>
        </div>
      </section>

      <div className="container visual-workspace">
        <form className="search-builder single" onSubmit={submit}>
          <section className="builder-card">
            <div className="builder-heading"><span>01</span><div><h2>Ảnh tham khảo</h2><p>Bạn có thể thay hoặc xóa ảnh trước khi tìm.</p></div></div>
            {!hasImage(state) ? (
              <label
                className={isDragging ? "dropzone dragging" : "dropzone"}
                onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={() => setIsDragging(false)}
                onDrop={onDrop}
              >
                <input type="file" accept="image/jpeg,image/png,image/webp,image/bmp" onChange={onInputChange} aria-describedby="image-help image-error" />
                <span className="upload-icon" aria-hidden="true">＋</span>
                <strong>Kéo thả ảnh vào đây</strong>
                <span>hoặc chọn tệp từ thiết bị</span>
                <small id="image-help">JPEG, PNG, WebP, BMP · tối đa 10 MiB</small>
              </label>
            ) : (
              <div className="image-preview-wrap">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={state.previewUrl} alt={`Ảnh đã chọn: ${state.file.name}`} />
                <div className="preview-meta"><div><strong>{state.file.name}</strong><span>{(state.file.size / 1024 / 1024).toFixed(2)} MiB</span></div><button className="button button-secondary button-small" type="button" onClick={removeImage}>Xóa ảnh</button></div>
              </div>
            )}
            {validationError ? <p className="field-error" id="image-error" role="alert">{validationError}</p> : null}
          </section>

          <button className="button button-primary button-large button-block" type="submit" disabled={!hasImage(state) || state.status === "searching"}>
            {state.status === "searching" ? "Đang tạo embedding và tìm kiếm…" : "Tìm sản phẩm tương tự"}
          </button>
        </form>

        <section className="search-results" aria-live="polite" aria-busy={state.status === "searching"}>
          <div className="results-header">
            <div><p className="eyebrow">Kết quả</p><h2>Sản phẩm tương đồng</h2></div>
            {state.status === "success" || state.status === "empty" ? (
              <div className="results-summary">
                <span>{state.status === "success" ? `${state.items.length} kết quả` : "0 kết quả"}</span>
                <strong>Truy vấn RAG phía server: {formatRetrievalTime(state.retrievalTimeMs)}</strong>
                <strong>Tổng thời gian phản hồi: {formatRetrievalTime(state.responseTimeMs)}</strong>
              </div>
            ) : null}
          </div>
          {state.status === "idle" || state.status === "image-selected" ? (
            <div className="results-placeholder"><span aria-hidden="true">⌁</span><h3>Kết quả sẽ xuất hiện tại đây</h3><p>Chọn một ảnh rồi bắt đầu tìm kiếm.</p></div>
          ) : state.status === "searching" ? (
            <div className="results-placeholder searching"><span className="loader" aria-hidden="true" /><h3>Đang tìm những món đồ phù hợp</h3><p>Lumi đang so sánh hình ảnh của bạn với các sản phẩm hiện có.</p></div>
          ) : state.status === "empty" ? (
            <div className="state-panel state-empty"><span className="state-icon" aria-hidden="true">0</span><div><h3>Không có kết quả phù hợp</h3><p>Hãy chọn ảnh rõ hơn hoặc thử một ảnh khác.</p></div></div>
          ) : state.status === "error" ? (
            <ApiErrorPanel error={state.error} title="Tìm kiếm không thành công" />
          ) : (
            <>
              <div className="visual-results-grid">
                {resultPage?.items.map((item) => (
                  <div className="visual-result-card" key={item.product.id}>
                    <div className="similarity-label"><span>Điểm tương đồng</span><strong>{formatSimilarity(item.similarity_score)}</strong></div>
                    <ProductCard product={item.product} />
                  </div>
                ))}
              </div>
              {resultPage && resultPage.pages > 1 ? (
                <nav className="pagination" aria-label="Phân trang kết quả tìm kiếm bằng hình ảnh">
                  <button
                    className="button button-secondary"
                    type="button"
                    disabled={resultPage.page <= 1}
                    onClick={() => setCurrentPage(resultPage.page - 1)}
                  >
                    ← Trang trước
                  </button>
                  <span>Trang <strong>{resultPage.page}</strong> / {resultPage.pages}</span>
                  <button
                    className="button button-secondary"
                    type="button"
                    disabled={resultPage.page >= resultPage.pages}
                    onClick={() => setCurrentPage(resultPage.page + 1)}
                  >
                    Trang sau →
                  </button>
                </nav>
              ) : null}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

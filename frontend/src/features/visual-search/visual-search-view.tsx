"use client";

import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { CategoryMultiSelect } from "@/components/categories/category-multi-select";
import { ProductCard } from "@/components/products/product-card";
import { ApiErrorPanel } from "@/components/ui/api-error-panel";
import { asApiError, type ApiError } from "@/lib/api/api-error";
import { classifyImage, getClassifiers } from "@/lib/api/classification.api";
import { getCategories } from "@/lib/api/categories.api";
import { SHOW_TEST_CATEGORIES } from "@/lib/env";
import { searchByImage } from "@/lib/api/visual-search.api";
import { formatRetrievalTime, formatSimilarity } from "@/lib/format";
import type { Category } from "@/types/category";
import type {
  ClassifierCapability,
  ClassifierModelId,
  ImageClassificationResponse,
} from "@/types/classification";
import type { VisualSearchItem } from "@/types/visual-search";
import { ClassificationResults } from "./classification-results";
import { ClassifierModelSelect } from "./classifier-model-select";
import { validateImageFile } from "./image-validation";
import { paginateVisualSearchItems } from "./visual-search-pagination";
import {
  CLASSIFICATION_TOAST_DURATION_MS,
  orderCategoriesByPredictions,
} from "./classification-utils";

type SearchState =
  | { status: "idle" }
  | { status: "image-selected"; file: File; previewUrl: string }
  | { status: "searching"; file: File; previewUrl: string }
  | { status: "success"; file: File; previewUrl: string; items: VisualSearchItem[]; retrievalTimeMs: number; responseTimeMs: number }
  | { status: "empty"; file: File; previewUrl: string; retrievalTimeMs: number; responseTimeMs: number }
  | { status: "error"; file: File; previewUrl: string; error: ApiError };

type ClassificationState =
  | { status: "idle" }
  | { status: "classifying" }
  | { status: "success"; data: ImageClassificationResponse }
  | { status: "error"; error: ApiError };

function hasImage(state: SearchState): state is Exclude<SearchState, { status: "idle" }> {
  return state.status !== "idle";
}

export function VisualSearchView() {
  const [state, setState] = useState<SearchState>({ status: "idle" });
  const [validationError, setValidationError] = useState<string | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryError, setCategoryError] = useState<ApiError | null>(null);
  const [classifiers, setClassifiers] = useState<ClassifierCapability[]>([]);
  const [classifiersLoading, setClassifiersLoading] = useState(true);
  const [classifierLoadError, setClassifierLoadError] = useState<ApiError | null>(null);
  const [selectedModel, setSelectedModel] = useState<ClassifierModelId>("none");
  const [classificationState, setClassificationState] = useState<ClassificationState>({ status: "idle" });
  const [showClassificationToast, setShowClassificationToast] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const previewUrlRef = useRef<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const requestSequence = useRef(0);
  const classificationRequestRef = useRef<AbortController | null>(null);
  const classificationSequence = useRef(0);
  const toastTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!SHOW_TEST_CATEGORIES) return;
    const controller = new AbortController();
    getCategories(controller.signal)
      .then((response) => setCategories(response.items))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setCategoryError(asApiError(error));
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getClassifiers(controller.signal)
      .then((response) => {
        setClassifiers(response.items);
        setClassifiersLoading(false);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setClassifierLoadError(asApiError(error));
          setClassifiersLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(
    () => () => {
      requestRef.current?.abort();
      classificationRequestRef.current?.abort();
      if (toastTimerRef.current !== null) window.clearTimeout(toastTimerRef.current);
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    },
    [],
  );

  function resetClassification() {
    classificationRequestRef.current?.abort();
    classificationSequence.current += 1;
    if (toastTimerRef.current !== null) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = null;
    setShowClassificationToast(false);
    setClassificationState({ status: "idle" });
  }

  function startClassificationToast() {
    if (toastTimerRef.current !== null) window.clearTimeout(toastTimerRef.current);
    setShowClassificationToast(true);
    toastTimerRef.current = window.setTimeout(() => {
      setShowClassificationToast(false);
      toastTimerRef.current = null;
    }, CLASSIFICATION_TOAST_DURATION_MS);
  }

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
    setSelectedCategories([]);
    resetClassification();
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
    setSelectedCategories([]);
    resetClassification();
    setState({ status: "idle" });
  }

  function changeModel(modelId: ClassifierModelId) {
    resetClassification();
    setSelectedModel(modelId);
    setSelectedCategories([]);
    setCurrentPage(1);
    if (hasImage(state) && state.status !== "searching") {
      setState({ status: "image-selected", file: state.file, previewUrl: state.previewUrl });
    }
  }

  async function runClassification() {
    if (!hasImage(state) || selectedModel === "none" || classificationState.status === "classifying") return;
    classificationRequestRef.current?.abort();
    const controller = new AbortController();
    classificationRequestRef.current = controller;
    const sequence = ++classificationSequence.current;
    const { file, previewUrl } = state;
    const modelId = selectedModel;
    setCurrentPage(1);
    setState({ status: "image-selected", file, previewUrl });
    setClassificationState({ status: "classifying" });
    try {
      const response = await classifyImage(
        { image: file, modelId, topK: 5 },
        controller.signal,
      );
      if (controller.signal.aborted || sequence !== classificationSequence.current) return;
      setSelectedCategories([response.suggested_category_id]);
      setClassificationState({ status: "success", data: response });
      startClassificationToast();
    } catch (error) {
      if (controller.signal.aborted || sequence !== classificationSequence.current) return;
      setClassificationState({ status: "error", error: asApiError(error) });
    }
  }

  function togglePredictedCategory(categoryId: string) {
    setSelectedCategories((current) =>
      current.includes(categoryId)
        ? current.filter((value) => value !== categoryId)
        : [...current, categoryId],
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const classificationAllowsSearch =
      selectedModel === "none" ||
      classificationState.status === "success" ||
      classificationState.status === "error";
    if (!hasImage(state) || state.status === "searching" || !classificationAllowsSearch) return;
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
        { image: file, categoryIds: selectedCategories, limit: 50 },
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

  const categoryStepState =
    state.status === "idle"
      ? ""
      : state.status === "image-selected"
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
  const orderedCategories = useMemo(
    () => orderCategoriesByPredictions(
      categories,
      classificationState.status === "success"
        ? classificationState.data.predictions
        : [],
    ),
    [categories, classificationState],
  );
  const classificationAllowsSearch =
    selectedModel === "none" ||
    classificationState.status === "success" ||
    classificationState.status === "error";

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
            <span className={categoryStepState}>2 · Chọn phạm vi</span>
            <span className={resultStepState}>3 · Kết quả</span>
          </div>
        </div>
      </section>

      {showClassificationToast && classificationState.status === "success" ? (
        <div className="classification-toast" role="status" aria-live="polite">
          Ảnh của bạn được dự đoán gần với các nhóm sản phẩm bên dưới. Nhóm phù hợp nhất đã được chọn.
        </div>
      ) : null}

      <div className="container visual-workspace">
        <form className={SHOW_TEST_CATEGORIES ? "search-builder" : "search-builder single"} onSubmit={submit}>
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

          <section className="builder-card">
            <div className="builder-heading"><span>02</span><div><h2>Mô hình phân loại</h2><p>Chọn model để nhận gợi ý danh mục trước khi tìm kiếm.</p></div></div>
            <ClassifierModelSelect
              classifiers={classifiers}
              disabled={state.status === "searching" || classificationState.status === "classifying"}
              loading={classifiersLoading}
              onChange={changeModel}
              value={selectedModel}
            />
            {classifierLoadError ? <p className="field-error" role="alert">Không tải được danh sách model. Bạn vẫn có thể chọn danh mục thủ công.</p> : null}
            {selectedModel !== "none" ? (
              <button
                className="button button-secondary button-block"
                type="button"
                disabled={!hasImage(state) || state.status === "searching" || classificationState.status === "classifying"}
                onClick={runClassification}
              >
                {classificationState.status === "classifying" ? "Đang phân loại ảnh…" : "Phân loại và gợi ý danh mục"}
              </button>
            ) : null}
            {classificationState.status === "error" ? (
              <p className="field-error" role="alert">{classificationState.error.message} Bạn vẫn có thể chọn danh mục thủ công và tìm kiếm.</p>
            ) : null}
          </section>

          {SHOW_TEST_CATEGORIES ? (
            <section className="builder-card">
              <div className="builder-heading"><span>03</span><div><h2>Danh mục tìm kiếm</h2><p>Bỏ trống để tìm trong tất cả sản phẩm.</p></div></div>
              {classificationState.status === "success" ? (
                <ClassificationResults
                  data={classificationState.data}
                  onToggleCategory={togglePredictedCategory}
                  selectedCategories={selectedCategories}
                />
              ) : null}
              {categoryError ? (
                <p className="field-error" role="alert">{categoryError.message}</p>
              ) : categories.length === 0 ? (
                <p className="muted">Đang tải danh mục…</p>
              ) : (
                <CategoryMultiSelect categories={orderedCategories} selected={selectedCategories} onChange={setSelectedCategories} compact />
              )}
            </section>
          ) : null}

          <button className="button button-primary button-large button-block" type="submit" disabled={!hasImage(state) || state.status === "searching" || classificationState.status === "classifying" || !classificationAllowsSearch}>
            {state.status === "searching" ? "Đang tạo embedding và tìm kiếm…" : selectedModel !== "none" && classificationState.status === "idle" ? "Hãy phân loại ảnh trước" : "Tìm sản phẩm tương tự"}
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
            <div className="results-placeholder"><span aria-hidden="true">⌁</span><h3>Kết quả sẽ xuất hiện tại đây</h3><p>Chọn ảnh, điều chỉnh danh mục rồi bắt đầu tìm kiếm.</p></div>
          ) : state.status === "searching" ? (
            <div className="results-placeholder searching"><span className="loader" aria-hidden="true" /><h3>Đang tìm những món đồ phù hợp</h3><p>Lumi đang so sánh hình ảnh của bạn với các sản phẩm hiện có.</p></div>
          ) : state.status === "empty" ? (
            <div className="state-panel state-empty"><span className="state-icon" aria-hidden="true">0</span><div><h3>Không có kết quả phù hợp</h3><p>Hãy bỏ bớt danh mục, chọn ảnh rõ hơn hoặc thử ảnh khác.</p></div></div>
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

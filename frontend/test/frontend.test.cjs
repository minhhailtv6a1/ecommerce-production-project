const assert = require("node:assert/strict");
const Module = require("node:module");
const path = require("node:path");
const test = require("node:test");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const ts = require("typescript");

const projectRoot = path.resolve(__dirname, "..");
const sourceRoot = path.join(projectRoot, "src");
const originalResolveFilename = Module._resolveFilename;

Module._resolveFilename = function resolveWithAlias(request, parent, isMain, options) {
  if (request.startsWith("@/")) {
    request = path.join(sourceRoot, request.slice(2));
  }
  return originalResolveFilename.call(this, request, parent, isMain, options);
};

function registerTypeScriptExtension(extension) {
  require.extensions[extension] = function transpile(module, filename) {
    const source = require("node:fs").readFileSync(filename, "utf8");
    const output = ts.transpileModule(source, {
      fileName: filename,
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        moduleResolution: ts.ModuleResolutionKind.NodeJs,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
        esModuleInterop: true,
      },
    }).outputText;
    module._compile(output, filename);
  };
}

registerTypeScriptExtension(".ts");
registerTypeScriptExtension(".tsx");

const { ApiError, parseApiError } = require("../src/lib/api/api-error.ts");
const { formatPrice, formatRetrievalTime } = require("../src/lib/format.ts");
const { buildProductQuery } = require("../src/lib/api/products.api.ts");
const { buildVisualSearchFormData, parseVisualSearchResponse } = require("../src/lib/api/visual-search.api.ts");
const { buildClassificationFormData, parseImageClassificationResponse } = require("../src/lib/api/classification.api.ts");
const { validateImageFile, IMAGE_MAX_BYTES } = require("../src/features/visual-search/image-validation.ts");
const { paginateVisualSearchItems, VISUAL_SEARCH_PAGE_SIZE } = require("../src/features/visual-search/visual-search-pagination.ts");
const { orderCategoriesByPredictions, CLASSIFICATION_TOAST_DURATION_MS } = require("../src/features/visual-search/classification-utils.ts");
const { ProductCard } = require("../src/components/products/product-card.tsx");
const { ProductGrid } = require("../src/components/products/product-grid.tsx");
const { ApiErrorPanel } = require("../src/components/ui/api-error-panel.tsx");
const { VisualSearchView } = require("../src/features/visual-search/visual-search-view.tsx");
const { ClassificationResults } = require("../src/features/visual-search/classification-results.tsx");
const { getNextEnabledIndex } = require("../src/features/visual-search/classifier-model-select.tsx");

const product = {
  id: "product-1",
  slug: "dam-vay-nu-demo",
  name: "Đầm nữ demo",
  category_id: "00",
  brand: "Demo Brand A",
  price: 459000,
  compare_at_price: 559000,
  currency: "VND",
  primary_image: {
    id: "image-1",
    url: "https://example.com/signed-image.jpg",
    alt: "Đầm nữ demo màu đen",
    sort_order: 0,
    is_primary: true,
  },
  available_sizes: ["S", "M"],
  available_colors: ["Đen"],
  in_stock: true,
};

test("parses the stable backend error contract", () => {
  const error = parseApiError(
    {
      code: "VALIDATION_ERROR",
      message: "Request validation failed",
      field_errors: { "query.limit": "Must be greater than zero" },
      request_id: "request-123",
    },
    422,
  );
  assert.equal(error.code, "VALIDATION_ERROR");
  assert.equal(error.status, 422);
  assert.deepEqual(error.fieldErrors, {
    "query.limit": "Must be greater than zero",
  });
  assert.equal(error.requestId, "request-123");
});

test("distinguishes a network failure", () => {
  const error = parseApiError(new TypeError("Failed to fetch"), null);
  assert.equal(error.code, "NETWORK_ERROR");
  assert.match(error.message, /tạm thời gián đoạn/);
});

test("formats VND prices and preserves other currency labels", () => {
  assert.match(formatPrice(459000, "VND").replace(/\u00a0/g, " "), /459[.\s]000\s₫/);
  assert.match(formatPrice(25, "USD"), /USD/);
});

test("builds repeated category_ids without losing leading zeros", () => {
  const params = new URLSearchParams(
    buildProductQuery({
      categoryIds: ["00", "01"],
      sort: "price_asc",
      page: 2,
      limit: 20,
    }),
  );
  assert.deepEqual(params.getAll("category_ids"), ["00", "01"]);
  assert.equal(params.get("sort"), "price_asc");
  assert.equal(params.get("page"), "2");
});

test("builds visual-search multipart fields", () => {
  const file = new File(["image-data"], "query.png", { type: "image/png" });
  const form = buildVisualSearchFormData({
    image: file,
    categoryIds: ["00", "41"],
    limit: 50,
  });
  assert.equal(form.get("image"), file);
  assert.deepEqual(form.getAll("category_ids"), ["00", "41"]);
  assert.equal(form.get("limit"), "50");
});

test("parses and formats server-side RAG retrieval time", () => {
  const response = parseVisualSearchResponse({
    items: [],
    retrieval_time_ms: 364.01,
  });
  assert.equal(response.retrieval_time_ms, 364.01);
  assert.match(formatRetrievalTime(response.retrieval_time_ms), /364,01 ms/);
});

test("builds and parses the top-five classification contract", () => {
  const file = new File(["image-data"], "query.png", { type: "image/png" });
  const form = buildClassificationFormData({
    image: file,
    modelId: "alexnet",
    topK: 5,
  });
  assert.equal(form.get("image"), file);
  assert.equal(form.get("model_id"), "alexnet");
  assert.equal(form.get("top_k"), "5");

  const response = parseImageClassificationResponse({
    model: { id: "alexnet", display_name: "AlexNet", version: "1.0.0" },
    predictions: [
      { rank: 1, category_id: "02", label: "Áo Thun", logit: 8.4, probability: 0.87 },
      { rank: 2, category_id: "28", label: "Áo Khoác", logit: 5.1, probability: 0.07 },
    ],
    suggested_category_id: "02",
    timing: { preprocess_ms: 2, inference_ms: 30, postprocess_ms: 1, total_ms: 33 },
  });
  assert.equal(response.predictions[0].category_id, "02");
  assert.equal(response.suggested_category_id, "02");
});

test("orders predicted categories first and keeps the toast for three seconds", () => {
  const categories = [
    { id: "00", slug: "zero", name: "Zero", description: null, product_count: 1 },
    { id: "02", slug: "two", name: "Two", description: null, product_count: 1 },
    { id: "28", slug: "twenty-eight", name: "Twenty Eight", description: null, product_count: 1 },
  ];
  const predictions = [
    { rank: 1, category_id: "28", label: "Twenty Eight", logit: 2, probability: 0.7 },
    { rank: 2, category_id: "02", label: "Two", logit: 1, probability: 0.2 },
  ];
  assert.deepEqual(
    orderCategoriesByPredictions(categories, predictions).map((item) => item.id),
    ["28", "02", "00"],
  );
  assert.equal(CLASSIFICATION_TOAST_DURATION_MS, 3000);
});

test("renders the classifier model picker as an accessible custom dropdown", () => {
  const html = renderToStaticMarkup(React.createElement(VisualSearchView));
  assert.match(html, /id="classifier-model"/);
  assert.match(html, /aria-haspopup="listbox"/);
  assert.match(html, /Không dùng model/);
  assert.doesNotMatch(html, /<select/);
  assert.doesNotMatch(html, /type="radio"/);
});

test("skips unavailable models during dropdown keyboard navigation", () => {
  const availability = [true, true, false, false];
  assert.equal(getNextEnabledIndex(availability, 0, 1), 1);
  assert.equal(getNextEnabledIndex(availability, 1, 1), 0);
  assert.equal(getNextEnabledIndex(availability, 0, -1), 1);
});

test("renders classification confidence as a selectable ranked result", () => {
  const data = {
    model: { id: "alexnet", display_name: "AlexNet", version: "1.0.0" },
    predictions: [
      { rank: 1, category_id: "02", label: "Áo Thun / Áo Phông", logit: 8.4, probability: 0.87 },
      { rank: 2, category_id: "28", label: "Áo Khoác Nam Nữ", logit: 5.1, probability: 0.07 },
    ],
    suggested_category_id: "02",
    timing: { preprocess_ms: 2, inference_ms: 30, postprocess_ms: 1, total_ms: 33 },
  };
  const html = renderToStaticMarkup(
    React.createElement(ClassificationResults, {
      data,
      selectedCategories: ["02"],
      onToggleCategory: () => {},
    }),
  );
  assert.match(html, /Phân loại hoàn tất/);
  assert.match(html, /87%/);
  assert.match(html, /Gợi ý phù hợp nhất/);
  assert.match(html, /type="checkbox" checked=""/);
});

test("paginates 50 visual-search results without running retrieval again", () => {
  const items = Array.from({ length: 50 }, (_, index) => index + 1);
  const first = paginateVisualSearchItems(items, 1);
  const second = paginateVisualSearchItems(items, 2);
  const last = paginateVisualSearchItems(items, 3);

  assert.equal(VISUAL_SEARCH_PAGE_SIZE, 20);
  assert.deepEqual(first.items, items.slice(0, 20));
  assert.deepEqual(second.items, items.slice(20, 40));
  assert.deepEqual(last.items, items.slice(40, 50));
  assert.equal(last.pages, 3);
  assert.equal(last.total, 50);
});

test("validates image MIME and backend size limit", () => {
  assert.equal(
    validateImageFile(new File(["ok"], "query.png", { type: "image/png" })),
    null,
  );
  assert.match(
    validateImageFile(new File(["bad"], "query.gif", { type: "image/gif" })),
    /chưa được hỗ trợ/i,
  );
  assert.match(
    validateImageFile(
      new File([new Uint8Array(IMAGE_MAX_BYTES + 1)], "large.jpg", {
        type: "image/jpeg",
      }),
    ),
    /10 MiB/i,
  );
});

test("renders a product card from backend fields", () => {
  const html = renderToStaticMarkup(React.createElement(ProductCard, { product }));
  assert.match(html, /Đầm nữ demo/);
  assert.match(html, /Demo Brand A/);
  assert.match(html, /Đầm nữ demo màu đen/);
  assert.match(html, /\/products\/dam-vay-nu-demo/);
  assert.match(html, /Còn hàng/);
});

test("renders distinct empty and error states", () => {
  const emptyHtml = renderToStaticMarkup(
    React.createElement(ProductGrid, { products: [] }),
  );
  assert.match(emptyHtml, /Chưa tìm thấy sản phẩm/);

  const error = new ApiError(
    {
      code: "SERVICE_UNAVAILABLE",
      message: "Product images are temporarily unavailable",
      field_errors: {},
      request_id: "request-456",
    },
    503,
  );
  const errorHtml = renderToStaticMarkup(
    React.createElement(ApiErrorPanel, { error }),
  );
  assert.match(errorHtml, /Product images are temporarily unavailable/);
  assert.match(errorHtml, /request-456/);
});

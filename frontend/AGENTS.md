# AGENTS.md — Image-Based E-commerce Frontend

## 1. Purpose and Scope

You are the AI coding agent responsible for building and maintaining the customer-facing frontend for this repository.

The product is a Vietnamese e-commerce website centered on image-based product discovery. A customer should be able to upload a product image, review category suggestions from the classifier, adjust the selected categories, search for visually similar products, inspect product information, and continue through familiar shopping flows when the corresponding backend capabilities exist.

The frontend lives in `frontend/`. The sibling `backend/` directory is a Python FastAPI application. Read `../backend/README.md`, `../backend/Agents.md`, and the relevant backend routes and schemas before implementing an integration.

The expected frontend stack is:

- Next.js with TypeScript.
- React Server Components and the App Router when the project is scaffolded with a Next.js version that supports them.
- A responsive, accessible component system suitable for desktop and mobile shopping.
- Automated unit/component tests and end-to-end tests appropriate to the chosen scaffold.

The `frontend/` directory is initially empty. Do not claim that a package manager, UI library, test framework, lint configuration, or deployment target is already established until the corresponding files exist. When scaffolding is requested, use a current stable Next.js setup and document every material choice.

## 2. Product Goals

Build a polished storefront that makes visual product search the primary differentiator while retaining recognizable e-commerce navigation.

The main customer journey is:

1. Land on the storefront and understand that products can be found from an image.
2. Select, drag and drop, paste, or capture an image where the browser supports it.
3. Preview the image and correct common input problems before upload.
4. Receive ranked category suggestions from the classifier.
5. Select, deselect, or combine categories. The predicted category is only a suggestion.
6. Submit the visual search.
7. Browse ranked product results with clear loading, empty, error, and retry states.
8. Open a product to review authoritative details such as title, price, images, availability, and description when supplied by the backend.
9. Use cart, checkout, authentication, favorites, reviews, or order history only after their data contracts are implemented or explicitly requested as UI-only prototypes.

Do not let conventional storefront features obscure image search. The upload/search action should be easy to find on the home page and remain reachable from result and catalog pages.

## 3. Current Backend Reality

Always distinguish implemented backend behavior from planned behavior.

At the time this file was created, the only browser-consumable backend route is:

```http
GET /api/v1/health
```

```json
{ "status": "ok" }
```

FastAPI documentation is available at `/docs` while the backend is running. The default local backend origin is `http://127.0.0.1:8000`, and the configured API prefix is `/api/v1`.

The backend already contains internal services and command-line scripts for:

- CLIP `ViT-B-32` image embeddings with 512 dimensions.
- Pinecone similarity search using the `image_vector` field and cosine similarity.
- Optional filtering by one or more canonical category IDs.
- Ranked matches containing `_id`, `score`, `category_id`, and dataset-relative `image_path`.

Those services are not REST endpoints. Product hydration from Supabase, product catalog APIs, classifier upload APIs, authentication, cart, orders, payments, and checkout APIs are not implemented yet.

Consequences for frontend work:

- Never invent an endpoint, request field, response field, database column, image URL, price, inventory state, or authentication behavior and present it as real.
- Inspect FastAPI OpenAPI output or route/schema source before writing an API client.
- Treat CLI output and Pinecone document structure as backend implementation details, not automatically as public API contracts.
- If a feature is blocked by a missing contract, build the reusable UI state separately only when that is within the task. Keep fixtures clearly labeled and isolated from production API code.
- Do not make the browser connect directly to Pinecone, Supabase PostgreSQL, model artifacts, or any provider that requires a secret.
- CORS is not currently configured in `backend/app/main.py`. For cross-origin browser calls, coordinate a backend CORS change or use an intentional same-origin Next.js server/proxy design. Do not work around CORS by disabling browser security.

## 4. Frontend Responsibilities

Act as a pragmatic senior frontend engineer with responsibility for:

1. Translating product requirements into clear, responsive user journeys.
2. Building maintainable Next.js and TypeScript code.
3. Defining a small, reusable design system rather than one-off page styling.
4. Isolating backend communication behind typed adapters.
5. Handling asynchronous and error states deliberately.
6. Protecting secrets and minimizing client-side data exposure.
7. Meeting accessibility and performance expectations.
8. Writing tests for high-value behavior and regression risks.
9. Keeping documentation and environment templates accurate.

Do not modify backend behavior as a side effect of a frontend task unless the requested feature explicitly requires coordinated changes. If a public API contract must change, describe the required backend work and keep both sides aligned.

## 5. Canonical Categories

Category IDs are stable two-character strings. Preserve leading zeros and the exact Vietnamese display names. Do not convert IDs to numbers, infer them from array positions, translate them silently, or reorder the canonical mapping in a way that changes identity.

```ts
export const CATEGORY_LABELS = {
  "00": "Đầm / Váy Nữ",
  "01": "Đầm Dáng Dài / Maxi",
  "02": "Áo Thun / Áo Phông",
  "03": "Áo Nỉ, Hoodie & Áo Len",
  "04": "Quần Jeans Nữ",
  "05": "Nhẫn & Trang Sức",
  "06": "Bông Tai / Khuyên Tai",
  "07": "Mũ & Nón Thời Trang",
  "08": "Ví & Bóp Tiền",
  "09": "Vali & Túi Du Lịch",
  "10": "Ốp Lưng & Phụ Kiện Điện Thoại",
  "11": "Điện Thoại & Máy Tính Bảng",
  "12": "Đồng Hồ Treo Tường & Để Bàn",
  "13": "Đồ Dùng Cho Bé Ăn Dặm",
  "14": "Nồi Cơm Điện & Bếp Điện",
  "15": "Cà Phê & Dụng Cụ Pha Chế",
  "16": "Giày Đế Bằng & Giày Búp Bê",
  "17": "Giày Cao Gót & Sandal Nữ",
  "18": "Tủ Lạnh & Máy Lạnh",
  "19": "Thẻ Nhớ & USB Lưu Trữ",
  "20": "Bàn Ghế & Nội Thất",
  "21": "Dụng Cụ Thể Thao Vợt",
  "22": "Mũ Bảo Hiểm & Đồ Bảo Hộ",
  "23": "Găng Tay Thời Trang & Bảo Hộ",
  "24": "Đồng Hồ Đeo Tay",
  "25": "Thắt Lưng / Dây Nịt",
  "26": "Tai Nghe & Thiết Bị Âm Thanh",
  "27": "Mô Hình Xe & Đồ Chơi Phương Tiện",
  "28": "Áo Khoác Nam Nữ",
  "29": "Quần Nam",
  "30": "Giày Thể Thao & Sneaker",
  "31": "Bánh Kẹo & Đồ Ăn Vặt",
  "32": "Khẩu Trang & Vật Tư Y Tế",
  "33": "Gel Sát Khuẩn & Nước Rửa Tay",
  "34": "Mỹ Phẩm & Trang Điểm",
  "35": "Nước Hoa & Xịt Thơm",
  "36": "Dụng Cụ Vệ Sinh & Sửa Chữa Nhà Cửa",
  "37": "Laptop & Phụ Kiện Máy Tính",
  "38": "Bát Đĩa & Bàn Ăn",
  "39": "Bình Hoa & Decor Trang Trí",
  "40": "Thiết Bị Phòng Tắm & Vòi Sen",
  "41": "Sofa & Ghế Phòng Khách",
} as const;

export type CategoryId = keyof typeof CATEGORY_LABELS;
```

Keep this mapping in one domain module when the source is scaffolded. API payloads use the stable ID; UI renders the Vietnamese label. Validate unknown IDs received at runtime instead of asserting them blindly.

## 6. Information Architecture and Screens

Implement only the screens required by the current task, but keep navigation and components compatible with this target structure:

- Home: value proposition, prominent visual-search entry point, categories, and real featured content when an API supplies it.
- Visual search: upload area, preview, validation, category suggestions, category controls, and search submission.
- Search results: query-image summary, active filters, result count, sorting if supported, product grid, pagination or incremental loading, and recovery states.
- Catalog/category: category context and product browsing when a catalog endpoint exists.
- Product detail: gallery and authoritative product information when a product endpoint exists.
- Cart and checkout: only when required and backed by an agreed persistence/commerce contract, or explicitly labeled as a prototype.
- Account and orders: only when authentication and order APIs exist.

Use semantic URLs that can be shared and refreshed. Put durable filters, category IDs, sort values, page numbers, and search identifiers in URL state when appropriate. Do not place raw image bytes, object URLs, secrets, or oversized serialized state in a URL.

## 7. Visual and Interaction Direction

The experience should feel like a trustworthy modern Vietnamese marketplace, not an admin dashboard or a generic AI demo.

- Prioritize product imagery, readable prices, category context, and a strong search action.
- Use a restrained neutral base with a consistent brand accent and status colors.
- Define design tokens for color, spacing, typography, radius, shadow, and motion. Avoid scattered magic values.
- Keep hierarchy obvious: one primary action per section, clear page titles, and recognizable controls.
- Use whitespace and alignment deliberately. Do not fill every area with cards, gradients, badges, or decorative icons.
- Design mobile-first and verify common widths from small phones through large desktops.
- Keep important upload, filter, and purchase controls reachable without precision pointing.
- Use motion sparingly, respect `prefers-reduced-motion`, and never delay task completion for decoration.
- Write concise Vietnamese customer-facing copy with correct diacritics. Use consistent terminology across pages.
- Never use misleading urgency, fake discounts, fabricated ratings, fake stock counts, or deceptive calls to action.

Product cards should show only fields actually available. They should have stable dimensions to prevent layout shift and should not hide essential information behind hover-only behavior.

## 8. Image Upload and Search UX

Image search is a stateful workflow. Model it explicitly rather than using unrelated booleans.

Recommended states include `idle`, `validating`, `ready`, `classifying`, `choosing-categories`, `searching`, `success`, and `error`. Names may differ, but impossible combinations such as loading and success at the same time should be difficult to represent.

For uploads:

- Use the actual backend limits once implemented. Until then, do not state an invented maximum file size as a backend guarantee.
- Validate known client-side constraints early, while treating server validation as authoritative.
- Support only formats confirmed by the public API. Do not infer browser upload formats from backend dataset-script extensions.
- Show the chosen filename or an understandable image preview.
- Allow replacement and removal before submission.
- Explain validation failures next to the upload control and announce them to assistive technology.
- Revoke object URLs when images are replaced, removed, or the component unmounts.
- Do not persist user-uploaded images to analytics, logs, local storage, or third parties without an explicit requirement and disclosure.
- Prevent stale requests from overwriting newer search state. Abort obsolete requests when practical.

For category suggestions:

- Display classifier confidence only if the API returns it and define whether it is a `0–1` value or percentage.
- Preserve backend ranking when showing suggestions.
- Preselecting the top suggestion may be acceptable, but the customer must be able to remove it and choose one or more other categories.
- Do not describe classifier confidence as product similarity.
- Do not describe Pinecone similarity score as probability or model confidence.

For results:

- Preserve backend ranking unless the user selects a supported alternate sort.
- Keep similarity score hidden by default unless it helps the intended audience; if shown, label it accurately.
- Treat an empty successful response differently from a failed request.
- Provide a useful next action: broaden categories, change the image, clear filters, or retry.

## 9. Suggested Source Organization

After scaffolding, prefer a feature-oriented structure similar to:

```text
frontend/
├── AGENTS.md
├── README.md
├── .env.example
├── package.json
├── public/
├── src/
│   ├── app/                  # Routes, layouts, loading/error boundaries
│   ├── components/
│   │   ├── ui/              # Small reusable primitives
│   │   └── layout/          # Header, navigation, footer
│   ├── features/
│   │   ├── image-search/    # Workflow, hooks, state, feature components
│   │   ├── products/        # Product cards, grids, product domain UI
│   │   └── cart/            # Add only when required
│   ├── lib/
│   │   ├── api/             # Typed transport and endpoint adapters
│   │   ├── env/             # Validated environment access
│   │   └── utils/           # Genuinely shared utilities
│   ├── domain/              # Categories and stable domain types
│   └── test/                # Shared test setup and fixtures
└── e2e/                     # High-value browser flows when configured
```

This is a direction, not a mandate to create empty folders. Keep route-specific components close to their route until reuse or domain ownership is clear.

Avoid:

- A single oversized page component containing transport, state, formatting, and rendering.
- A generic `utils.ts` dumping ground.
- Deep barrel-export chains that create circular dependencies.
- Global client state for data that belongs to a route, form, URL, or server cache.
- Premature abstractions that support only one call site.

## 10. Next.js and React Rules

- Prefer Server Components for static content and server-readable data.
- Add `"use client"` only at the narrowest interactive boundary that needs browser APIs, state, effects, or event handlers.
- Do not turn an entire route or layout into a Client Component merely for one interactive child.
- Use framework metadata APIs for page titles, descriptions, canonical URLs, and social metadata.
- Use `next/image` for product and marketing images when source hosts and dimensions are known. Configure remote patterns narrowly.
- Provide meaningful `alt` text for informative images and empty alt text for decorative images.
- Use route-level `loading`, `error`, and `not-found` handling where it improves recovery.
- Do not use an effect to derive values that can be computed during render.
- Keep keys stable; never use array indexes for reorderable/filterable product lists.
- Clean up object URLs, timers, observers, and subscriptions.
- Treat hydration warnings as defects. Do not suppress them without identifying the source.
- Keep browser-only APIs behind client boundaries and guard optional platform features.

## 11. TypeScript and Domain Modeling

- Use strict TypeScript settings.
- Do not use `any` to bypass an unknown API shape. Use `unknown` and validate at the boundary.
- Model API request and response types separately from view models when transformation is meaningful.
- Use discriminated unions for meaningful workflow states and result variants.
- Keep money as an integer in the smallest agreed currency unit or use the exact backend representation. Never use floating-point arithmetic for checkout totals.
- Format Vietnamese currency with `Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" })` only when the backend confirms the value is VND.
- Treat IDs as opaque strings.
- Treat optional and nullable fields according to the public schema; do not normalize missing data into invented values.
- Validate environment variables and untrusted runtime responses at clear boundaries if the selected stack includes a schema-validation library.

## 12. API Integration

Centralize API access. Components should consume typed feature functions rather than construct URLs or call `fetch` ad hoc.

- Use a single configurable base URL, normally exposed as `NEXT_PUBLIC_API_BASE_URL` only when direct browser requests are intentional.
- Keep server-only environment variables in server-only modules without the `NEXT_PUBLIC_` prefix.
- Never expose `PINECONE_API_KEY`, database credentials, `JWT_SECRET`, model paths, or other backend `.env` values to the browser.
- Prefer the backend OpenAPI schema as the source of truth after routes exist. If generating types, make the command reproducible and document whether generated files are committed.
- Normalize network errors into a small application error model without discarding useful HTTP status and validation details.
- Check `response.ok`; do not assume every JSON response is successful.
- Set request headers intentionally. Let the browser set multipart boundaries for `FormData`.
- Use abort signals and reasonable timeouts for long-running image operations.
- Do not retry validation failures. Retry transient failures conservatively and never duplicate a state-changing commerce request without idempotency guarantees.
- Do not log full upload payloads, secrets, tokens, or personal information.

When a public image-search contract is added, confirm at minimum:

- Endpoint path and HTTP method.
- Multipart field name and accepted MIME types/size.
- Whether classification and retrieval are one request or separate requests.
- Category request shape and whether category selection is optional.
- Response schemas for category suggestions, product IDs, images, scores, pagination, and errors.
- How dataset-relative `image_path` values become browser-accessible image URLs.
- Cancellation, timeout, and maximum result behavior.

Do not implement against assumptions when any of these choices affect compatibility.

## 13. Data, Fixtures, and Missing Features

Use real APIs when they exist. For independent UI development before an API exists:

- Put deterministic fixtures in test/story/demo-only modules.
- Mark prototype screens and placeholder data clearly in code and documentation.
- Keep the production adapter from silently falling back to mock products after an error.
- Do not ship mock checkout, fake authentication, or fake order confirmation in a way customers could mistake for a completed transaction.
- Use neutral placeholder media with known licensing or locally created assets. Do not hotlink arbitrary marketplace images.

If a task asks for a complete visual prototype, a fixture-backed adapter is acceptable when explicitly disclosed and easy to replace. If a task asks for working integration, missing backend contracts are blockers to that portion and must be reported precisely.

## 14. Accessibility

Target WCAG 2.2 AA practices for all new UI.

- Use semantic elements before adding ARIA.
- Ensure every action is keyboard operable and has a visible focus state.
- Associate labels, descriptions, and errors with form controls.
- Make drag-and-drop upload also work through a standard file input.
- Announce asynchronous search status and validation feedback without excessive live-region noise.
- Use real buttons and links for their intended behavior.
- Provide sufficient text and control contrast in all states.
- Do not communicate category selection, error, discount, or stock state by color alone.
- Maintain logical heading order and predictable focus after dialogs or route changes.
- Ensure touch targets are comfortably sized and controls do not depend on hover.
- Test at increased text size and browser zoom.

## 15. Performance and Reliability

- Optimize for useful content and interaction, not a perfect synthetic score at the expense of correctness.
- Prevent layout shift by reserving image and skeleton dimensions.
- Avoid eagerly loading full-resolution images outside the initial viewport.
- Keep client JavaScript small by limiting client boundaries and heavy dependencies.
- Lazy-load expensive secondary UI where it helps without hiding the primary search flow.
- Debounce only inputs that genuinely trigger repeated work; do not add delay to buttons.
- Cache public, stable data deliberately. Do not cache private account, cart, or order data across users.
- Make loading states resemble the final layout and keep them accessible.
- Protect against duplicate submissions and out-of-order responses.
- Verify behavior on slow connections and backend failure, not only the success path.

## 16. Security and Privacy

- Treat all API data, route parameters, query strings, and uploaded filenames as untrusted.
- Rely on React escaping and avoid raw HTML. If rich HTML becomes required, sanitize it with an approved, maintained solution.
- Do not store bearer tokens in `localStorage` by default. Follow the agreed authentication design, preferring secure HTTP-only cookies where applicable.
- Do not put secrets or sensitive customer data in URLs, client bundles, analytics events, or error-reporting breadcrumbs.
- Validate redirect destinations to prevent open redirects.
- For checkout, render amounts from authoritative backend responses and never let client calculations become the source of truth.
- Do not add trackers, session replay, pixels, or third-party upload services without an explicit requirement and privacy review.
- Keep dependencies minimal and review their maintenance and bundle impact before adding them.

## 17. Testing and Validation

Choose test tools that match the scaffold instead of introducing multiple overlapping frameworks.

At minimum, cover high-risk behavior such as:

- Canonical category IDs remain strings and preserve leading zeros.
- Upload validation and image replacement/removal.
- Category suggestion selection, including multiple categories and removing the top prediction.
- Loading, empty, validation-error, server-error, and retry states.
- Stale/aborted searches do not overwrite the latest result.
- Product/result rendering tolerates optional fields defined by the schema.
- Keyboard use and key accessibility properties for custom interactive UI.
- The primary end-to-end image-search journey once its API exists.

Mock external services at the network boundary for unit/component tests. Keep a small number of contract or end-to-end checks against a real local backend when they add confidence and can run predictably.

Before reporting completion, run the relevant commands available in `package.json`, typically formatting, linting, type checking, tests, and a production build. Report the exact commands and results. Never state that checks pass if they were not run successfully.

## 18. Agent Workflow

For each task:

1. Read this file and inspect the relevant frontend files.
2. Inspect current backend routes, schemas, OpenAPI, and README when integration is involved.
3. State material assumptions, especially around missing API contracts or prototype data.
4. Implement the smallest coherent feature that meets the request.
5. Reuse established components and tokens without forcing unrelated refactors.
6. Add or update tests and documentation for changed behavior.
7. Run proportionate validation, including a production build for routing, configuration, or rendering changes.
8. Review the page at mobile and desktop widths when UI changes materially.
9. Summarize changed files, actual validation results, and any backend dependency still missing.

Do not:

- Rewrite unrelated code.
- Change the 42-category mapping without explicit approval.
- Invent a backend contract or silently conceal missing integration with mocks.
- Add a large state library, UI kit, form library, or data-fetching library before the need is demonstrated.
- Expose backend secrets in frontend environment variables.
- perform destructive backend, database, index, filesystem, or deployment actions as part of routine frontend work.
- claim a browser flow works without testing the relevant state or clearly explaining what remains mocked.

## 19. Definition of Done

A frontend task is complete when:

- The requested customer behavior works at the intended routes and viewport sizes.
- The implementation follows the real backend contract or clearly identifies an intentional prototype boundary.
- Loading, empty, success, validation, and failure states relevant to the feature are handled.
- Accessibility and keyboard behavior have been considered and verified proportionately.
- Types are strict, secrets remain server-side, and no fabricated commerce facts are shown as real.
- Relevant formatting, lint, type-check, test, and build commands have been run where available.
- Documentation and `.env.example` are updated when setup or configuration changes.
- The final report accurately names what changed, what was verified, and what remains blocked or unimplemented.

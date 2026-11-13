# Kế hoạch chuyển Classification sang Admin Catalog Management

**Ngày lập:** 12/11/2026  
**Phạm vi:** thay đổi luồng visual search của khách hàng, bổ sung RBAC cho admin, xây backend quản trị catalog và frontend quản trị sản phẩm.  
**Nguồn yêu cầu:** `frontend/AGENTS.md`, `backend/Agents.md` và source hiện tại trong `frontend/src`, `backend/app`, `backend/scripts`.

## 1. Quyết định nghiệp vụ

Module Deep Learning classification không còn nằm trong luồng tìm kiếm của khách hàng.

- Khách hàng chỉ tải ảnh và tìm sản phẩm tương đồng bằng CLIP/Pinecone.
- Không yêu cầu khách hàng chọn model hoặc xác nhận category trước khi search.
- Không dùng category do classifier dự đoán để filter Pinecone trong customer visual search.
- AlexNet/ResNet50/ViT trở thành công cụ hỗ trợ admin xác định category khi tạo hoặc chỉnh sửa sản phẩm.
- Model trả top-k category theo Softmax giảm dần; admin là người quyết định category cuối cùng.
- Category được admin xác nhận mới là dữ liệu authoritative lưu vào `products.category_id` và metadata Pinecone.
- Logits/Softmax không được dùng thay CLIP embedding để tìm sản phẩm.

### Lý do chuyển đổi

1. Customer search không filter category có luồng ngắn và ổn định hơn.
2. Metadata filter không mặc nhiên làm vector search nhanh hơn; cả hai trường hợp hiện vẫn lấy `top_k=50`.
3. Classification tạo thêm một request, model inference và human-in-the-loop trước retrieval.
4. Category prediction có giá trị nghiệp vụ cao hơn tại thời điểm chuẩn hóa dữ liệu catalog.
5. Admin hiểu sản phẩm và có trách nhiệm xác nhận category nên phù hợp với human-in-the-loop hơn khách hàng.

## 2. Phạm vi và ngoài phạm vi

### 2.1 Trong phạm vi

- Trả customer visual search về luồng ảnh → CLIP → Pinecone → hydrate product.
- Chuyển classification endpoint thành admin-only.
- Thêm role `customer` và `admin` vào custom authentication hiện tại.
- Phân quyền backend bằng dependency, không chỉ ẩn UI.
- Thêm API admin để xem, tạo, sửa, archive sản phẩm, variant và ảnh.
- Dùng classifier gợi ý top category trong form tạo/chỉnh sửa sản phẩm.
- Đồng bộ sản phẩm published với Supabase Storage và Pinecone.
- Xây frontend `/admin` có product list và product form.
- Bổ sung migration, test, audit và tài liệu vận hành.

### 2.2 Chưa nằm trong phạm vi đầu tiên

- Multi-vendor marketplace hoặc mỗi seller chỉ sở hữu một tập sản phẩm.
- Role động, permission editor hoặc giao diện tự cấp quyền admin.
- Hard-delete sản phẩm published khỏi toàn bộ hệ thống.
- Quản lý order/payment dành cho admin.
- Bulk import catalog qua UI.
- Retrain model, calibration hoặc tự động thay category mà không có admin xác nhận.
- Dùng classifier logits làm embedding cho Pinecone.

## 3. Hiện trạng source code

| Thành phần | Hiện trạng | Tác động cần xử lý |
| --- | --- | --- |
| Customer visual search | Model selector, classify request, top-5 prediction, category selector rồi mới search | Xóa dependency classification/category khỏi customer flow |
| Image search API | Nhận `image`, lặp `category_ids`, `limit`; filter Pinecone khi có category | Contract cuối chỉ cần `image` và `limit` |
| Classifier backend | Registry lazy-load, manifest, AlexNet adapter và `/image-search/classifiers`, `/image-search/classify` | Tái sử dụng service; chuyển route sang `/admin` và bắt buộc role admin |
| Auth | Custom JWT, `users` có email/password/is_active nhưng chưa có role | Migration role, cập nhật UserRecord/schema và dependency `require_admin` |
| Token | JWT chỉ lưu `sub`; mỗi protected request vẫn đọc user từ DB | Có thể giữ token hiện tại; role DB là nguồn quyết định authoritative |
| Catalog DB | Có categories, products, product_variants, product_images | Bổ sung provenance/audit/index status phục vụ CRUD admin |
| Product lifecycle | Đã có `draft`, `published`, `archived` | Dùng đúng lifecycle, không hard-delete mặc định |
| Public catalog API | Chỉ đọc published products | Giữ nguyên; admin API riêng có thể đọc cả draft/archived |
| Supabase Storage | Có upload script và URL resolver | Cần service upload/delete dành cho HTTP admin flow |
| Pinecone | Có search/upsert/update/fetch, chưa có đầy đủ delete/retry orchestration | Bổ sung index lifecycle cho create/update/archive/image delete |
| Frontend auth | Bearer token giữ trong memory, reload mất session | Dùng được cho MVP; backend RBAC vẫn authoritative, session persistence là hardening riêng |
| Frontend admin | Chưa có route/layout/admin API adapter | Xây mới theo feature boundary riêng |

## 4. Kiến trúc đích

```text
CUSTOMER
  chọn ảnh
     -> validate upload
     -> CLIP embedding 512 chiều
     -> Pinecone similarity search, không category filter
     -> hydrate published products từ PostgreSQL/Supabase
     -> kết quả + retrieval timing

ADMIN
  đăng nhập
     -> backend xác thực user và role=admin
     -> chọn ảnh sản phẩm
     -> classifier inference
     -> Softmax trên đủ 42 lớp
     -> hiển thị top-k category
     -> admin xác nhận một category
     -> lưu product draft + variants + images
     -> validate điều kiện publish
     -> CLIP embedding ảnh sản phẩm
     -> upsert Pinecone với category authoritative
     -> publish product
```

### 4.1 Boundary bắt buộc

| Module | Trách nhiệm | Không được làm |
| --- | --- | --- |
| Classifier | Gợi ý category cho admin | Tự publish hoặc quyết định category cuối cùng |
| CLIP | Sinh image embedding cho retrieval/indexing | Dùng Softmax classifier thay embedding |
| PostgreSQL | Nguồn sự thật của product/category/variant/inventory/status | Tin metadata Pinecone hơn DB |
| Pinecone | Tìm vector và giữ metadata đủ để nối về product/image | Trở thành nguồn dữ liệu giá, tồn kho hoặc trạng thái published |
| Supabase Storage | Lưu ảnh catalog | Nhận secret từ frontend |
| Frontend admin | Thu thập input, hiển thị prediction, xác nhận hành động | Tin role phía client như lớp bảo mật duy nhất |
| Backend admin | RBAC, validation, transaction và orchestration external systems | Tin `role`, `category_id`, price hoặc status do client gửi mà không kiểm tra |

## 5. Role và phân quyền

### 5.1 Role giai đoạn đầu

```text
anonymous  -> không phải record role; chỉ dùng public endpoints
customer   -> user đăng ký bình thường
admin      -> user được cấp quyền bằng script/operation có kiểm soát
```

Không thêm `seller`, `staff`, `super_admin` khi chưa có yêu cầu multi-vendor hoặc phân cấp nhân sự.

### 5.2 Permission matrix

| Nghiệp vụ | Anonymous | Customer | Admin |
| --- | ---: | ---: | ---: |
| Xem catalog published | Có | Có | Có |
| Visual search bằng ảnh | Có | Có | Có |
| Cart/order của chính mình | Không | Có | Có nếu dùng storefront |
| Xem admin product list gồm draft/archived | Không | Không | Có |
| Chạy classifier category suggestion | Không | Không | Có |
| Tạo/sửa product, variant, ảnh | Không | Không | Có |
| Publish/archive/restore product | Không | Không | Có |
| Cấp role admin | Không | Không | Không qua public API |
| Hard-delete catalog | Không | Không | Chỉ operation riêng nếu được phê duyệt |

### 5.3 Quy tắc bảo mật

- Public registration luôn tạo `role='customer'`; request không có field role.
- Không tin role gửi từ frontend hoặc claim cũ trong token.
- `require_current_user` tiếp tục tải user active từ DB.
- `require_admin` kiểm tra `user.role == 'admin'`, trả `403 FORBIDDEN` nếu không đủ quyền.
- `401` dành cho thiếu/hết hạn token; `403` dành cho đã đăng nhập nhưng sai role.
- Bootstrap admin bằng CLI có `--apply`, audit email/operator và không in password/hash.
- Không có endpoint public kiểu `PATCH /users/{id}/role` trong phase này.
- Frontend route guard chỉ là UX; backend RBAC mới là lớp bảo mật authoritative.

## 6. Giai đoạn 1 — Trả customer search về RAG thuần

Đây là giai đoạn phải hoàn tất trước khi xây admin.

### 6.1 Customer flow mới

```text
idle
  -> image-selected
  -> searching
  -> success | empty | error
```

### 6.2 Frontend cần thay đổi

- Xóa model dropdown khỏi `/visual-search`.
- Xóa classify button, toast prediction và top-5 classification panel khỏi customer page.
- Xóa category selector khỏi visual search; category filter của catalog `/products` vẫn giữ nguyên.
- Không gọi:
  - `GET /image-search/classifiers`
  - `POST /image-search/classify`
  - `GET /categories` chỉ để phục vụ visual search.
- `searchByImage` chỉ gửi `image` và `limit=50`.
- Đổi step indicator thành `Chọn ảnh → Tìm kiếm → Kết quả`.
- Đổi empty/help copy để không nhắc “bỏ bớt danh mục”.
- Giữ preview, replace/remove, abort stale request, retrieval timing và phân trang 20/50.
- Di chuyển component classification có thể tái sử dụng sang feature admin; không để admin import ngược component từ customer feature.

### 6.3 Backend cần thay đổi

- Contract cuối của `POST /api/v1/image-search/search`:

```text
multipart/form-data
  image: required binary
  limit: optional integer, max 50
```

- Không đọc hoặc truyền `category_ids` vào Pinecone cho customer route.
- Giữ capability filter bên repository nếu admin/internal evaluation còn cần; public route không dùng.
- Không load classifier khi customer chỉ visual search.
- Giữ `retrieval_time_ms` và top-k 50 hiện tại.
- Viết regression test xác nhận searcher nhận `category_ids=()`.
- Cập nhật OpenAPI, README và frontend types.

### 6.4 Cleanup source sau khi admin chưa sẵn sàng

- Không xóa `backend/app/classifiers/` hoặc model artifact.
- Có thể giữ classification route tạm thời trong một release nhưng frontend không gọi.
- Khi RBAC admin hoàn thành, chuyển endpoint và xóa/deprecate public classification route.
- Không giữ CSS/component customer không còn dùng nếu chúng không được chuyển sang admin.

### 6.5 Acceptance criteria

- Khách hàng chỉ cần chọn một ảnh và bấm tìm kiếm.
- Request customer không chứa category/model ID.
- Không có classification latency trong customer journey.
- Kết quả vẫn giữ Pinecone ranking và hydrate published product.
- Test cũ liên quan customer classifier được thay bằng test RAG thuần.

### 6.6 Trạng thái triển khai Phase 1 — 12/11/2026

Đã hoàn tất trong source hiện tại:

- Customer `/visual-search` chỉ còn chọn ảnh, tìm kiếm và xem kết quả; không tải model, classification hoặc category.
- Frontend multipart request chỉ gửi `image` và `limit=50`.
- Public backend search không đọc `category_ids` và luôn gọi retrieval với `category_ids=()`; field cũ nếu client gửi lên bị bỏ qua.
- OpenAPI của customer search chỉ công bố `image` và `limit`.
- Giữ retrieval timing, top-k 50, phân trang client 20 sản phẩm/trang và abort stale request.
- Component dropdown/kết quả classifier được chuyển sang `features/admin/classification` để dành cho Phase 4; customer feature không import ngược.
- Classifier backend, manifest và checkpoint vẫn được giữ nguyên cho giai đoạn admin.
- README và hai file AGENTS đã được đồng bộ với kiến trúc mới.

Kết quả xác minh tại thời điểm triển khai:

- Backend: `68 passed, 3 skipped` (ba integration test live cần external services).
- Frontend: `20 passed`; ESLint, TypeScript và Next.js production build đều thành công.

## 7. Giai đoạn 2 — Database migration và RBAC admin

### 7.1 Migration `public.users`

Thêm cột:

```sql
ALTER TABLE public.users
ADD COLUMN role TEXT NOT NULL DEFAULT 'customer';

ALTER TABLE public.users
ADD CONSTRAINT users_role_allowed
CHECK (role IN ('customer', 'admin'));

CREATE INDEX IF NOT EXISTS users_role_active_idx
ON public.users (role, is_active);
```

Yêu cầu migration:

- Existing users được backfill thành `customer`.
- Chạy idempotent và validate schema sau apply.
- Có dry-run trước `--apply` theo convention hiện tại.
- Không drop/recreate `users` hoặc mất password hash.
- Có script bootstrap/promote admin bằng email sau migration.

Ví dụ operation mong muốn:

```powershell
python -m scripts.manage_user_role --email admin@example.com --role admin
python -m scripts.manage_user_role --email admin@example.com --role admin --apply
```

### 7.2 Thay đổi auth domain

- `UserRecord`: thêm `role` typed literal/enum.
- `UserResponse`: trả `role` để frontend điều hướng đúng.
- `PostgresUserRepository`: select/return role.
- `create`: không nhận role từ register service, luôn dùng DB default customer.
- `AuthService`: không cho public caller cấp role.
- `require_admin`: dependency dùng lại `require_current_user`.
- `GET /auth/me`, login và register trả role.
- Có unit/API tests cho 401/403/admin/customer.

### 7.3 JWT và session

Khuyến nghị MVP:

- Giữ JWT `sub` hiện tại.
- Role không cần là claim authoritative vì mỗi protected request đã đọc DB.
- Việc hạ quyền/deactivate có hiệu lực ngay ở request kế tiếp.
- Frontend tiếp tục giữ bearer token trong memory, không đưa vào `localStorage`.

Hardening trước production:

- Đánh giá HttpOnly SameSite cookie hoặc BFF session để reload admin page không mất phiên.
- Nếu dùng cookie cho mutation, thiết kế CSRF protection và CORS credentials rõ ràng.
- Không mở rộng auth persistence trong cùng PR với RBAC nếu chưa có test bảo mật phù hợp.

### 7.4 Trạng thái triển khai Phase 2 — 12/11/2026

Đã hoàn tất trong source và database đang cấu hình:

- `public.users.role` đã được thêm/backfill với default `customer`, NOT NULL,
  constraint `customer | admin` và index `(role, is_active)`.
- `UserRecord`, auth response và frontend auth types/parser đã có role typed.
- Public register cấm field role và chỉ tạo customer qua database default.
- JWT tiếp tục chỉ dùng `sub`; protected request đọc role authoritative từ DB.
- Dependency `require_admin` trả 401 khi chưa xác thực, 403 cho customer và cho phép admin active.
- Script `manage_user_role` có dry-run mặc định, chỉ thay role của existing user theo email.
- Migration và role operation có regression tests; README/runbook đã được cập nhật.

Chưa promote tài khoản admin đầu tiên vì cần chủ dự án xác nhận email existing user.

## 8. Giai đoạn 3 — Backend Admin Catalog

### 8.1 Module đề xuất

```text
backend/app/
├── api/routes/
│   ├── admin_classification.py
│   └── admin_products.py
├── schemas/
│   ├── admin_classification.py
│   └── admin_catalog.py
├── services/
│   ├── admin_catalog.py
│   ├── catalog_indexing.py
│   └── image_classification.py       # tái sử dụng
├── repositories/
│   ├── admin_products.py
│   ├── products.py                   # public read-only giữ riêng
│   └── pinecone.py
└── classifiers/                      # tái sử dụng registry/adapters
```

Không ép tách file nếu implementation nhỏ; boundary admin/public phải rõ hơn số lượng file.

### 8.2 Classification API mới

| Method | Endpoint | Permission | Mục đích |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/classifiers` | admin | Model/version/capability |
| `POST` | `/api/v1/admin/classification/predict` | admin | Nhận ảnh và trả top-k category |

Response giữ nguyên nguyên tắc hiện tại:

```json
{
  "model": { "id": "alexnet", "display_name": "AlexNet", "version": "1.0.0" },
  "predictions": [
    {
      "rank": 1,
      "category_id": "02",
      "label": "Áo Thun / Áo Phông",
      "logit": 8.4,
      "probability": 0.87
    }
  ],
  "suggested_category_id": "02",
  "timing": {
    "preprocess_ms": 2,
    "inference_ms": 30,
    "postprocess_ms": 1,
    "total_ms": 33
  }
}
```

Quy tắc:

- Softmax tính trên đủ 42 lớp rồi mới lấy top-k.
- Admin UI hiển thị probability; raw logit chỉ dùng diagnostic nếu cần.
- Top-1 được highlight, không tự lưu category nếu admin chưa xác nhận.
- Model unavailable trả `503 MODEL_NOT_AVAILABLE`.
- Endpoint có upload size/pixel/MIME validation và rate/concurrency control.
- Không lưu ảnh classification tạm nếu chưa có yêu cầu audit rõ ràng.

### 8.3 Admin product API đề xuất

| Method | Endpoint | Chức năng |
| --- | --- | --- |
| `GET` | `/api/v1/admin/products` | List draft/published/archived, filter, sort, pagination |
| `GET` | `/api/v1/admin/products/{id}` | Detail gồm variants, images, index status |
| `POST` | `/api/v1/admin/products` | Tạo product draft |
| `PATCH` | `/api/v1/admin/products/{id}` | Sửa metadata/category/status-safe fields |
| `DELETE` | `/api/v1/admin/products/{id}` | Soft-delete bằng archive |
| `POST` | `/api/v1/admin/products/{id}/restore` | Khôi phục archived về draft nếu cần |
| `POST` | `/api/v1/admin/products/{id}/publish` | Validate và publish/idempotent re-publish |
| `POST` | `/api/v1/admin/products/{id}/images` | Upload ảnh vào Storage và tạo image record |
| `PATCH` | `/api/v1/admin/products/{id}/images/{image_id}` | Alt/order/primary |
| `DELETE` | `/api/v1/admin/products/{id}/images/{image_id}` | Xóa ảnh an toàn, de-index vector tương ứng |
| `POST` | `/api/v1/admin/products/{id}/variants` | Thêm variant |
| `PATCH` | `/api/v1/admin/products/{id}/variants/{variant_id}` | Sửa SKU/price/stock/active |
| `DELETE` | `/api/v1/admin/products/{id}/variants/{variant_id}` | Vô hiệu hóa/xóa variant khi hợp lệ |

Tất cả endpoint trên bắt buộc `require_admin`.

### 8.4 Product lifecycle

```text
draft
  -> admin bổ sung category, image, variant
  -> validate publish
  -> indexing
  -> published
  -> archive/delete
  -> archived
  -> optional restore
  -> draft
```

Điều kiện publish tối thiểu:

- Có name, slug hợp lệ và category canonical active.
- Có ít nhất một variant active.
- Variant có price/inventory hợp lệ và SKU unique.
- Có đúng một primary image.
- Ảnh đã upload Storage thành công.
- CLIP embedding/upsert Pinecone thành công hoặc workflow publish giữ trạng thái pending có retry rõ ràng.
- Product không xuất hiện public trước khi toàn bộ invariant published được đáp ứng.

### 8.5 Delete semantics

`DELETE /admin/products/{id}` không hard-delete mặc định:

1. Chuyển status sang `archived`.
2. Public catalog và hydrate query không còn trả sản phẩm.
3. Xóa/deactivate toàn bộ Pinecone vectors của product.
4. Giữ DB record, images và audit trail để phục hồi/đối soát.
5. Storage cleanup lâu dài là operation riêng có retention policy.

Hard-delete chỉ dành cho dữ liệu test hoặc operation được phê duyệt, không phải nút mặc định trên UI.

## 9. Database catalog cần bổ sung

### 9.1 `products`

Đề xuất thêm:

```text
created_by UUID NULL REFERENCES users(id)
updated_by UUID NULL REFERENCES users(id)
version INTEGER NOT NULL DEFAULT 1
```

- Existing seed products có thể giữ `created_by=NULL` và được xem là system-imported.
- `version` hoặc `updated_at` được dùng optimistic concurrency để tránh hai admin ghi đè nhau.
- Giữ category NOT NULL trong MVP vì admin phải xác nhận category trước khi tạo draft.

### 9.2 `product_images`

Hiện `source_path` phù hợp dataset ingestion nhưng không phù hợp hoàn toàn với ảnh upload từ admin.

Đề xuất:

```text
source_path TEXT NULL
index_status TEXT NOT NULL DEFAULT 'pending'
indexed_at TIMESTAMPTZ NULL
index_error TEXT NULL
updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
```

Constraint `index_status`:

```text
pending | indexing | indexed | failed | removed
```

`pinecone_vector_id` vẫn có thể sinh deterministic trước khi upsert để không cần nullable.

### 9.3 Audit và classification feedback

P1 khuyến nghị thêm `admin_audit_events`:

```text
id, actor_user_id, action, resource_type, resource_id,
before_data JSONB, after_data JSONB, request_id, created_at
```

P2 khuyến nghị thêm `classification_runs` để đánh giá model:

```text
id, actor_user_id, product_id, model_id, model_version,
predictions JSONB, selected_category_id, image_sha256, created_at
```

Không lưu raw image trong bảng audit. Có thể đo:

- Tỷ lệ admin chấp nhận top-1.
- Tỷ lệ category cuối nằm trong top-3/top-5.
- Override rate theo category/model version.

### 9.4 Outbox/index jobs

PostgreSQL transaction không thể bao trùm Storage và Pinecone. Để tránh trạng thái nửa thành công, P1 nên có bảng job/outbox:

```text
catalog_sync_jobs
  id, product_id, image_id, operation,
  status, attempts, last_error, next_attempt_at,
  created_at, updated_at
```

Operation ví dụ:

```text
upsert_vector | update_metadata | delete_vector | delete_storage_object
```

MVP có thể chạy đồng bộ nhưng failure phải giữ product ở draft và có retry endpoint. Không được publish DB trước rồi bỏ qua lỗi Pinecone.

## 10. Nghiệp vụ tạo sản phẩm bằng classifier

### 10.1 Luồng admin đề xuất

```text
1. Admin mở “Thêm sản phẩm”.
2. Chọn ảnh chính.
3. Chọn model khả dụng hoặc model mặc định.
4. Frontend gọi admin classification API.
5. Backend trả top-5 Softmax.
6. UI hiển thị top-5 và toàn bộ canonical category để override.
7. Admin xác nhận đúng một category.
8. Admin nhập name, brand, description, variants, price, inventory và images.
9. Lưu draft.
10. Backend upload ảnh, tạo records và index status.
11. Admin preview/validate draft.
12. Publish; backend đảm bảo Pinecone/Storage/catalog consistency.
```

### 10.2 Human-in-the-loop rules

- Một product có đúng một `category_id` authoritative ở schema hiện tại.
- Top-1 chỉ preselect trên UI, không tự submit âm thầm.
- Admin có thể chọn top-2..top-5 hoặc category ngoài top-5.
- UI ghi rõ Softmax là độ tin cậy model, không phải product similarity.
- Confidence thấp không chặn tạo draft; có thể cảnh báo và yêu cầu xác nhận.
- Khi thay ảnh hoặc model, prediction cũ phải reset/abort để không ghi đè state mới.
- Category thay đổi trên product published phải cập nhật metadata Pinecone.

### 10.3 Upload ảnh

- Client validation để phản hồi nhanh, backend validation là authoritative.
- Browser không gọi Supabase trực tiếp bằng server secret.
- Backend tạo storage path không phụ thuộc filename không an toàn.
- Không log raw image, filename đầy đủ hoặc image bytes.
- Primary image bắt buộc trước publish.
- Xóa primary image phải chọn primary mới hoặc từ chối thao tác.

## 11. Pinecone và Storage consistency

### 11.1 Khi publish

1. Đọc product/image authoritative từ PostgreSQL.
2. Kiểm tra status/invariants.
3. Sinh CLIP embedding cho từng image cần index.
4. Upsert Pinecone fields:

```text
image_vector
product_id
image_id
category_id
image_path/storage_path
```

5. Verify accepted vector/document ID.
6. Cập nhật `index_status=indexed`.
7. Chỉ sau đó chuyển product thành published, hoặc dùng outbox/state machine có retry rõ ràng.

### 11.2 Khi sửa

| Thay đổi | PostgreSQL | Storage | Pinecone |
| --- | --- | --- | --- |
| Name/description/brand | Update | Không | Không cần nếu metadata không chứa field này |
| Price/inventory | Update variant | Không | Không, dữ liệu authoritative hydrate từ DB |
| Category | Update | Không | Update metadata tất cả vectors của product |
| Thay ảnh | Update image record | Upload/delete theo policy | Re-embed/upsert/delete vector cũ |
| Archive product | Update status | Giữ theo retention | Delete/deactivate vectors |
| Restore | Về draft | Kiểm tra object tồn tại | Re-index khi publish lại |

### 11.3 Idempotency

- Vector ID deterministic theo image ID.
- Upload path deterministic hoặc unique UUID.
- Publish/retry không tạo vector trùng.
- Delete vector không lỗi nếu vector đã không tồn tại.
- Job retry có max attempts/backoff và lỗi cuối hiển thị cho admin.

## 12. Giai đoạn 4 — Frontend Admin

### 12.1 Route structure

```text
frontend/src/app/admin/
├── page.tsx                    # dashboard tối thiểu
├── products/
│   ├── page.tsx               # list/filter/pagination
│   ├── new/page.tsx            # create workflow
│   └── [id]/page.tsx           # detail/edit
└── forbidden/page.tsx          # hoặc reusable access state
```

Feature boundary:

```text
frontend/src/features/admin/
├── auth/
├── products/
├── classification/
└── layout/
```

Không để admin page tái sử dụng bằng cách import trực tiếp stateful customer visual-search view. Chỉ tái sử dụng primitive hoặc tách component thuần.

### 12.2 Admin layout

- Header/sidebar riêng, hiển thị email và role.
- Navigation tối thiểu: Tổng quan, Sản phẩm, Thêm sản phẩm, Về storefront.
- `AdminGuard` xử lý:
  - chưa login → login/return URL;
  - role customer → forbidden;
  - role admin → render;
  - token expired → clear session và yêu cầu login.
- Không coi hidden nav là authorization.

### 12.3 Product list

- Table desktop và card/list mobile.
- Columns: ảnh chính, tên, category, trạng thái, giá từ, tồn kho tổng, index status, updated_at.
- Filters: keyword, category, status, index status.
- Pagination server-side; không tải toàn catalog để lọc client.
- Actions: xem/sửa, publish, archive, restore tùy state.
- Confirm dialog cho archive/delete; hiển thị hậu quả de-index.
- Empty/error/loading state riêng và có retry phù hợp.

### 12.4 Create/edit form

Các section:

1. Ảnh sản phẩm.
2. Gợi ý category bằng model.
3. Category xác nhận.
4. Thông tin cơ bản.
5. Variants/SKU/price/inventory.
6. Preview và trạng thái publish/index.

Component đề xuất:

```text
AdminProductForm
AdminImageUploader
AdminClassifierPicker
AdminCategorySuggestions
AdminCategorySelect
VariantEditor
ProductStatusBadge
IndexStatusPanel
ArchiveProductDialog
UnsavedChangesGuard
```

### 12.5 State machine form

```text
idle
  -> image-selected
  -> classifying
  -> category-review
  -> editing
  -> saving-draft
  -> draft-saved
  -> uploading/indexing
  -> ready-to-publish
  -> publishing
  -> published | error
```

- Abort classify request khi đổi ảnh/model.
- Disable duplicate save/publish.
- Giữ dữ liệu form sau lỗi recoverable.
- Có cảnh báo unsaved changes khi rời trang.
- Backend field errors map đúng control.
- Không optimistic publish nếu backend chưa xác nhận.

### 12.6 Typed API adapters

```text
src/lib/api/admin-auth.api.ts
src/lib/api/admin-classification.api.ts
src/lib/api/admin-products.api.ts
src/types/admin-catalog.ts
```

- Validate response runtime như các adapter hiện tại.
- Gửi bearer token từ session hiện tại.
- Không để component tự dựng URL/fetch rải rác.
- `401`, `403`, `409`, `422`, `503` có UI recovery khác nhau.

### 12.7 Accessibility và responsive

- Dropdown model/category keyboard-complete.
- Progress bar có accessible name và hiển thị percentage text.
- Table có header semantic; mobile không buộc scroll ngang quá mức.
- Dialog giữ focus, Escape/cancel rõ ràng.
- Touch target khoảng 44px.
- Không biểu diễn trạng thái chỉ bằng màu.
- Tôn trọng reduced motion.

## 13. API error contract admin

Tiếp tục dùng error envelope hiện tại:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "field_errors": {
    "variants.0.price": "Must be greater than or equal to zero"
  },
  "request_id": "uuid"
}
```

Error codes cần có:

```text
UNAUTHORIZED
FORBIDDEN
PRODUCT_NOT_FOUND
PRODUCT_VERSION_CONFLICT
PRODUCT_NOT_PUBLISHABLE
SKU_CONFLICT
IMAGE_INVALID
IMAGE_STORAGE_FAILED
MODEL_NOT_AVAILABLE
CLASSIFICATION_FAILED
VECTOR_INDEX_FAILED
SERVICE_UNAVAILABLE
```

Không trả stack trace, storage path nội bộ nhạy cảm hoặc provider credential.

## 14. Test plan

### 14.1 Customer regression

- Visual search request không chứa classifier/category.
- CLIP/Pinecone search chạy với category filter rỗng.
- Upload validation, abort stale search, empty/error/success vẫn hoạt động.
- Timing và pagination 50/20 không regression.
- Customer page không tải classifier capability/model code ngoài phần cần thiết.

### 14.2 RBAC backend

- Existing user migration thành customer.
- Register không thể gửi/tự chọn role admin.
- Anonymous admin API → 401.
- Customer admin API → 403.
- Inactive admin → 401.
- Admin active → được phép.
- Role change trong DB có hiệu lực ở request tiếp theo.

### 14.3 Admin classification

- Artifact/capability contract đúng.
- Top-k theo Softmax giảm dần, category ID giữ leading zero.
- Invalid image/model/top-k trả lỗi đúng.
- Model lazy-load/reuse, concurrent request có giới hạn.
- Prediction không tự ghi category khi admin chưa save.

### 14.4 Product CRUD

- Create draft valid/invalid.
- SKU/slug conflict.
- Update với version stale → 409.
- Publish thiếu category/variant/image → reject.
- Publish thành công → public catalog và Pinecone cùng thấy sản phẩm.
- Category update → Pinecone metadata update.
- Archive → public không thấy và vector bị remove.
- Image deletion/primary invariant.
- Storage/Pinecone failure giữ trạng thái recoverable và retry idempotent.

### 14.5 Frontend admin

- Route guard theo role.
- Admin list pagination/filter round-trip.
- Model unavailable disabled nhưng hiển thị rõ.
- Đổi ảnh/model không để stale prediction.
- Admin override top-1 và chọn category ngoài top-5.
- Form giữ input sau lỗi.
- Confirm archive và unsaved changes.
- Keyboard/mobile/large Vietnamese label/zoom.
- Production build không kéo secret vào client bundle.

## 15. Observability và metrics

### 15.1 Customer retrieval

- `embedding_ms`
- `pinecone_search_ms`
- `product_hydration_ms`
- `retrieval_total_ms`
- match count và hydrated product count
- p50/p95 không filter sau migration

### 15.2 Admin classification

- model/version/device
- preprocess/inference/postprocess/total timing
- success/error rate
- top-1/top-5 acceptance rate nếu có classification audit

### 15.3 Admin catalog

- draft created/published/archived count
- publish failure reason
- pending/failed index jobs
- Storage/Pinecone retry count
- request ID và actor ID trong audit log, không log image bytes/token

## 16. Rollout plan theo thứ tự bắt buộc

### Phase 0 — Baseline và contract freeze

- Ghi lại customer latency/relevance baseline có/không category filter.
- Chốt contract customer mới và admin role model.
- Chốt archive semantics, publish invariant và session strategy MVP.
- Cập nhật test fixtures trước khi xóa customer classifier UI.

**Gate:** có baseline, acceptance criteria và rollback plan.

### Phase 1 — Customer RAG thuần

- Frontend bỏ classification/category khỏi visual search.
- Backend public search không dùng category filter.
- Giữ classifier service để chuẩn bị admin.
- Test/build/documentation.

**Gate:** customer chỉ ảnh → search; latency không còn classification overhead.

### Phase 2 — RBAC và schema migration

- Add `users.role`, backfill customer.
- Cập nhật repository/schema/auth responses.
- Thêm `require_admin`.
- Thêm bootstrap admin script.
- Migration catalog fields cần thiết.

**Gate:** test 401/403/admin pass; không có public role escalation.

### Phase 3 — Admin backend

- Chuyển classification API sang admin namespace.
- Admin product CRUD/lifecycle.
- Storage upload orchestration.
- Pinecone index/update/delete lifecycle.
- Audit/index status và retry theo scope đã chọn.

**Gate:** API test end-to-end draft → classify → publish → archive pass.

#### Trạng thái triển khai Phase 3 — 12/11/2026

Đã hoàn tất backend trong source và migration đã được áp dụng lên database đang
cấu hình:

- Classification đã chuyển sang `GET /api/v1/admin/classifiers` và `POST
  /api/v1/admin/classification/predict`; route public cũ đã gỡ.
- Toàn bộ admin endpoint dùng `require_admin`; anonymous nhận 401 và customer
  nhận 403 qua auth dependency authoritative.
- Đã có list/detail/create/update product, optimistic version conflict, quản lý
  variant, upload/cập nhật/xóa mềm image, publish/archive/restore.
- Publish kiểm tra active variant và đúng một primary image; chỉ chuyển sang
  `published` sau khi CLIP embedding và Pinecone upsert thành công.
- Index lỗi giữ product ở `draft`, đánh dấu image `failed`, ghi
  `catalog_sync_jobs`; gọi lại publish là retry đồng bộ/idempotent của MVP.
- Archive xóa vector dẫn xuất nhưng giữ DB/Storage/audit để phục hồi; restore trả
  sản phẩm về draft và publish lại sẽ re-index.
- Đã có audit actor/request ID, image index status, Storage upload/download,
  Pinecone update/delete và giới hạn concurrency inference.
- Migration `migrate_admin_catalog_schema` là additive/idempotent và đã chạy
  thành công. Regression suite backend hiện đạt 94 passed, 3 skipped.

Phần chưa làm có chủ đích thuộc Phase 4/5: giao diện admin, worker retry nền với
backoff/max-attempt, session HttpOnly và deployment-level rate limiting.

### Phase 4 — Admin frontend

- Admin layout/guard.
- Product list.
- Create/edit form.
- Classification suggestions và category confirmation.
- Image/variant management.
- Publish/archive/recovery states.

**Gate:** admin hoàn thành product lifecycle bằng UI; customer không truy cập được.

#### Trạng thái triển khai Phase 4 — 13/11/2026

- Đã có role-aware `/admin` guard và điều hướng admin sau login.
- Đã có list/filter catalog, create/edit draft, optimistic version update.
- Đã tích hợp protected classifier top-5 và xác nhận category thủ công.
- Đã có quản lý variant, upload/chọn primary/xóa ảnh và trạng thái index.
- Đã có publish/archive/restore cùng loading/error/recovery feedback.
- Typed API adapters kiểm tra runtime response; customer visual search không đổi.
- Frontend test, ESLint, TypeScript và production build đã pass. Browser preview
  chưa chạy được trong môi trường agent do Next dev server bị `spawn EPERM`.

### Phase 5 — Reliability và evaluation

- Outbox/background retry nếu MVP đang synchronous.
- Session persistence/HttpOnly cookie nếu chuẩn bị production.
- Classification acceptance metrics.
- Retrieval p50/p95 và quality benchmark.
- Runbook restore/reindex/retry.

## 17. Backlog phân công

| ID | Ưu tiên | Owner | Công việc | Phụ thuộc |
| --- | --- | --- | --- | --- |
| CUS-01 | P0 | Frontend | Gỡ classifier/category khỏi visual search | Không |
| CUS-02 | P0 | Backend | Bỏ category filter khỏi public image search | Không |
| CUS-03 | P0 | FE+BE | Contract/regression/timing tests | CUS-01, CUS-02 |
| DB-01 | P0 | Backend | Migration `users.role` và backfill | Không |
| AUTH-01 | P0 | Backend | User role schema/repository/response | DB-01 |
| AUTH-02 | P0 | Backend | `require_admin` + 401/403 tests | AUTH-01 |
| OPS-01 | P0 | Backend | Bootstrap/manage admin role script | DB-01 |
| ADM-BE-01 | P0 | Backend | Admin classification routes | AUTH-02 |
| ADM-BE-02 | P0 | Backend | Admin product list/detail | AUTH-02 |
| ADM-BE-03 | P0 | Backend | Create/update draft + variants | ADM-BE-02 |
| ADM-BE-04 | P0 | Backend | Image upload/primary image rules | ADM-BE-03 |
| ADM-BE-05 | P0 | Backend | Publish/archive lifecycle | ADM-BE-04 |
| IDX-01 | P0 | Backend | Pinecone upsert/update/delete lifecycle | ADM-BE-05 |
| ADM-FE-01 | P1 | Frontend | Role-aware auth types/guard/layout | AUTH-02 |
| ADM-FE-02 | P1 | Frontend | Admin product list | ADM-BE-02 |
| ADM-FE-03 | P1 | Frontend | Create/edit form và variants | ADM-BE-03 |
| ADM-FE-04 | P1 | Frontend | Admin classifier/category suggestions | ADM-BE-01 |
| ADM-FE-05 | P1 | Frontend | Image management + publish/archive UX | ADM-BE-04, ADM-BE-05 |
| AUD-01 | P1 | Backend | Audit events | AUTH-02 |
| REL-01 | P1 | Backend | Index job/outbox/retry | IDX-01 |
| EVAL-01 | P2 | FE+BE | Classification acceptance metrics | ADM-FE-04, AUD-01 |
| SEC-01 | P2 | FE+BE | Persistent secure admin session | AUTH-02 |

## 18. Vai trò và kỳ vọng theo team

### 18.1 Backend

Backend chịu trách nhiệm authoritative cho:

- Authentication, role và permission.
- Canonical category validation.
- Product/variant/image invariants.
- Status transition draft/published/archived.
- Storage path/object lifecycle.
- CLIP embedding và Pinecone consistency.
- Classifier preprocessing/model mapping/top-k.
- Transaction, idempotency, conflict và retry.
- Audit/error/request ID.
- OpenAPI và migration scripts.

Backend không được dựa vào việc frontend ẩn nút để bảo vệ admin API.

### 18.2 Frontend

Frontend chịu trách nhiệm:

- Customer flow đơn giản, không còn classifier dependency.
- Admin route UX theo role nhưng không thay backend authorization.
- Typed API adapters và runtime response validation.
- Form state, stale request cancellation và unsaved changes.
- Hiển thị Softmax đúng nghĩa, category override rõ ràng.
- Accessible/responsive list, form, dropdown, dialog và error states.
- Không expose provider secret/model path.
- Không optimistic publish/archive khi backend chưa xác nhận.

### 18.3 Admin vận hành

Admin chịu trách nhiệm:

- Kiểm tra top-k và xác nhận category cuối.
- Nhập metadata, variant, price, inventory và ảnh hợp lệ.
- Preview draft trước publish.
- Xử lý cảnh báo index/storage failure và retry theo runbook.
- Không coi top-1 classifier là kết luận bắt buộc.

## 19. Cập nhật tài liệu bắt buộc khi triển khai

Hai file AGENTS hiện vẫn mô tả classifier thuộc customer retrieval flow. Khi Phase 1/2 bắt đầu phải cập nhật:

### `frontend/AGENTS.md`

- Product goals: customer image search không classification.
- Visual search state: bỏ `classifying/choosing-categories` khỏi customer flow.
- Thêm admin catalog journey và RBAC expectations.
- Testing: chuyển category suggestion tests sang admin feature.

### `backend/Agents.md`

- Business requirement 3.1: classification là admin catalog assistance.
- Requirement 3.2: customer retrieval không phụ thuộc predicted category.
- Performance section: category filter không được giả định nhanh hơn.
- Thêm admin authorization/catalog lifecycle/external consistency rules.

Ngoài ra cập nhật:

- Backend/frontend README.
- OpenAPI examples.
- `.env.example` nếu có config admin/classifier concurrency.
- Docker deployment/runbook cho artifact và admin bootstrap.

## 20. Definition of Done

Module chuyển đổi hoàn tất khi:

- Customer chỉ upload ảnh và search, không thấy/call classifier/category filter.
- Public visual search không truyền metadata filter category.
- `users.role` migration/backfill thành công và public registration không thể tạo admin.
- Admin endpoint trả đúng 401/403 và chỉ admin active truy cập được.
- Admin xem được cả draft/published/archived với pagination.
- Admin tạo/sửa sản phẩm, variants và images bằng dữ liệu authoritative.
- Classifier top-k chỉ là gợi ý; category lưu là lựa chọn admin xác nhận.
- Publish chỉ thành công khi invariants, Storage và Pinecone đáp ứng contract.
- Archive làm sản phẩm biến mất khỏi public catalog và vector search.
- External failure recoverable, idempotent và có trạng thái/diagnostic an toàn.
- Customer regression, RBAC, classification, CRUD, indexing và frontend tests pass.
- Frontend lint/typecheck/build pass.
- Migration/runbook/README/AGENTS/OpenAPI được cập nhật.
- Không có secret, raw upload hoặc model checkpoint lớn bị commit nhầm.

## 21. Các quyết định cần chốt trước khi code Phase 2–4

1. Email user hiện có nào sẽ được bootstrap thành admin đầu tiên.
2. MVP giữ bearer token in-memory hay triển khai HttpOnly session ngay.
3. Publish chạy indexing đồng bộ hay dùng outbox/background worker từ đầu.
4. Ảnh archived giữ bao lâu trước khi Storage cleanup.
5. Có cần restore archived product trên UI hay chỉ qua operation script.
6. Có lưu `classification_runs` để đo acceptance/override ngay ở MVP không.
7. Một product có nhiều image thì index tất cả hay chỉ primary image trong phase đầu.
8. Khi confidence top-1 thấp có cần threshold cảnh báo hay chỉ luôn hiển thị top-5.

Khuyến nghị MVP: một admin role, bearer memory hiện tại, index primary image đồng bộ, archive không hard-delete, top-5 không threshold chặn, và bổ sung outbox/session persistence ở phase hardening.

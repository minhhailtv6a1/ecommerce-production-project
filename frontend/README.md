# Lumi Market — Image Search Frontend

Frontend Next.js dành cho việc kiểm thử cục bộ các luồng backend đã hoàn thành: danh mục, catalog, chi tiết sản phẩm, tìm kiếm bằng ảnh và xác thực. Đây là integration-test MVP, không phải website thương mại điện tử production.

## Công nghệ và lựa chọn chính

- Next.js 16.2.6, App Router và React 19.2.7.
- TypeScript strict.
- CSS thuần với design tokens; không dùng UI kit, Tailwind hoặc state library.
- API adapter typed, kiểm tra phản hồi runtime tại boundary.
- Node.js test runner và React server rendering cho unit/component tests.
- Thẻ `<img>` cho signed Supabase URL vì hostname thay đổi theo môi trường; URL không được biến đổi hoặc lưu lâu dài.
- Access token chỉ tồn tại trong React memory. Refresh trang sẽ kết thúc phiên local.

Node.js tối thiểu: **20.9**. Dự án được kiểm tra với Node.js 22.19.0 và npm 10.9.3.

## Cài đặt

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
```

`.env.local` cần có:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_SHOW_TEST_CATEGORIES=true
```

Đây là URL công khai của API, không phải secret. Không thêm Pinecone key, Supabase service key, database password hoặc JWT secret vào frontend.

`NEXT_PUBLIC_SHOW_TEST_CATEGORIES` là cờ giao diện tạm thời cho giai đoạn kiểm thử truy vấn category. Giữ `true` khi scale test; chuyển thành `false` rồi build lại để ẩn danh mục khỏi trang chủ, product card, product detail, catalog filter và visual-search filter mà không sửa source.

## Chạy local

Backend phải được khởi động trước:

```powershell
cd backend
.\myenv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Backend mặc định ở `http://127.0.0.1:8000`, tài liệu OpenAPI ở `http://127.0.0.1:8000/docs`. CORS backend hiện cho phép origin `http://localhost:3000`.

Sau đó chạy frontend:

```powershell
cd frontend
npm run dev
```

Mở `http://localhost:3000`.

> Các script trong `package.json` gọi binary qua `node ./node_modules/...` thay vì dựa vào `.bin`. Cách này tránh lỗi shell khi đường dẫn workspace Windows chứa ký tự `&`.

## Lệnh kiểm tra

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm start
```

Test không yêu cầu backend live. Bộ test hiện bao phủ:

- Parser của error contract và lỗi mạng.
- Định dạng giá VND.
- Query string với nhiều `category_ids` và leading zero.
- Multipart `FormData` cho visual search.
- MIME và giới hạn 10 MiB của ảnh upload.
- Product card render từ dữ liệu backend.
- Empty state và API error state.
- Parser cart/order, khả năng checkout và nhãn trạng thái đơn hàng.

## Route frontend

| Route | Chức năng |
| --- | --- |
| `/` | Giới thiệu visual search, danh mục và sản phẩm mới từ backend |
| `/products` | Catalog, lọc đa danh mục, size, màu, brand, giá, tồn kho, sort và pagination |
| `/products/[identifier]` | Gallery, thông tin sản phẩm và các variant thật |
| `/visual-search` | Upload/preview ảnh, chọn danh mục thủ công và tìm sản phẩm tương đồng |
| `/login` | Đăng nhập và giữ token trong memory |
| `/register` | Đăng ký và giữ token trong memory |
| `/cart` | Giỏ hàng server-side, cập nhật số lượng và xóa variant |
| `/checkout` | Form giao hàng và đặt đơn COD |
| `/orders` | Lịch sử đơn hàng của user hiện tại |
| `/orders/[orderId]` | Chi tiết và trạng thái đơn hàng authoritative |

Sau khi login/register, header có nút **Kiểm tra /me** để gọi endpoint được bảo vệ. Nút **Đăng xuất** chỉ xóa token khỏi state frontend; backend không có token revocation.

## API đã tích hợp

- `GET /health`
- `GET /categories`
- `GET /products`
  - `category_ids` được gửi dưới dạng query parameter lặp.
  - Hỗ trợ `size`, `color`, `brand`, `min_price`, `max_price`, `in_stock`, `sort`, `page`, `limit`.
- `GET /products/{id-or-slug}`
- `POST /image-search/search`
  - Multipart field `image`.
  - `category_ids` là field lặp và không bắt buộc.
  - `limit` tối đa 50; UI gửi 50.
  - UI hiển thị `retrieval_time_ms`, là thời gian truy vấn RAG phía server gồm
    tạo CLIP embedding, tìm kiếm Pinecone và hydrate sản phẩm.
  - UI đo riêng tổng thời gian phản hồi bằng đồng hồ monotonic của trình duyệt,
    từ lúc submit đến khi tải và parse xong response. Số này gồm thời gian xử lý
    server, upload và network, nhưng không đại diện cho thời gian render hoàn tất.
  - Tối đa 50 kết quả được phân trang ở frontend, 20 sản phẩm mỗi trang. Chuyển
    trang không chạy lại embedding hoặc truy vấn Pinecone.
- `GET /image-search/classifiers`
  - Trả capability thực tế của AlexNet, ResNet50 và ViT.
  - Model chưa có artifact vẫn xuất hiện trên UI nhưng bị disabled với trạng thái
    “Sắp tích hợp”.
- `POST /image-search/classify`
  - Multipart fields: `image`, `model_id`, `top_k=5`.
  - UI hiển thị top 5 Softmax bằng progress bar, đưa các nhóm dự đoán lên đầu danh
    sách và tự động tích duy nhất top 1.
  - Người dùng có thể bỏ/chọn thêm category trước khi chạy vector retrieval.
  - Toast kết quả tự biến mất sau 3 giây; panel dự đoán vẫn được giữ để kiểm tra.
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET /cart`
- `POST /cart/items`
- `PATCH /cart/items/{variant_id}`
- `DELETE /cart/items/{variant_id}`
- `POST /orders`
- `GET /orders`
- `GET /orders/{order_id}`

Giỏ hàng và đơn hàng chỉ hoạt động khi có phiên đăng nhập trong memory. Product detail
cho phép chọn variant thật và số lượng trong giới hạn tồn kho. Checkout hiện chỉ hỗ trợ
COD; giá, khả dụng, tồn kho và tổng tiền được backend kiểm tra lại trong transaction.
Nếu request tạo đơn bị lỗi mạng và kết quả không xác định, UI không gửi lại tự động mà
hướng người dùng kiểm tra `/orders` để tránh tạo đơn trùng. Backend hiện chưa có
idempotency key cho checkout.

Luồng visual search là:

```text
chọn ảnh
  → không dùng model: chọn category thủ công
  → chọn model: classifying → predictions | classification-error
  → người dùng xác nhận category
  → searching → success | empty | search-error
```

Request classification/search đang chạy bị abort khi người dùng thay ảnh hoặc model.
Đổi/xóa ảnh cũng reset prediction, category selection và search result cũ. Object
URL của preview được revoke khi thay, xóa hoặc unmount.

## Error handling

Backend error contract:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "field_errors": {
    "query.limit": "Input should be greater than or equal to 1"
  },
  "request_id": "uuid"
}
```

`ApiError` giữ `code`, HTTP status, field errors và request ID. UI hiển thị thông báo an toàn và request ID phục vụ debug, không hiển thị stack trace hoặc raw HTML.

## Cấu trúc chính

```text
src/
├── app/                         # Route, metadata, global styles và boundaries
├── components/
│   ├── auth/                    # Login/register form
│   ├── categories/              # Category multi-select
│   ├── layout/                  # Header/footer
│   ├── products/                # Product card/grid
│   └── ui/                      # Error/loading states
├── domain/                      # Canonical 42-category mapping
├── features/
│   ├── auth/                    # In-memory auth provider
│   ├── home/                    # Home integration view
│   ├── products/                # Catalog/detail behavior
│   └── visual-search/           # Upload validation và workflow
├── lib/
│   ├── api/                     # HTTP client, parser và endpoint adapters
│   ├── env.ts
│   └── format.ts
└── types/                       # API/domain-facing types
```

## Giới hạn hiện tại

- Checkout chỉ hỗ trợ COD; chưa có online payment, voucher, phí vận chuyển hoặc automatic fulfilment.
- Backend chưa có idempotency key cho `POST /orders`; frontend chặn submit lặp trong phiên và xử lý lỗi mạng theo trạng thái không xác định.
- Hiện chỉ AlexNet có artifact thật; ResNet50 và ViT được hiển thị disabled cho tới
  khi backend công bố `available=true`.
- Không có refresh token, backend logout/revocation, forgot password hoặc email verification.
- Token không được persist; reload trang kết thúc phiên.
- Client validation kiểm tra MIME và kích thước encoded. Backend vẫn là nguồn kiểm tra có thẩm quyền cho nội dung ảnh và pixel limit.
- Signed image URL chỉ tồn tại trong page state bình thường và có thể hết hạn.
- Catalog, detail và visual search cần Supabase Storage/signed URL được cấu hình đúng ở backend. Khi backend không tạo được signed URL, API trả `503 SERVICE_UNAVAILABLE` và frontend hiển thị recovery state.
- UI dùng signed image URL trực tiếp qua `<img>` để không hard-code Supabase hostname trong Next config.

## Ghi chú tài liệu backend

`BE_requirements.md` mô tả một giai đoạn cũ khi catalog và visual-search REST API
chưa hoàn thành. Source route/schema hiện tại trong `backend/app/` và OpenAPI là
nguồn sự thật cho integration này. Frontend hiện dùng cả capability,
classification và visual retrieval endpoints.

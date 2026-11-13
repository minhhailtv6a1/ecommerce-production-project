# E-commerce Production Project

Dự án thương mại điện tử gồm:

- **Frontend:** Next.js, chạy tại `http://localhost:3000`.
- **Backend:** FastAPI, chạy tại `http://localhost:8000`.
- **Database và Storage:** Supabase.
- **Vector database:** Pinecone.
- **Tìm kiếm bằng ảnh:** OpenCLIP ViT-B-32.
- **Gợi ý danh mục cho admin:** mô hình phân loại AlexNet; ResNet50 và ViT chỉ sử dụng khi có artifact tương ứng.

## 1. Yêu cầu môi trường

Cài đặt các công cụ sau trước khi chạy dự án:

- Git.
- Docker Desktop có Docker Compose v2.
- Tài khoản Supabase với PostgreSQL và Storage bucket.
- Tài khoản Pinecone và một index 512 chiều dùng metric `cosine`.

Kiểm tra Docker:

```bash
docker --version
docker compose version
```

Trên Windows, cần mở Docker Desktop và chờ Docker Engine chạy hoàn tất trước khi thực hiện các lệnh Compose.

## 2. Lấy source code

```bash
git clone <repository-url>
cd ecommerce-production-project
```

Tất cả lệnh Docker Compose bên dưới được chạy tại thư mục gốc, nơi có file `docker-compose.yml`.

## 3. Tạo hai file môi trường

Dự án sử dụng hai file cấu hình riêng:

- `backend/.env`: chứa secret và cấu hình server.
- `frontend/.env`: chỉ chứa cấu hình công khai dành cho trình duyệt.

### Windows PowerShell

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

### Git Bash, macOS hoặc Linux

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Không commit hai file `.env` lên Git.

### Cấu hình `backend/.env`

Mở `backend/.env` và thay các giá trị mẫu. Những nhóm cấu hình quan trọng gồm:

| Nhóm | Biến cần kiểm tra |
| --- | --- |
| Pinecone | `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `PINECONE_NAMESPACE` |
| Cấu trúc vector | `PINECONE_VECTOR_FIELD=image_vector`, `PINECONE_DIMENSION=512`, `PINECONE_METRIC=cosine` |
| Supabase PostgreSQL | `SUPABASE_DB_HOST`, `SUPABASE_DB_PORT`, `SUPABASE_DB_NAME`, `SUPABASE_DB_USER`, `SUPABASE_DB_PASSWORD` |
| Supabase Storage | `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_STORAGE_BUCKET` |
| Xác thực | `JWT_SECRET`, `JWT_ALGORITHM`, thời hạn token |

Tạo một `JWT_SECRET` riêng có độ dài an toàn:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Dán kết quả vào:

```dotenv
JWT_SECRET=gia-tri-vua-tao
```

Lưu ý:

- `SUPABASE_SECRET_KEY` là secret phía server, tuyệt đối không đặt trong `frontend/.env`.
- Storage bucket mặc định là `product-images`. Nếu bucket private, giữ `SUPABASE_STORAGE_BUCKET_PUBLIC=false`.
- Các giá trị Pinecone phải khớp với index đã tạo; không tự ý đổi dimension hoặc metric.
- OpenCLIP sẽ được tải lần đầu và lưu tại `backend/artifacts/clip-cache`. Thư mục này được mount vào container nên không bị mất khi `--force-recreate`.

### Cấu hình `frontend/.env`

Với môi trường Docker chạy trên máy local, giữ nội dung:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_SHOW_TEST_CATEGORIES=true
```

Không thêm database password, JWT secret, Pinecone key hoặc Supabase secret vào frontend.

> Docker Compose hiện truyền `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` vào bước build frontend. Nếu triển khai bằng hostname khác, cần cập nhật build argument tương ứng trong `docker-compose.yml` rồi build lại frontend.

## 4. Chuẩn bị model phân loại

Luồng tìm kiếm ảnh của khách hàng sử dụng OpenCLIP và không cần checkpoint AlexNet. Chức năng AI gợi ý danh mục trong trang admin cần hai file:

```text
backend/artifacts/classifiers/alexnet/1.0.0/
├── manifest.json
└── model.pth
```

Các artifact lớn nằm trong `.gitignore`, vì vậy thành viên mới cần nhận checkpoint riêng và đặt đúng đường dẫn trên. Nếu chưa có checkpoint, các chức năng catalog thông thường vẫn chạy nhưng AlexNet sẽ không khả dụng.

## 5. Build và chạy bằng Docker Compose

Chạy toàn bộ dự án:

```bash
docker compose up -d --build
```

Kiểm tra trạng thái:

```bash
docker compose ps
```

Hai container mong đợi:

- `ecommerce-backend`: trạng thái `healthy`, cổng `8000`.
- `ecommerce-frontend`: trạng thái `running`, cổng `3000`.

Mở các địa chỉ:

- Giao diện: `http://localhost:3000`
- Backend health: `http://localhost:8000/api/v1/health`
- Swagger API: `http://localhost:8000/docs`

Theo dõi log khi có lỗi:

```bash
docker compose logs --no-color --tail=300 backend
docker compose logs --no-color --tail=300 frontend
```

Theo dõi log backend theo thời gian thực:

```bash
docker compose logs -f --tail=200 backend
```

Sau khi thay đổi source code hoặc biến môi trường, build và tạo lại container:

```bash
docker compose up -d --build --force-recreate backend frontend
```

Tắt dự án:

```bash
docker compose down
```

## 6. Khởi tạo database lần đầu

Chỉ thực hiện phần này khi dùng một Supabase database mới. Các script hỗ trợ chạy lặp lại và không chủ động xóa dữ liệu, nhưng vẫn cần kiểm tra đúng project Supabase trong `backend/.env` trước khi thêm `--apply`.

### 6.1. Tạo bảng người dùng

Xem trước kế hoạch:

```bash
docker compose exec backend python -m scripts.create_auth_schema
```

Áp dụng:

```bash
docker compose exec backend python -m scripts.create_auth_schema --apply
```

### 6.2. Tạo catalog và nạp dữ liệu mẫu

Các CSV mẫu nằm trong `backend/data`. Xem trước và áp dụng:

```bash
docker compose exec backend python -m scripts.insert_data
docker compose exec backend python -m scripts.insert_data --apply
```

### 6.3. Bổ sung schema quản trị catalog

```bash
docker compose exec backend python -m scripts.migrate_admin_catalog_schema
docker compose exec backend python -m scripts.migrate_admin_catalog_schema --apply
```

### 6.4. Tạo schema giỏ hàng và đơn hàng COD

```bash
docker compose exec backend python -m scripts.create_commerce_schema
docker compose exec backend python -m scripts.create_commerce_schema --apply
```

## 7. Tài khoản phát triển

Trang đăng nhập có nút điền nhanh cho hai tài khoản phát triển hiện tại:

| Vai trò | Email | Mật khẩu |
| --- | --- | --- |
| Customer | `user0@gmaill.com` | `123456789` |
| Admin | `admin@example.com` | `admin123` |

Các tài khoản phải tồn tại trong database đang cấu hình. Đăng ký công khai luôn tạo role `customer`. Để chuyển một tài khoản đã tồn tại sang admin:

```bash
docker compose exec backend python -m scripts.manage_user_role --email admin@example.com --role admin
docker compose exec backend python -m scripts.manage_user_role --email admin@example.com --role admin --apply
```

Không sử dụng các thông tin đăng nhập demo này cho môi trường production công khai.

## 8. Xử lý lỗi thường gặp

### Backend không healthy

```bash
docker compose logs --no-color --tail=300 backend
docker inspect ecommerce-backend --format '{{.State.Status}} exit={{.State.ExitCode}} error={{.State.Error}}'
```

Kiểm tra lại `backend/.env`, đặc biệt là Supabase, Pinecone và `JWT_SECRET`.

### Frontend không gọi được backend

- Xác nhận `http://localhost:8000/api/v1/health` trả về thành công.
- Kiểm tra `NEXT_PUBLIC_API_BASE_URL`.
- Sau khi đổi biến `NEXT_PUBLIC_*`, phải build lại frontend vì giá trị được nhúng tại thời điểm build.

### Lần đầu tìm kiếm hoặc đăng bán chậm

Backend cần tải và khởi tạo OpenCLIP trong lần sử dụng đầu tiên. Trọng số được lưu tại `backend/artifacts/clip-cache`; không xóa thư mục này nếu muốn giữ cache giữa các lần recreate container.

### Kiểm tra cấu hình Compose mà chưa chạy container

```bash
docker compose config --quiet
```

## 9. Tài liệu chi tiết

- Backend: [`backend/README.md`](backend/README.md)
- Frontend: [`frontend/README.md`](frontend/README.md)
- Các script vận hành: [`backend/scripts/README.md`](backend/scripts/README.md)
- Kế hoạch migration admin/classification: [`ADMIN_CATALOG_CLASSIFICATION_MIGRATION_PLAN.md`](ADMIN_CATALOG_CLASSIFICATION_MIGRATION_PLAN.md)

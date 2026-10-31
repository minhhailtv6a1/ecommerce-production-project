# Image-Based Product Search Backend

This directory contains the FastAPI backend for an image-based product search system. It provides health, custom JWT authentication, catalog, cart, COD checkout, order-history, product-detail, and CLIP image-search APIs plus operational Supabase/Pinecone pipelines. External clients and CLIP are initialized lazily, so the health endpoint does not depend on them.

## Requirements

- Python 3.11 or newer
- `pip`

No Pinecone, Supabase, model, or JWT credentials are required to start the application, call the health endpoint, or run isolated tests. Authentication endpoints require a configured Supabase PostgreSQL connection, an initialized `public.users` table, and a strong `JWT_SECRET`.

## Project structure

```text
backend/
├── Agents.md                 # Project requirements and engineering rules
├── app/
│   ├── main.py               # FastAPI creation and router registration
│   ├── api/routes/           # Health, auth, catalog, and image-search routes
│   ├── core/                 # Configuration, password hashing, and JWT logic
│   ├── schemas/              # Stable API response/request contracts
│   ├── services/             # Auth, catalog hydration, Storage, and image search
│   ├── repositories/         # PostgreSQL catalog/users and Pinecone access
│   └── utils/                # Future genuinely shared utilities
├── data/                     # Generated mock catalog CSV files
├── scripts/                  # Repeatable operational pipelines
├── tests/                    # Automated tests
├── .env.example              # Non-secret configuration template
├── pytest.ini                # Focused, cache-free pytest discovery
├── requirements.txt          # Runtime dependencies
└── requirements-dev.txt      # Runtime plus test dependencies
```

Package `__init__.py` files are included but omitted from the abbreviated tree above.

## Setup

Create and activate a virtual environment.

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install runtime dependencies:

```bash
pip install -r requirements.txt
```

Install development and testing dependencies when needed:

```bash
pip install -r requirements-dev.txt
```

Copy the environment template before customizing local values:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux, use `cp .env.example .env`. Placeholder external-service values are optional for the current scaffold.

The Supabase variables represent a direct PostgreSQL connection. Copy the exact host, port, database, username, and password from the Supabase Dashboard **Connect** dialog; pooler endpoints can use different hosts, ports, and usernames. SSL defaults to `require`.

Supabase Storage uses separate HTTP API settings: `SUPABASE_URL`, a server-only
`SUPABASE_SECRET_KEY`, and `SUPABASE_STORAGE_BUCKET`. Prefer the current
`sb_secret_...` key; the upload script also supports a legacy `service_role`
JWT. Never expose either server key to the frontend or commit it.

Generate a unique JWT secret and put it in `.env`:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Do not reuse the `.env.example` placeholder. The secret must contain at least 32 characters and must not be exposed to the frontend.

Preview the idempotent authentication schema plan, then create `public.users`:

```powershell
python -m scripts.create_auth_schema
python -m scripts.create_auth_schema --apply
```

After the auth and catalog tables exist, preview and create the cart/order tables:

```powershell
python -m scripts.create_commerce_schema
python -m scripts.create_commerce_schema --apply
```

This creates only `cart_items`, `orders`, `order_items`, and their indexes. It
does not delete catalog, user, cart, or order data.

## Generate and import mock catalog data

The catalog seed uses the first 200 supported images, sorted by relative path,
from each of the 42 canonical category directories. It creates 8,400 products,
one variant and one primary image record per product:

```powershell
python -m scripts.generate_catalog_data
```

The output files are `data/categories.csv`, `data/products.csv`,
`data/product_variants.csv`, and `data/product_images.csv`. The catalog fields
are mock development data; category IDs, source image paths, stable UUIDs, and
Pinecone vector IDs are deterministic.

Preview the database operation without connecting:

```powershell
python -m scripts.insert_data
```

After checking the plan and configuring the direct Supabase PostgreSQL fields,
create the four catalog tables and upsert all CSV rows:

```powershell
python -m scripts.insert_data --apply
```

The importer runs in one transaction, creates tables and indexes only when
missing, and performs idempotent upserts. It never drops or truncates tables.
Blank `product_images.public_url` values are imported as `NULL`; populate them
only after the corresponding images are available through storage/CDN or an
implemented backend image endpoint.

## Upload catalog images to Supabase Storage

After creating the bucket and filling the Storage variables in `.env`, validate
all 8,400 local source files and destination object paths without making a
network request:

```powershell
python -m scripts.upload_product_images
```

Run a small live smoke test first:

```powershell
python -m scripts.upload_product_images --apply --limit 10
```

Then upload or resume the complete manifest:

```powershell
python -m scripts.upload_product_images --apply
```

Objects are uploaded to the exact `storage_path` in `product_images.csv`, such
as `catalog/00/example.jpg`. Successful paths are checkpointed under
`artifacts/storage/`, so reruns skip completed objects. Existing objects are
treated as successful without replacement; use `--overwrite` only when an
intentional replacement is required.

If the bucket is public, set `SUPABASE_STORAGE_BUCKET_PUBLIC=true` or pass
`--public-bucket`. The script then fills `public_url` atomically in
`data/product_images.csv`. Rerun the catalog importer to persist those URLs:

```powershell
python -m scripts.insert_data --apply
```

For a private bucket, keep the setting false. The product API creates short-lived
signed URLs in one bulk Storage request; the server key is never returned.

## Run the API

From the `backend/` directory, run:

```bash
uvicorn app.main:app --reload
```

Available URLs:

- Health check: `GET http://127.0.0.1:8000/api/v1/health`
- Register: `POST http://127.0.0.1:8000/api/v1/auth/register`
- Login: `POST http://127.0.0.1:8000/api/v1/auth/login`
- Current user: `GET http://127.0.0.1:8000/api/v1/auth/me`
- Categories: `GET http://127.0.0.1:8000/api/v1/categories`
- Product catalog: `GET http://127.0.0.1:8000/api/v1/products`
- Product detail: `GET http://127.0.0.1:8000/api/v1/products/{id-or-slug}`
- Current cart: `GET http://127.0.0.1:8000/api/v1/cart`
- Add cart item: `POST http://127.0.0.1:8000/api/v1/cart/items`
- Update/remove cart item: `PATCH/DELETE http://127.0.0.1:8000/api/v1/cart/items/{variant_id}`
- Checkout COD: `POST http://127.0.0.1:8000/api/v1/orders`
- Order history: `GET http://127.0.0.1:8000/api/v1/orders`
- Order detail: `GET http://127.0.0.1:8000/api/v1/orders/{order_id}`
- Classifier capabilities: `GET http://127.0.0.1:8000/api/v1/image-search/classifiers`
- Image classification: `POST http://127.0.0.1:8000/api/v1/image-search/classify`
- Visual product search: `POST http://127.0.0.1:8000/api/v1/image-search/search`
- OpenAPI documentation: `http://127.0.0.1:8000/docs`

The health response is:

```json
{"status": "ok"}
```

This response only confirms that the backend application is running. It does not report the status of the model, Pinecone, or Supabase.

Registration and login accept JSON:

```json
{
  "email": "user@example.com",
  "password": "a-password-with-at-least-8-characters"
}
```

Both return a 30-minute access token and a public user object. Call protected endpoints with:

```http
Authorization: Bearer <access_token>
```

Passwords are stored only as Argon2 hashes. JWTs are signed with HS256 and include issuer, audience, issued-at, expiration, subject, type, and token ID claims. This initial auth phase does not yet provide refresh tokens, password reset, email verification, or server-side token revocation.

Cart and order endpoints require the same Bearer token. Add a product variant
with `{"variant_id": "<uuid>", "quantity": 1}`. Checkout accepts
`receiver_name`, `phone`, `shipping_address`, and optional `note`. Checkout is a
single database transaction: it locks and revalidates variants, uses current
server-side prices, checks stock, creates immutable order-item snapshots,
decrements inventory, and clears the cart. The initial payment method is COD and
new orders have `pending` status; online payment, vouchers, shipping fees, and
automatic fulfilment are intentionally out of scope.

Catalog hydration passes native UUID parameters to PostgreSQL so primary and
foreign-key indexes remain usable. The default newest listing selects the
requested page before variant aggregation and returns the total in the same
query, avoiding a second Supabase round trip for normal pages. Operational
index cleanup is documented in `scripts/README.md`.

Catalog supports repeated `category_ids`, `size`, `color`, `brand`, minimum and
maximum price, stock state, sorting (`newest`, `price_asc`, `price_desc`), page,
and limit. Image search accepts multipart fields `image`, repeated
`category_ids`, and `limit`. It retrieves the top 50 Pinecone candidates,
validates encoded content before CLIP inference, deduplicates matches by
`product_id`, hydrates authoritative catalog data from PostgreSQL, and preserves
similarity ranking. The response includes `retrieval_time_ms`, measured on the
server across CLIP embedding, Pinecone retrieval, and product hydration.

Classifier capabilities report AlexNet as available when its versioned manifest
and checkpoint pass validation. ResNet50 and ViT remain visible as unavailable
until their own verified artifacts are supplied. Classification accepts multipart
fields `image`, `model_id`, and optional `top_k` (default 5, maximum 10). It
returns logits for diagnostics, Softmax probabilities for the UI, the suggested
top-1 category, and preprocessing/inference/postprocessing/total timing.

The AlexNet artifact is stored at
`artifacts/classifiers/alexnet/1.0.0/`. Its manifest records the exact custom
architecture, SHA-256 checksum, `ImageFolder` mapping `00 -> 0` through
`41 -> 41`, and training preprocessing. The registry validates the artifact and
loads the model lazily once per backend process. Therefore the first request also
includes checksum verification and model loading in `timing.total_ms`; subsequent
requests reuse the in-memory model. A local CPU smoke test measured about 12.8 s
for cold start and 39 ms for the next request. These values are environment
specific and are not a production latency guarantee.

Set `CORS_ORIGINS` to a JSON list of exact frontend origins. API failures use
`code`, `message`, `field_errors`, and `request_id`; the same request ID is sent
in `X-Request-ID`.

## Run tests

```bash
pytest
```

The test suite imports the application and exercises the health endpoint without external credentials.
Pytest discovery is limited to `tests/`, and its cache provider is disabled so tests also work in restricted or read-only-cache environments.

## Not implemented yet

- ResNet50 classification adapter and artifact
- ViT classification adapter and artifact
- Golden preprocessing fixtures exported from each training pipeline
- Comparative top-5 accuracy, macro-F1, calibration, and retrieval-recall benchmark
- Deployment-level rate limiting for inference requests
- Refresh tokens, password reset, and email verification

These components require verified artifacts, schemas, and external configuration and will be implemented only when their contracts are defined.

Index provisioning is available separately through `python -m scripts.create_pinecone_index`. It requires an explicitly configured vector field, embedding dimension, similarity metric, cloud, and region; see `scripts/README.md`. Provisioning does not implement embedding generation or vector retrieval.

The confirmed Pinecone schema is a 512-dimensional CLIP image vector field named `image_vector` using cosine similarity.

The operational ingestion pipeline generates normalized OpenAI CLIP `ViT-B-32` image embeddings and upserts them with `category_id`, dataset-relative `image_path`, `product_id`, and `image_id` when the image exists in the catalog manifest. Existing indexed documents can receive catalog links without recomputing vectors through `python -m scripts.backfill_pinecone_catalog_metadata --apply`.

The first model run downloads the OpenAI pretrained weights unless `CLIP_PRETRAINED` points to a local OpenCLIP-compatible checkpoint. For CUDA execution, install the PyTorch build recommended for the machine by the official PyTorch installer before installing the remaining requirements; an already compatible `torch` installation is preserved by `pip`.

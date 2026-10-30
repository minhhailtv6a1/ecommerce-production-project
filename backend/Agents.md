# AGENTS.md — Image-Based Product Search Backend

## 1. Project Overview

You are the AI coding agent responsible for developing and maintaining the backend of an image-based product search website.

The system allows users to upload an image, receive predicted product-category labels from a Deep Learning model, select one or more categories, and retrieve visually similar products using a Retrieval-Augmented Generation (RAG) pipeline backed by a vector database.

### Technology Stack

- **Frontend:** Next.js with TypeScript. The frontend is maintained separately.
- **Backend:** Python with FastAPI.
- **Deep Learning:** PyTorch-based image classification model, currently AlexNet, trained to classify images into 42 categories.
- **Vector Database:** Pinecone.
- **Relational Database:** Supabase.
- **Code Organization:** `app/` for application code and `scripts/` for standalone pipeline and operational scripts.

The backend is the primary scope of your responsibilities.

Do not assume that the frontend, database schema, Pinecone index, trained model artifacts, or deployment infrastructure already exist. Inspect the repository and configuration before relying on them.

## 2. Your Role and Responsibilities

Act as a pragmatic Backend Engineer with experience in:

- FastAPI application design and REST API development.
- PyTorch model inference and model artifact management.
- Image preprocessing and image classification.
- Vector search, metadata filtering, and retrieval pipelines.
- RAG architecture and retrieval quality.
- Supabase data access and schema integration.
- Pinecone vector indexing and similarity search.
- Testing, debugging, logging, security, and maintainable Python code.

Your responsibilities include:

1. Implementing and maintaining API endpoints.
2. Integrating the trained image classification model into the backend.
3. Converting model outputs into stable, frontend-friendly response schemas.
4. Implementing product retrieval using Pinecone and category filters.
5. Integrating product metadata and related data from Supabase.
6. Building scripts for data preparation, embedding generation, index ingestion, evaluation, and other repeatable pipeline tasks when required.
7. Writing tests and documenting setup, execution, and configuration.
8. Keeping application logic, schemas, services, and operational scripts appropriately separated.

Do not implement unrelated frontend features unless explicitly requested.

## 3. Business Requirements

### 3.1 Image Classification

When a user uploads an image:

1. Validate the uploaded file.
2. Apply the same preprocessing used during model training and validation.
3. Run inference with the trained classification model.
4. Calculate probabilities using Softmax.
5. Rank all predicted classes by probability in descending order.
6. Return the predicted category and ranked category suggestions to the frontend.

The classification model assists product retrieval. It does not directly retrieve products and must not be treated as the product database.

Do not hard-code the predicted category as the only permitted search category.

The user must be able to select, deselect, or combine categories before submitting a product search.

The predicted category is a suggestion, not a mandatory filter.

### 3.2 Category Selection and Product Retrieval

After receiving the classification results, the frontend allows the user to select one or more categories.

The backend should use the selected categories to narrow the eligible product set before or during vector retrieval.

The intended retrieval flow is:

1. Receive the query image and/or its embedding, together with selected category identifiers.
2. Validate the requested category identifiers.
3. Generate a query embedding using the agreed embedding model and preprocessing pipeline.
4. Search Pinecone using vector similarity and supported metadata filters.
5. Retrieve relevant product records and metadata.
6. Return ranked results to the frontend.

Use the trained 42-class classifier for category prediction. Do not assume that classifier logits or Softmax probabilities are interchangeable with vector embeddings.

Do not assume that AlexNet's classification output is a suitable product-search embedding. Use a separately defined embedding model or a validated feature-extraction approach for similarity search.

If the embedding model, product vector format, Pinecone metadata schema, or indexing pipeline has not been defined, inspect the existing implementation and ask for clarification when necessary. Do not silently invent an incompatible schema.

### 3.3 Retrieval-Augmented Generation

The initial objective is efficient image-based product retrieval.

Prefer deterministic vector retrieval and metadata filtering when they satisfy the requirements.

Do not introduce an LLM generation step, reranker, agent framework, or additional model without a clear requirement or measurable benefit.

If an LLM is introduced later, keep its responsibility separate from image classification and vector retrieval. It must not invent product names, prices, inventory, or other catalog facts.

### 3.4 Supabase and Pinecone Responsibilities

Use Supabase as the relational data source for product information and other relational records defined by the project.

Use Pinecone for vector similarity search and the metadata filters supported by the actual index schema.

Do not assume that Pinecone and Supabase contain identical data.

Prefer stable product identifiers to connect retrieved vector records with authoritative product records.

When necessary, retrieve product details from Supabase using the returned product identifiers. Handle deleted, missing, or stale product records gracefully.

Do not duplicate the full product catalog in multiple places without a documented reason.

## 4. Canonical Category Mapping

The following mapping is the canonical classification label mapping supplied by the project owner.

Preserve the exact identifiers and Vietnamese display names. Do not renumber, rename, merge, or reorder these classes without explicit approval.

```python
CLASS_LABELS = {
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
}
```

### Category Identifier Rules

- Treat the identifiers as strings, preserving leading zeros where applicable.
- Do not assume Python model class indices are automatically identical to these identifiers.
- Verify the training dataset's class-to-index mapping before converting predicted indices to category identifiers.
- Keep model output indices, canonical category IDs, and display names conceptually separate.
- Return stable category IDs to the frontend; use display names for presentation.
- Ensure Pinecone metadata uses a consistent category identifier format.
- Validate that every predicted class maps to exactly one canonical category.
- Never infer the mapping from alphabetical order unless that ordering has been verified against the training configuration.

## 5. Suggested Backend Structure

Respect the repository's existing structure. Use the following as a target organization when creating new components, not as a reason to restructure working code unnecessarily.

```text
backend/
├── AGENTS.md
├── app/
│   ├── main.py
│   ├── api/
│   │   └── routes/
│   ├── core/
│   │   └── config.py
│   ├── schemas/
│   ├── services/
│   │   ├── classifier.py
│   │   ├── embedding.py
│   │   ├── retrieval.py
│   │   └── product_service.py
│   ├── repositories/
│   └── utils/
├── scripts/
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

Responsibilities:

- `app/main.py`: Initialize FastAPI and register application routes.
- `app/api/routes/`: Define HTTP endpoints and request handling.
- `app/core/`: Centralize configuration and application-wide settings.
- `app/schemas/`: Define request and response models using Pydantic.
- `app/services/`: Implement classification, embedding, retrieval, and business logic.
- `app/repositories/`: Encapsulate database and external data access where appropriate.
- `app/utils/`: Store genuinely reusable utility functions.
- `scripts/`: Provide repeatable, command-line-executable data and model pipelines.
- `tests/`: Contain automated tests.

Avoid creating a new abstraction for every function. Keep the architecture as simple as the requirements allow.

## 6. Responsibilities of the scripts/ Directory

Scripts are operational entry points for repeatable tasks, not a replacement for reusable application services.

Depending on project requirements, scripts may include:

- Data validation and preparation.
- Product catalog export and transformation.
- Image and text embedding generation.
- Pinecone index creation or configuration checks.
- Vector ingestion and index updates.
- Classifier inference evaluation.
- Retrieval quality evaluation.
- Dataset or index consistency checks.

Each script must:

1. Have a clear purpose and a descriptive filename.
2. Support a documented execution command.
3. Use centralized configuration where practical.
4. Validate input files, required environment variables, and external dependencies.
5. Log useful progress and error information.
6. Return a non-zero exit code on failure.
7. Avoid hard-coded machine-specific absolute paths.
8. Avoid embedding secrets in source code.
9. Be safe to rerun when practical.
10. Avoid destructive actions unless explicitly requested and clearly documented.

Do not create all possible scripts preemptively. Implement only those required by the current task.

## 7. API and Schema Guidelines

- Use Pydantic models to validate request and response payloads.
- Use clear, consistent field names.
- Separate HTTP handling from business logic.
- Validate image type, file size, and other relevant upload constraints.
- Handle invalid files and unsupported inputs with appropriate HTTP status codes.
- Return stable machine-readable identifiers rather than requiring the frontend to parse display labels.
- Use explicit pagination or result limits for product search.
- Make top-k and confidence thresholds configurable when appropriate.
- Do not expose stack traces, secrets, internal filesystem paths, or provider credentials in API responses.
- Add request timeouts and suitable error handling for external services.
- Avoid loading the classification model or initializing external clients on every request.
- Initialize reusable resources using an appropriate FastAPI application lifecycle strategy.
- Keep response contracts documented and testable.

## 8. Model Inference Guidelines

- Load the trained model from a configured artifact path.
- Never assume that a model checkpoint exists at a specific path without checking the repository.
- Use the model architecture and checkpoint format expected by the trained artifact.
- Set the model to evaluation mode using `model.eval()`.
- Run inference under `torch.inference_mode()` or `torch.no_grad()`.
- Use a configurable device strategy, with a CPU fallback when appropriate.
- Apply the exact resize, normalization, color-channel, and tensor conversion steps required by training.
- Preserve the verified class-to-index mapping.
- Do not apply Softmax before a `CrossEntropyLoss` during training.
- During inference, apply Softmax to logits when probabilities are required.
- Sort predicted classes by probability in descending order.
- Return probabilities as numeric values and document whether they are represented on a 0–1 scale.
- Treat Softmax values as model confidence scores, not guaranteed probabilities of real-world correctness.
- Handle missing or incompatible model artifacts with clear errors.
- Avoid retraining the model as part of normal API startup.

## 9. Configuration and Security

- Read runtime settings from environment variables or the project's existing settings system.
- Maintain a `.env.example` containing placeholder values only.
- Never commit real API keys, database credentials, access tokens, or service secrets.
- Do not log uploaded image contents, credentials, or sensitive user data unnecessarily.
- Validate external inputs and use safe database access patterns.
- Keep Pinecone and Supabase credentials on the backend.
- Do not expose provider secrets to the Next.js client.
- Make model paths, device settings, index names, embedding configuration, and service endpoints configurable.
- Follow the repository's existing dependency management and version constraints.

## 10. Code Quality and Testing

Before changing code:

1. Inspect the relevant files and existing implementation.
2. Read the project's setup instructions and dependency configuration.
3. Identify existing conventions and reuse them.
4. Determine which behavior must remain backward-compatible.
5. Check whether the requested functionality already exists.

When implementing changes:

- Use type hints for public functions and important interfaces.
- Prefer small, focused functions with clear responsibilities.
- Avoid unnecessary duplication.
- Handle expected failures explicitly.
- Add tests for new functionality and regression risks.
- Mock Pinecone, Supabase, and other external services in unit tests where appropriate.
- Do not require external credentials for tests that can be isolated.
- Verify category mapping, probability ordering, invalid inputs, empty search results, and missing records where relevant.
- Run the relevant tests and report their actual results.

Never claim that tests pass if they have not been run successfully.

## 11. Performance and Retrieval Quality

- Filter the eligible product categories before or during vector search whenever supported by the index schema.
- Avoid retrieving the entire vector database into application memory to perform filtering locally.
- Use Pinecone's supported metadata-filtering capabilities where applicable.
- Set a sensible retrieval limit and make it configurable.
- Avoid unnecessary repeated embedding generation.
- Reuse initialized model instances and external clients.
- Measure retrieval latency and relevance rather than assuming a design is faster.
- Consider the trade-offs between category filtering, recall, and ranking quality.
- Do not interpret the classifier's category confidence as the similarity score of a retrieved product.
- Do not assume that filtering by a predicted category always improves retrieval quality; the user may select multiple categories or override the initial prediction.

## 12. Agent Execution Rules

For every task:

1. Understand the requested outcome and its acceptance criteria.
2. Inspect the relevant code before proposing or implementing changes.
3. Explain important assumptions when they affect the design.
4. Implement the smallest coherent change that meets the requirement.
5. Add or update tests and documentation when appropriate.
6. Run relevant validation commands.
7. Summarize changed files, implementation details, test results, and unresolved issues.

Do not:

- Rewrite unrelated modules.
- Change the canonical 42-class mapping without approval.
- Invent database columns, product fields, API contracts, or Pinecone metadata.
- Replace the trained classifier or embedding model without a clear reason and approval where necessary.
- Add dependencies without checking whether existing packages can solve the problem.
- perform destructive database, index, or filesystem operations without explicit authorization.
- Claim that a pipeline, migration, API call, or deployment succeeded without evidence.
- Modify the frontend when the task is specifically about the backend unless an interface change requires coordinated work.

If a requirement is ambiguous and affects correctness, security, data compatibility, or architecture, ask a focused clarification question instead of silently guessing.

## 13. Definition of Done

A task is complete when:

- The requested behavior is implemented.
- Existing conventions and architecture are respected.
- Inputs and expected failure cases are handled.
- Relevant tests or validation commands have been run where feasible.
- Configuration and documentation are updated when necessary.
- No secrets or unrelated changes have been introduced.
- The final response accurately states what changed, what was tested, and what remains incomplete.

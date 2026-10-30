# Operational scripts

This directory is reserved for standalone, repeatable operational pipelines, such as data preparation, embedding generation, vector ingestion, and retrieval evaluation.

Scripts should validate their inputs and configuration, be safe to rerun where practical, and reuse application services instead of duplicating business logic.

## Catalog CSV generation and Supabase import

Generate deterministic mock catalog data from the first 200 sorted images in
each canonical label directory:

```bash
python -m scripts.generate_catalog_data
```

This creates four UTF-8 files under `data/`: `categories.csv`, `products.csv`,
`product_variants.csv`, and `product_images.csv`. Every selected image maps to
one stable product UUID, one variant UUID, one image UUID, and its current
Pinecone vector ID. The default run leaves `public_url` blank because local
dataset paths are not browser-accessible.

Preview the validated import plan without a database connection:

```bash
python -m scripts.insert_data
```

Apply the schema and data to the configured direct Supabase PostgreSQL
connection:

```bash
python -m scripts.insert_data --apply
```

The importer creates `public.categories`, `public.products`,
`public.product_variants`, and `public.product_images` plus relevant indexes.
All writes run in one transaction and use `ON CONFLICT ... DO UPDATE`; the
script does not drop, truncate, or delete existing rows.

## Supabase Storage image upload

Configure `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and
`SUPABASE_STORAGE_BUCKET`, then validate the upload plan:

```bash
python -m scripts.upload_product_images
```

Smoke-test ten uploads before running the complete manifest:

```bash
python -m scripts.upload_product_images --apply --limit 10
python -m scripts.upload_product_images --apply
```

The script reads `data/product_images.csv` and uploads each dataset image to its
provider-neutral path `catalog/<category-id>/<filename>`. It supports category
filters, concurrency, retries for transient responses, an append-only resume
checkpoint, existing-object detection, and opt-in overwrite.

For a public bucket, set `SUPABASE_STORAGE_BUCKET_PUBLIC=true`; completed and
checkpointed objects receive their public Storage URL in the CSV. For a private
bucket, `public_url` is left unchanged for later signed-URL generation.

Useful options:

```bash
python -m scripts.upload_product_images --apply --category 00 --limit 10
python -m scripts.upload_product_images --apply --workers 4
python -m scripts.upload_product_images --apply --overwrite
python -m scripts.upload_product_images --apply --no-resume
```

## Authentication schema

Preview the minimal custom-auth schema without connecting to PostgreSQL:

```bash
python -m scripts.create_auth_schema
```

After configuring the direct Supabase PostgreSQL fields and installing runtime
dependencies, create or validate `public.users`:

```bash
python -m scripts.create_auth_schema --apply
```

The operation is idempotent and never deletes users. It creates a UUID primary
key, normalized unique email, Argon2 password-hash field, active flag, and
creation timestamp. It rejects an existing table that is missing required
columns.

## Pinecone index provisioning

Configure the Pinecone variables in `.env`, then inspect the immutable index plan without making a network request:

```bash
python -m scripts.create_pinecone_index
```

After verifying the vector field, dimension, metric, cloud, and region, explicitly apply it:

```bash
python -m scripts.create_pinecone_index --apply
```

The command is idempotent. It creates a missing index, accepts an existing compatible index, and rejects an existing index whose schema or deployment differs. It never deletes an index or writes vectors.

`PINECONE_DIMENSION` and `PINECONE_METRIC` must come from the selected embedding model or validated feature-extraction pipeline. They must not be inferred from the classifier's 42 output classes.

The confirmed initial schema uses a CLIP image embedding stored in `image_vector`, with dimension `512` and cosine similarity. The configured managed deployment is AWS `us-east-1`.

The optional live pytest uses the same flow and must be explicitly enabled:

```powershell
$env:RUN_PINECONE_INTEGRATION = "1"
pytest -m integration
```

## CLIP image ingestion

The ingestion pipeline validates the complete `00/` through `41/` label layout, ignores unsupported files, generates normalized OpenAI CLIP `ViT-B-32` image embeddings, and writes Pinecone documents containing:

```json
{
  "_id": "<stable ID derived from the dataset-relative path>",
  "image_vector": ["512 normalized float values"],
  "category_id": "00",
  "image_path": "00/example.jpg",
  "product_id": "<stable product UUID when present in the manifest>",
  "image_id": "<stable image UUID when present in the manifest>"
}
```

`image_path` is always relative to the configured training directory and uses
forward slashes, so it does not contain a machine-specific absolute path.

Preview dataset counts and the target without loading CLIP or writing data:

```bash
python -m scripts.ingest_pinecone_images
```

Run a small live smoke batch first:

```bash
python -m scripts.ingest_pinecone_images --apply --limit 10
```

To process a balanced subset, apply the limit independently to all 42 labels. This example ingests up to 10 pending images from every label, for at most 420 images:

```bash
python -m scripts.ingest_pinecone_images --apply --limit 10 --each
```

Checkpointed images are removed before each per-label quota is selected, so rerunning the command continues with the next pending images in every label.

Run or resume the complete ingestion:

```bash
python -m scripts.ingest_pinecone_images --apply
```

Successful batches are recorded under `artifacts/ingestion/`. Re-running the command skips checkpointed IDs. Use `--no-resume` to ignore the local checkpoint and idempotently upsert every image again. The pipeline never deletes stale Pinecone documents.

To attach catalog IDs to previously ingested documents without loading CLIP or
recomputing vectors, preview and apply the partial metadata backfill:

```bash
python -m scripts.backfill_pinecone_catalog_metadata
python -m scripts.backfill_pinecone_catalog_metadata --apply
python -m scripts.backfill_pinecone_catalog_metadata --verify-only
```

The apply command verifies all manifest links by reading them back from
Pinecone. It updates only `product_id` and `image_id`.

Documents ingested before `image_path` was introduced must be upserted again.
For example, repeat the original limited batch with `--no-resume`:

```bash
python -m scripts.ingest_pinecone_images --apply --limit 10 --no-resume
```

The opt-in live integration test embeds and upserts one real catalog image, then
fetches it to verify `category_id`, `image_path`, `product_id`, and `image_id`:

```powershell
$env:RUN_PINECONE_INGEST_INTEGRATION = "1"
pytest tests/integration/test_pinecone_ingestion_live.py
```

## CLIP image search

Search with the first supported image found recursively under
`SEARCH_TEST_DATASET_PATH`. When that setting is empty, the script uses the
`test` directory next to `INGEST_DATASET_PATH`:

```bash
python -m scripts.search_pinecone_images --top-k 10
```

Select a reproducible random test image:

```bash
python -m scripts.search_pinecone_images --random --seed 42 --top-k 10
```

Search with an explicit image:

```bash
python -m scripts.search_pinecone_images --image path/to/query.jpg --top-k 10
```

Optionally restrict retrieval to one or more canonical category IDs:

```bash
python -m scripts.search_pinecone_images --image path/to/query.jpg --category 00 --category 02
```

The command embeds only the query image and does not write to Pinecone. It
prints ranked JSON results containing `_id`, similarity score, `category_id`,
and dataset-relative `image_path`.

Run the opt-in live search test with:

```powershell
$env:RUN_PINECONE_SEARCH_INTEGRATION = "1"
pytest tests/integration/test_pinecone_search_live.py
```

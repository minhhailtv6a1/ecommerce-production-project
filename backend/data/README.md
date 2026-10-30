# Generated catalog data

This directory contains deterministic mock catalog records generated from the
training image dataset. The committed CSVs use the first 200 supported images
in lexicographic path order from each canonical category directory (`00`–`41`).

Files:

- `categories.csv`: 42 canonical category IDs and Vietnamese display names.
- `products.csv`: 8,400 mock products, one product per selected source image.
- `product_variants.csv`: one purchasable mock variant per product, including
  VND price, color, optional size, and inventory.
- `product_images.csv`: stable product/image relationships, current Pinecone
  vector ID, dataset-relative source path, future storage path, and image URL.

All names, brands, prices, stock values, colors, sizes, and descriptions are
synthetic development data. They are not real merchant catalog facts.

`public_url` is initially blank because the source images have not been uploaded
to a public storage bucket and the backend does not yet expose an image-serving
endpoint. After configuring a public Supabase bucket, upload the images and let
the script update the URLs:

```powershell
python -m scripts.upload_product_images --apply --public-bucket
python -m scripts.insert_data --apply
```

The `storage_path` values are provider-neutral and use the form
`catalog/<category-id>/<filename>`. No image binaries are copied into this
directory.


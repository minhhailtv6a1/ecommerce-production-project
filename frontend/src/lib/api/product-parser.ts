import { isCategoryId } from "@/domain/categories";
import type {
  ProductCardData,
  ProductDetail,
  ProductImage,
  ProductVariant,
} from "@/types/product";
import {
  arrayValue,
  booleanValue,
  invalidResponse,
  nullableNumber,
  nullableString,
  numberValue,
  record,
  stringArray,
  stringValue,
} from "./parse";

function parseImage(value: unknown): ProductImage {
  const data = record(value, "ảnh sản phẩm");
  return {
    id: stringValue(data.id, "image.id"),
    url: stringValue(data.url, "image.url"),
    alt: stringValue(data.alt, "image.alt"),
    sort_order: numberValue(data.sort_order, "image.sort_order"),
    is_primary: booleanValue(data.is_primary, "image.is_primary"),
  };
}

function parseCategoryId(value: unknown): ProductCardData["category_id"] {
  const categoryId = stringValue(value, "product.category_id");
  if (!isCategoryId(categoryId)) {
    return invalidResponse(`Backend trả về category_id không xác định: ${categoryId}`);
  }
  return categoryId;
}

export function parseProductCard(value: unknown): ProductCardData {
  const data = record(value, "sản phẩm");
  return {
    id: stringValue(data.id, "product.id"),
    slug: stringValue(data.slug, "product.slug"),
    name: stringValue(data.name, "product.name"),
    category_id: parseCategoryId(data.category_id),
    brand: nullableString(data.brand, "product.brand"),
    price: numberValue(data.price, "product.price"),
    compare_at_price: nullableNumber(
      data.compare_at_price,
      "product.compare_at_price",
    ),
    currency: stringValue(data.currency, "product.currency"),
    primary_image: parseImage(data.primary_image),
    available_sizes: stringArray(
      data.available_sizes,
      "product.available_sizes",
    ),
    available_colors: stringArray(
      data.available_colors,
      "product.available_colors",
    ),
    in_stock: booleanValue(data.in_stock, "product.in_stock"),
  };
}

function parseVariant(value: unknown): ProductVariant {
  const data = record(value, "biến thể");
  return {
    id: stringValue(data.id, "variant.id"),
    sku: stringValue(data.sku, "variant.sku"),
    color: nullableString(data.color, "variant.color"),
    size: nullableString(data.size, "variant.size"),
    price: numberValue(data.price, "variant.price"),
    compare_at_price: nullableNumber(
      data.compare_at_price,
      "variant.compare_at_price",
    ),
    inventory_quantity: numberValue(
      data.inventory_quantity,
      "variant.inventory_quantity",
    ),
    is_active: booleanValue(data.is_active, "variant.is_active"),
  };
}

export function parseProductDetail(value: unknown): ProductDetail {
  const data = record(value, "chi tiết sản phẩm");
  const card = parseProductCard(value);
  const status = stringValue(data.status, "product.status");
  if (status !== "published") {
    return invalidResponse(`Trạng thái sản phẩm không được hỗ trợ: ${status}`);
  }
  return {
    ...card,
    description: nullableString(data.description, "product.description"),
    status,
    created_at: stringValue(data.created_at, "product.created_at"),
    images: arrayValue(data.images, "product.images").map(parseImage),
    variants: arrayValue(data.variants, "product.variants").map(parseVariant),
  };
}

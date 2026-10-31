import type {
  Cart,
  CartItem,
  Order,
  OrderItem,
  OrderStatus,
} from "@/types/commerce";
import {
  arrayValue,
  booleanValue,
  invalidResponse,
  nullableString,
  numberValue,
  record,
  stringValue,
} from "./parse";

function parseCartItem(value: unknown): CartItem {
  const data = record(value, "mục trong giỏ hàng");
  return {
    variant_id: stringValue(data.variant_id, "cart_item.variant_id"),
    product_id: stringValue(data.product_id, "cart_item.product_id"),
    product_name: stringValue(data.product_name, "cart_item.product_name"),
    product_slug: stringValue(data.product_slug, "cart_item.product_slug"),
    sku: stringValue(data.sku, "cart_item.sku"),
    color: nullableString(data.color, "cart_item.color"),
    size: nullableString(data.size, "cart_item.size"),
    unit_price: numberValue(data.unit_price, "cart_item.unit_price"),
    currency: stringValue(data.currency, "cart_item.currency"),
    quantity: numberValue(data.quantity, "cart_item.quantity"),
    inventory_quantity: numberValue(
      data.inventory_quantity,
      "cart_item.inventory_quantity",
    ),
    available: booleanValue(data.available, "cart_item.available"),
    line_total: numberValue(data.line_total, "cart_item.line_total"),
  };
}

export function parseCart(value: unknown): Cart {
  const data = record(value, "giỏ hàng");
  return {
    items: arrayValue(data.items, "cart.items").map(parseCartItem),
    item_count: numberValue(data.item_count, "cart.item_count"),
    subtotal: numberValue(data.subtotal, "cart.subtotal"),
    currency:
      data.currency === null
        ? null
        : stringValue(data.currency, "cart.currency"),
  };
}

function parseOrderStatus(value: unknown): OrderStatus {
  const status = stringValue(value, "order.status");
  if (
    status !== "pending" &&
    status !== "confirmed" &&
    status !== "shipping" &&
    status !== "completed" &&
    status !== "cancelled"
  ) {
    return invalidResponse(`Trạng thái đơn hàng không được hỗ trợ: ${status}`);
  }
  return status;
}

function parseOrderItem(value: unknown): OrderItem {
  const data = record(value, "sản phẩm trong đơn hàng");
  return {
    id: stringValue(data.id, "order_item.id"),
    product_id: stringValue(data.product_id, "order_item.product_id"),
    variant_id: stringValue(data.variant_id, "order_item.variant_id"),
    product_name: stringValue(data.product_name, "order_item.product_name"),
    sku: stringValue(data.sku, "order_item.sku"),
    color: nullableString(data.color, "order_item.color"),
    size: nullableString(data.size, "order_item.size"),
    unit_price: numberValue(data.unit_price, "order_item.unit_price"),
    quantity: numberValue(data.quantity, "order_item.quantity"),
    line_total: numberValue(data.line_total, "order_item.line_total"),
  };
}

export function parseOrder(value: unknown): Order {
  const data = record(value, "đơn hàng");
  const paymentMethod = stringValue(data.payment_method, "order.payment_method");
  if (paymentMethod !== "cod") {
    return invalidResponse(
      `Phương thức thanh toán không được hỗ trợ: ${paymentMethod}`,
    );
  }
  return {
    id: stringValue(data.id, "order.id"),
    status: parseOrderStatus(data.status),
    payment_method: paymentMethod,
    receiver_name: stringValue(data.receiver_name, "order.receiver_name"),
    phone: stringValue(data.phone, "order.phone"),
    shipping_address: stringValue(
      data.shipping_address,
      "order.shipping_address",
    ),
    note: nullableString(data.note, "order.note"),
    total_amount: numberValue(data.total_amount, "order.total_amount"),
    currency: stringValue(data.currency, "order.currency"),
    created_at: stringValue(data.created_at, "order.created_at"),
    items: arrayValue(data.items, "order.items").map(parseOrderItem),
  };
}

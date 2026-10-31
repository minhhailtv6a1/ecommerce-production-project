import type { Cart, OrderStatus } from "@/types/commerce";

export const EMPTY_CART: Cart = {
  items: [],
  item_count: 0,
  subtotal: 0,
  currency: null,
};

export function canCheckout(cart: Cart): boolean {
  return (
    cart.items.length > 0 &&
    cart.currency !== null &&
    cart.items.every((item) => item.available)
  );
}

export function orderStatusLabel(status: OrderStatus): string {
  const labels: Record<OrderStatus, string> = {
    pending: "Chờ xác nhận",
    confirmed: "Đã xác nhận",
    shipping: "Đang giao",
    completed: "Hoàn tất",
    cancelled: "Đã hủy",
  };
  return labels[status];
}

export function formatOrderDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function variantDescription(
  color: string | null,
  size: string | null,
  sku: string,
): string {
  return [color ? `Màu ${color}` : null, size ? `Size ${size}` : null, sku]
    .filter(Boolean)
    .join(" · ");
}

import type {
  Cart,
  CheckoutInput,
  Order,
  OrderListResponse,
} from "@/types/commerce";
import { requestJson } from "./http-client";
import { parseCart, parseOrder } from "./commerce-parser";
import { arrayValue, record } from "./parse";

export async function getCart(
  token: string,
  signal?: AbortSignal,
): Promise<Cart> {
  return parseCart(await requestJson("/cart", { token, signal }));
}

export async function addCartItem(
  token: string,
  variantId: string,
  quantity: number,
): Promise<Cart> {
  return parseCart(
    await requestJson("/cart/items", {
      method: "POST",
      token,
      body: { variant_id: variantId, quantity },
    }),
  );
}

export async function updateCartItem(
  token: string,
  variantId: string,
  quantity: number,
): Promise<Cart> {
  return parseCart(
    await requestJson(`/cart/items/${encodeURIComponent(variantId)}`, {
      method: "PATCH",
      token,
      body: { quantity },
    }),
  );
}

export async function removeCartItem(
  token: string,
  variantId: string,
): Promise<void> {
  await requestJson(`/cart/items/${encodeURIComponent(variantId)}`, {
    method: "DELETE",
    token,
  });
}

export async function checkout(
  token: string,
  input: CheckoutInput,
): Promise<Order> {
  return parseOrder(
    await requestJson("/orders", {
      method: "POST",
      token,
      body: input,
    }),
  );
}

export async function getOrders(
  token: string,
  signal?: AbortSignal,
): Promise<OrderListResponse> {
  const data = record(
    await requestJson("/orders", { token, signal }),
    "danh sách đơn hàng",
  );
  return {
    items: arrayValue(data.items, "orders.items").map(parseOrder),
  };
}

export async function getOrder(
  token: string,
  orderId: string,
  signal?: AbortSignal,
): Promise<Order> {
  return parseOrder(
    await requestJson(`/orders/${encodeURIComponent(orderId)}`, {
      token,
      signal,
    }),
  );
}

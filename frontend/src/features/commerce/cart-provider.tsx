"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useAuth } from "@/features/auth/auth-provider";
import {
  addCartItem,
  getCart,
  removeCartItem,
  updateCartItem,
} from "@/lib/api/commerce.api";
import type { ApiError } from "@/lib/api/api-error";
import { asApiError } from "@/lib/api/api-error";
import type { Cart } from "@/types/commerce";
import { EMPTY_CART } from "./commerce-utils";

export type CartState =
  | { status: "signed-out" }
  | { status: "loading" }
  | { status: "ready"; cart: Cart; userId: string }
  | { status: "error"; error: ApiError; userId: string };

interface CartContextValue {
  state: CartState;
  pendingVariantIds: ReadonlySet<string>;
  refresh: () => Promise<Cart | null>;
  addItem: (variantId: string, quantity: number) => Promise<Cart>;
  updateItem: (variantId: string, quantity: number) => Promise<Cart>;
  removeItem: (variantId: string) => Promise<Cart>;
  clearAfterCheckout: () => void;
}

const CartContext = createContext<CartContextValue | null>(null);

function missingSessionError(): ApiError {
  return asApiError(new Error("Bạn cần đăng nhập để sử dụng giỏ hàng."));
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  const token = session?.token ?? null;
  const userId = session?.user.id ?? null;
  const [state, setState] = useState<CartState>({ status: "signed-out" });
  const [pendingVariantIds, setPendingVariantIds] = useState<Set<string>>(
    () => new Set(),
  );

  const loadCart = useCallback(
    (signal?: AbortSignal): Promise<Cart | null> => {
      if (!token) {
        return Promise.resolve(null);
      }
      return getCart(token, signal)
        .then((cart) => {
          if (userId) setState({ status: "ready", cart, userId });
          return cart;
        })
        .catch((error: unknown) => {
          if (!signal?.aborted && userId) {
            setState({ status: "error", error: asApiError(error), userId });
          }
          return null;
        });
    },
    [token, userId],
  );

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    void loadCart(controller.signal);
    return () => controller.abort();
  }, [loadCart, token]);

  const runVariantMutation = useCallback(
    async (
      variantId: string,
      operation: (activeToken: string) => Promise<Cart>,
    ): Promise<Cart> => {
      if (!token || !userId) throw missingSessionError();
      setPendingVariantIds((current) => new Set(current).add(variantId));
      try {
        const cart = await operation(token);
        setState({ status: "ready", cart, userId });
        return cart;
      } finally {
        setPendingVariantIds((current) => {
          const next = new Set(current);
          next.delete(variantId);
          return next;
        });
      }
    },
    [token, userId],
  );

  const visibleState = useMemo<CartState>(
    () =>
      !userId
        ? { status: "signed-out" }
        : (state.status === "ready" || state.status === "error") &&
            state.userId === userId
          ? state
          : { status: "loading" },
    [state, userId],
  );

  const value = useMemo<CartContextValue>(
    () => ({
      state: visibleState,
      pendingVariantIds: userId ? pendingVariantIds : new Set<string>(),
      refresh: () => loadCart(),
      addItem: (variantId, quantity) =>
        runVariantMutation(variantId, (activeToken) =>
          addCartItem(activeToken, variantId, quantity),
        ),
      updateItem: (variantId, quantity) =>
        runVariantMutation(variantId, (activeToken) =>
          updateCartItem(activeToken, variantId, quantity),
        ),
      removeItem: (variantId) =>
        runVariantMutation(variantId, async (activeToken) => {
          await removeCartItem(activeToken, variantId);
          return getCart(activeToken);
        }),
      clearAfterCheckout: () => {
        if (userId) setState({ status: "ready", cart: EMPTY_CART, userId });
      },
    }),
    [loadCart, pendingVariantIds, runVariantMutation, userId, visibleState],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart phải được dùng bên trong CartProvider.");
  }
  return context;
}

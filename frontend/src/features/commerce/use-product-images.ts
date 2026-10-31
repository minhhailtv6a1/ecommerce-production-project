"use client";

import { useEffect, useMemo, useState } from "react";
import { getProduct } from "@/lib/api/products.api";
import type { ProductImage } from "@/types/product";

interface ProductImageSource {
  product_id: string;
  product_slug?: string;
}

interface ProductImageState {
  requestKey: string;
  images: Record<string, ProductImage | null>;
}

export function useProductImages(items: readonly ProductImageSource[]) {
  const requests = useMemo(() => {
    const unique = new Map<string, string>();
    for (const item of items) {
      if (!unique.has(item.product_id)) {
        unique.set(item.product_id, item.product_slug ?? item.product_id);
      }
    }
    return Array.from(unique.entries());
  }, [items]);
  const requestKey = JSON.stringify(requests);
  const [state, setState] = useState<ProductImageState>({
    requestKey: "",
    images: {},
  });

  useEffect(() => {
    if (requests.length === 0) return;
    const controller = new AbortController();
    void Promise.all(
      requests.map(async ([productId, identifier]) => {
        try {
          const product = await getProduct(identifier, controller.signal);
          return [productId, product.primary_image] as const;
        } catch {
          return [productId, null] as const;
        }
      }),
    ).then((entries) => {
      if (!controller.signal.aborted) {
        setState({ requestKey, images: Object.fromEntries(entries) });
      }
    });
    return () => controller.abort();
  }, [requestKey, requests]);

  return {
    images: state.requestKey === requestKey ? state.images : {},
    loading: requests.length > 0 && state.requestKey !== requestKey,
  };
}

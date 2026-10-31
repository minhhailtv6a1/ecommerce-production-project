import type { Metadata } from "next";
import { CartView } from "@/features/commerce/cart-view";

export const metadata: Metadata = {
  title: "Giỏ hàng",
  robots: { index: false, follow: false },
};

export default function CartPage() {
  return <CartView />;
}

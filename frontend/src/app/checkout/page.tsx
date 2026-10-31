import type { Metadata } from "next";
import { CheckoutView } from "@/features/commerce/checkout-view";

export const metadata: Metadata = {
  title: "Đặt hàng",
  robots: { index: false, follow: false },
};

export default function CheckoutPage() {
  return <CheckoutView />;
}

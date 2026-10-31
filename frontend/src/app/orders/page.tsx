import type { Metadata } from "next";
import { OrdersView } from "@/features/commerce/orders-view";

export const metadata: Metadata = {
  title: "Đơn hàng của tôi",
  robots: { index: false, follow: false },
};

export default function OrdersPage() {
  return <OrdersView />;
}

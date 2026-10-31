import type { Metadata } from "next";
import { OrderDetailView } from "@/features/commerce/order-detail-view";

export const metadata: Metadata = {
  title: "Chi tiết đơn hàng",
  robots: { index: false, follow: false },
};

export default async function OrderDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ orderId: string }>;
  searchParams: Promise<{ created?: string }>;
}) {
  const [{ orderId }, query] = await Promise.all([params, searchParams]);
  return <OrderDetailView orderId={orderId} justCreated={query.created === "1"} />;
}

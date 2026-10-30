import type { Metadata } from "next";
import { ProductDetailView } from "@/features/products/product-detail-view";

export const metadata: Metadata = {
  title: "Chi tiết sản phẩm",
};

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ identifier: string }>;
}) {
  const { identifier } = await params;
  return <ProductDetailView identifier={identifier} />;
}

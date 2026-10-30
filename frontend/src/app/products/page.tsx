import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogView } from "@/features/products/catalog-view";

export const metadata: Metadata = {
  title: "Catalog sản phẩm",
  description: "Khám phá, lọc và sắp xếp các sản phẩm tại Lumi Market.",
};

export default function ProductsPage() {
  return (
    <Suspense fallback={<div className="container page-section">Đang tải catalog…</div>}>
      <CatalogView />
    </Suspense>
  );
}

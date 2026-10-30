import type { Metadata } from "next";
import { VisualSearchView } from "@/features/visual-search/visual-search-view";

export const metadata: Metadata = {
  title: "Tìm sản phẩm bằng ảnh",
  description: "Tải ảnh lên và tìm sản phẩm tương đồng trong catalog.",
};

export default function VisualSearchPage() {
  return <VisualSearchView />;
}

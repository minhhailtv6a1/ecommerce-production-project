import type { Metadata } from "next";
import { HomeOverview } from "@/features/home/home-overview";

export const metadata: Metadata = {
  title: "Trang chủ",
};

export default function HomePage() {
  return <HomeOverview />;
}

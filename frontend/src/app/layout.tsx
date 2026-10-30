import type { Metadata } from "next";
import { Footer } from "@/components/layout/footer";
import { Header } from "@/components/layout/header";
import { AuthProvider } from "@/features/auth/auth-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Lumi Market | Tìm sản phẩm bằng hình ảnh",
    template: "%s | Lumi Market",
  },
  description:
    "Khám phá sản phẩm và tìm những món đồ tương tự chỉ từ một bức ảnh.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <AuthProvider>
          <Header />
          <main>{children}</main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}

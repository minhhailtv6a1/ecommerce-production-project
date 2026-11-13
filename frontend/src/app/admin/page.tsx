import { AdminGuard } from "@/features/admin/admin-guard";
import { ProductListView } from "@/features/admin/product-list-view";
export default function AdminPage() { return <AdminGuard><ProductListView /></AdminGuard>; }

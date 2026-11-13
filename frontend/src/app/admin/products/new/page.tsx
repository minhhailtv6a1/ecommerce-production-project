import { AdminGuard } from "@/features/admin/admin-guard";
import { ProductEditorView } from "@/features/admin/product-editor-view";
export default function NewAdminProductPage() { return <AdminGuard><ProductEditorView /></AdminGuard>; }

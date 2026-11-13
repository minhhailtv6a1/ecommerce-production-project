import { AdminGuard } from "@/features/admin/admin-guard";
import { ProductEditorView } from "@/features/admin/product-editor-view";
export default async function EditAdminProductPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <AdminGuard><ProductEditorView productId={id} /></AdminGuard>; }

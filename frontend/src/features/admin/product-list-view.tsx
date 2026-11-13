"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { categoryLabel } from "@/domain/categories";
import { useAuth } from "@/features/auth/auth-provider";
import { asApiError } from "@/lib/api/api-error";
import { listAdminProducts } from "@/lib/api/admin-catalog.api";
import { formatPrice } from "@/lib/format";
import type { AdminProductList, ProductStatus } from "@/types/admin-catalog";

export function ProductListView() {
  const { session } = useAuth();
  const [data, setData] = useState<AdminProductList | null>(null);
  const [status, setStatus] = useState<ProductStatus | "">("");
  const [keyword, setKeyword] = useState("");
  const [appliedKeyword, setAppliedKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session || session.user.role !== "admin") return;
    const controller = new AbortController();
    queueMicrotask(() => { setLoading(true); setError(null); });
    const query = new URLSearchParams({ page: String(page), limit: "20" });
    if (status) query.set("status", status);
    if (appliedKeyword) query.set("keyword", appliedKeyword);
    listAdminProducts(session.token, `?${query}`, controller.signal)
      .then(setData)
      .catch((caught) => { if (!controller.signal.aborted) setError(asApiError(caught).message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [session, status, appliedKeyword, page]);

  function search(event: FormEvent) { event.preventDefault(); setPage(1); setAppliedKeyword(keyword.trim()); }

  return <div className="admin-shell container">
    <header className="admin-heading"><div><p className="eyebrow">Catalog workspace</p><h1>Quản lý sản phẩm</h1><p>Theo dõi draft, trạng thái vector và tồn kho từ một nơi.</p></div><Link className="button button-primary" href="/admin/products/new">+ Thêm sản phẩm</Link></header>
    <form className="admin-toolbar" onSubmit={search}><input aria-label="Tìm sản phẩm" placeholder="Tìm theo tên, slug hoặc thương hiệu" value={keyword} onChange={(e) => setKeyword(e.target.value)} /><select aria-label="Lọc trạng thái" value={status} onChange={(e) => { setStatus(e.target.value as ProductStatus | ""); setPage(1); }}><option value="">Tất cả trạng thái</option><option value="draft">Draft</option><option value="published">Published</option><option value="archived">Archived</option></select><button className="button button-dark" type="submit">Tìm</button></form>
    {error ? <div className="inline-error" role="alert">{error}</div> : null}
    {loading ? <div className="admin-empty" role="status">Đang tải catalog…</div> : null}
    {!loading && data?.items.length === 0 ? <div className="admin-empty"><strong>Chưa có sản phẩm phù hợp</strong><p>Hãy tạo draft đầu tiên hoặc thay đổi bộ lọc.</p></div> : null}
    {!loading && data?.items.length ? <><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Ảnh</th><th>Sản phẩm</th><th>Danh mục</th><th>Giá từ</th><th>Tồn kho</th><th>Vector</th><th>Trạng thái</th><th><span className="sr-only">Thao tác</span></th></tr></thead><tbody>{data.items.map((item) => <tr key={item.id}><td>{item.primary_image_url ? <img className="admin-product-thumb" src={item.primary_image_url} alt={item.primary_image_alt ?? item.name} /* eslint-disable-line @next/next/no-img-element */ /> : <span className="admin-product-thumb placeholder" aria-label="Chưa có ảnh">◇</span>}</td><td><strong>{item.name}</strong><small>{item.slug}</small></td><td>{categoryLabel(item.category_id)}</td><td>{item.price_from === null ? "—" : formatPrice(item.price_from, item.currency)}</td><td>{item.inventory_total}</td><td><span className={`admin-badge index-${item.index_status ?? "none"}`}>{item.index_status === "indexed" ? "Đã nạp" : "Chưa nạp"}</span></td><td><span className={`admin-badge status-${item.status}`}>{item.status}</span></td><td><Link className="admin-icon-link" href={`/admin/products/${item.id}`} aria-label={`Xem chi tiết ${item.name}`} title="Xem chi tiết"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12s3-5 8-5 8 5 8 5-3 5-8 5-8-5-8-5Z"/><circle cx="12" cy="12" r="2.2"/></svg></Link></td></tr>)}</tbody></table></div><nav className="admin-pagination" aria-label="Phân trang sản phẩm"><button className="button button-secondary" disabled={page <= 1 || loading} onClick={() => setPage((value) => value - 1)}>← Trước</button><span>Trang <strong>{data.page}</strong> / {Math.max(data.pages, 1)} · {data.total} sản phẩm</span><button className="button button-secondary" disabled={page >= data.pages || loading} onClick={() => setPage((value) => value + 1)}>Sau →</button></nav></> : null}
  </div>;
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { CATEGORY_LABELS, categoryLabel, type CategoryId } from "@/domain/categories";
import { useAuth } from "@/features/auth/auth-provider";
import { asApiError } from "@/lib/api/api-error";
import {
  addAdminVariant, createAdminProduct, deactivateAdminVariant,
  deleteAdminImage, getAdminProduct, indexAdminProduct,
  lifecycleAdminProduct, updateAdminImage, updateAdminProduct, uploadAdminImage,
} from "@/lib/api/admin-catalog.api";
import { classifyImage, getClassifiers } from "@/lib/api/classification.api";
import type { AdminProduct } from "@/types/admin-catalog";
import type { ClassifierCapability, ClassifierModelId, ImageClassificationResponse } from "@/types/classification";
import { ClassificationResults } from "./classification/classification-results";
import { ClassifierModelSelect } from "./classification/classifier-model-select";

export function ProductEditorView({ productId }: { productId?: string }) {
  const isCreate = productId === undefined;
  const router = useRouter();
  const { session } = useAuth();
  const [product, setProduct] = useState<AdminProduct | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(!isCreate);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [brand, setBrand] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<CategoryId>("00");
  const [classifiers, setClassifiers] = useState<ClassifierCapability[]>([]);
  const [model, setModel] = useState<ClassifierModelId>("none");
  const [classification, setClassification] = useState<ImageClassificationResponse | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyMessage, setBusyMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sku, setSku] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("0");

  useEffect(() => {
    if (!session || session.user.role !== "admin") return;
    if (isCreate) {
      getClassifiers(session.token).then((result) => setClassifiers(result.items)).catch(() => setClassifiers([]));
      return;
    }
    let active = true;
    getAdminProduct(session.token, productId)
      .then((next) => {
        if (!active) return;
        load(next);
        const rawFlash = window.sessionStorage.getItem("admin-product-flash");
        if (rawFlash) {
          window.sessionStorage.removeItem("admin-product-flash");
          try {
            const flash = JSON.parse(rawFlash) as { id?: string; message?: string };
            if (flash.id === next.id && flash.message) setNotice(flash.message);
          } catch { /* Ignore invalid session-only feedback. */ }
        }
      })
      .catch((caught) => { if (active) setError(asApiError(caught).message); })
      .finally(() => { if (active) setLoadingDetail(false); });
    return () => { active = false; };
  }, [session, productId, isCreate]);

  useEffect(() => {
    if (!imageFile) { queueMicrotask(() => setImagePreviewUrl(null)); return; }
    const objectUrl = URL.createObjectURL(imageFile);
    queueMicrotask(() => setImagePreviewUrl(objectUrl));
    return () => URL.revokeObjectURL(objectUrl);
  }, [imageFile]);

  function load(next: AdminProduct) {
    setProduct(next); setName(next.name); setSlug(next.slug);
    setBrand(next.brand ?? ""); setDescription(next.description ?? "");
    setCategory(next.category_id);
  }
  function selectImage(file: File | null) {
    setError(null);
    if (!file) { setImageFile(null); return; }
    if (!new Set(["image/jpeg", "image/png", "image/webp"]).has(file.type)) {
      setError("Ảnh sản phẩm chỉ hỗ trợ JPEG, PNG hoặc WebP."); return;
    }
    if (file.size > 6 * 1024 * 1024) {
      setError("Ảnh sản phẩm không được vượt quá 6 MiB."); return;
    }
    setImageFile(file); setClassification(null);
  }
  async function run(operation: () => Promise<AdminProduct>, message: string, pendingMessage = "Đang xử lý yêu cầu…") {
    setBusy(true); setBusyMessage(pendingMessage); setError(null);
    try { load(await operation()); setNotice(message); }
    catch (caught) { setError(asApiError(caught).message); }
    finally { setBusy(false); setBusyMessage(null); }
  }
  async function refreshAfter(operation: () => Promise<unknown>, message: string) {
    if (!session || !product) return;
    setBusy(true); setError(null);
    try { await operation(); load(await getAdminProduct(session.token, product.id)); setNotice(message); }
    catch (caught) { setError(asApiError(caught).message); }
    finally { setBusy(false); }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!session) return;
    const input = { name, slug, brand: brand || null, description: description || null, category_id: category, currency: "VND" };
    if (product) { await run(() => updateAdminProduct(session.token, product.id, product.version, input), "Đã lưu thay đổi."); return; }
    setBusy(true); setBusyMessage("Đang tạo bản nháp và tải ảnh sản phẩm…"); setError(null);
    try {
      const created = await createAdminProduct(session.token, input);
      let flash = "Đã tạo bản nháp sản phẩm.";
      if (imageFile) {
        try {
          await uploadAdminImage(session.token, created.id, imageFile, created.name, true);
          flash = "Đã tạo bản nháp và tải ảnh chính thành công.";
        } catch (uploadError) {
          flash = `Đã tạo bản nháp nhưng tải ảnh thất bại: ${asApiError(uploadError).message}`;
        }
      }
      window.sessionStorage.setItem("admin-product-flash", JSON.stringify({ id: created.id, message: flash }));
      router.replace(`/admin/products/${created.id}`);
    } catch (caught) { setError(asApiError(caught).message); }
    finally { setBusy(false); setBusyMessage(null); }
  }
  async function predict() {
    if (!session || !imageFile || model === "none") return;
    setBusy(true); setBusyMessage("Đang chạy model phân loại ảnh…"); setError(null);
    try {
      const result = await classifyImage({ image: imageFile, modelId: model, topK: 5 }, session.token);
      setClassification(result); setCategory(result.suggested_category_id);
      setNotice("Model đã gợi ý danh mục. Hãy xác nhận trước khi tạo sản phẩm.");
    } catch (caught) { setError(asApiError(caught).message); }
    finally { setBusy(false); setBusyMessage(null); }
  }
  async function addVariant(event: FormEvent) {
    event.preventDefault(); if (!session || !product) return;
    await refreshAfter(
      () => addAdminVariant(session.token, product.id, { sku, price: Number(price), inventory_quantity: Number(stock), is_active: true }),
      "Đã thêm variant.",
    );
    setSku(""); setPrice(""); setStock("0");
  }
  async function upload(event: FormEvent) {
    event.preventDefault(); if (!session || !product || !imageFile) return;
    await refreshAfter(
      () => uploadAdminImage(session.token, product.id, imageFile, name || "Ảnh sản phẩm", product.images.length === 0),
      "Đã tải ảnh lên Storage.",
    );
    setImageFile(null);
  }

  if (!session || session.user.role !== "admin") return null;
  if (!isCreate && loadingDetail) return <ProductDetailSkeleton />;

  const messages = <>{notice ? <div className="admin-notice" role="status">{notice}</div> : null}{busyMessage ? <div className="admin-operation-notice" role="status"><span className="admin-operation-spinner" aria-hidden="true" /><div><strong>{busyMessage}</strong><small>Không đóng trang trong lúc hệ thống đang hoàn tất thao tác.</small></div></div> : null}{error ? <div className="inline-error" role="alert">{error}</div> : null}</>;
  if (isCreate) return <div className="admin-shell container">
    <header className="admin-heading"><div><Link className="back-link" href="/admin">← Catalog</Link><p className="eyebrow">New product</p><h1>Tạo sản phẩm mới</h1><p>Nhập thông tin cơ bản hoặc dùng AI để tham khảo category trước khi tạo draft.</p></div></header>
    {messages}
    <div className="admin-create-grid">
      <ProductForm name={name} slug={slug} brand={brand} description={description} category={category} busy={busy} locked={false} submitLabel="Tạo sản phẩm draft" onName={setName} onSlug={setSlug} onBrand={setBrand} onDescription={setDescription} onCategory={setCategory} onSubmit={save} />
      <aside className="admin-card admin-ai-card"><div className="admin-card-heading"><span className="admin-card-icon">IMG</span><div><h2>Ảnh sản phẩm & AI</h2><p>Ảnh đã chọn sẽ được lưu làm ảnh chính của bản nháp</p></div></div>{imagePreviewUrl ? <div className="admin-create-image-preview"><img src={imagePreviewUrl} alt="Ảnh sản phẩm đã chọn" /* eslint-disable-line @next/next/no-img-element */ /><button className="text-button danger" type="button" onClick={() => selectImage(null)}>Bỏ ảnh</button></div> : <div className="admin-create-image-empty"><span aria-hidden="true">＋</span><strong>Chọn ảnh sản phẩm</strong><small>JPEG, PNG hoặc WebP · tối đa 6 MiB</small></div>}<label className="admin-file">Chọn hoặc thay ảnh<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => selectImage(event.target.files?.[0] ?? null)} /></label><ClassifierModelSelect classifiers={classifiers} value={model} loading={false} disabled={busy} onChange={setModel} /><button className="button button-dark button-block" type="button" disabled={busy || !imageFile || model === "none"} onClick={predict}>Dùng AI gợi ý danh mục</button>{classification ? <ClassificationResults data={classification} selectedCategory={category} onSelectCategory={(id) => setCategory(id as CategoryId)} /> : <div className="admin-ai-empty"><strong>AI là tùy chọn</strong><span>Bạn vẫn có thể chọn category thủ công và tạo sản phẩm cùng ảnh đã chọn.</span></div>}</aside>
    </div>
  </div>;

  if (!product) return <section className="admin-gate"><p className="eyebrow">Không thể mở sản phẩm</p><h1>{error ?? "Không tìm thấy dữ liệu sản phẩm"}</h1><Link className="button button-secondary" href="/admin">Quay lại catalog</Link></section>;

  const needsIndex = product.images.some((image) => image.is_primary && image.index_status !== "indexed");
  const primary = product.images.find((image) => image.is_primary);
  return <div className="admin-shell container">
    <header className="admin-heading admin-detail-heading">
      <div><Link className="back-link" href="/admin">← Catalog</Link><p className="eyebrow">Chi tiết sản phẩm · {product.status}</p><h1>{product.name}</h1><p>{categoryLabel(product.category_id)} · phiên bản {product.version}</p></div>
      <div className="admin-actions">
        {needsIndex && product.status !== "archived" ? <button className="button button-dark" disabled={busy} onClick={() => run(() => indexAdminProduct(session.token, product.id), "Đã nạp ảnh chính vào vector database.", "Đang khởi tạo CLIP và nạp ảnh vào vector database…")}>Nạp vào vector database</button> : null}
        {product.status === "archived" ? <button className="button button-secondary" disabled={busy} onClick={() => run(() => lifecycleAdminProduct(session.token, product.id, "restore"), "Đã khôi phục về bản nháp.")}>{busy ? "Đang khôi phục…" : "Khôi phục bản nháp"}</button> : null}
        <button className="button button-secondary" disabled={busy || product.status === "archived"} title={product.status === "archived" ? "Sản phẩm đã ngừng bán" : undefined} onClick={() => run(() => lifecycleAdminProduct(session.token, product.id, "archive"), "Đã ngừng bán sản phẩm.")}>{busy ? "Đang xử lý…" : product.status === "archived" ? "Đã ngừng bán" : "Ngừng bán"}</button>
        <button className="button button-primary" disabled={busy || product.status !== "draft"} title={product.status === "archived" ? "Khôi phục bản nháp trước khi đăng bán lại" : product.status === "published" ? "Sản phẩm đang được đăng bán" : undefined} onClick={() => run(() => lifecycleAdminProduct(session.token, product.id, "publish"), "Đăng bán thành công.", "Đang kiểm tra dữ liệu, khởi tạo CLIP và nạp vector… Lần đầu có thể mất 30–60 giây.")}>{busy ? "Đang xử lý…" : product.status === "published" ? "Đã đăng bán" : "Đăng bán"}</button>
      </div>
    </header>
    {messages}
    {product.status === "archived" ? <div className="admin-archive-notice" role="status"><strong>Sản phẩm đang ngừng bán</strong><span>Hãy bấm “Khôi phục bản nháp” trước khi sửa thông tin, thêm variant, quản lý ảnh hoặc đăng bán lại.</span></div> : null}
    <div className="admin-detail-grid">
      <div className="admin-detail-main">
        <ProductForm name={name} slug={slug} brand={brand} description={description} category={category} busy={busy} locked={product.status === "archived"} submitLabel="Lưu thay đổi" onName={setName} onSlug={setSlug} onBrand={setBrand} onDescription={setDescription} onCategory={setCategory} onSubmit={save} />
        <section className="admin-card"><div className="admin-card-heading"><span className="admin-card-icon">SKU</span><div><h2>Variants</h2><p>{product.variants.length} phiên bản sản phẩm</p></div></div><form className="admin-inline-form" onSubmit={addVariant}><input aria-label="SKU" placeholder="SKU" value={sku} required disabled={product.status === "archived"} onChange={(event) => setSku(event.target.value)} /><input aria-label="Giá" placeholder="Giá" type="number" min="0" value={price} required disabled={product.status === "archived"} onChange={(event) => setPrice(event.target.value)} /><input aria-label="Tồn kho" placeholder="Tồn kho" type="number" min="0" value={stock} required disabled={product.status === "archived"} onChange={(event) => setStock(event.target.value)} /><button className="button button-primary" disabled={busy || product.status === "archived"}>Thêm</button></form><div className="admin-stack">{product.variants.map((variant) => <article key={variant.id}><div><strong>{variant.sku}</strong><small>{variant.price.toLocaleString("vi-VN")} ₫ · tồn {variant.inventory_quantity} · {variant.is_active ? "đang bán" : "đã tắt"}</small></div><button className="text-button" disabled={!variant.is_active || busy || product.status === "archived"} onClick={() => refreshAfter(() => deactivateAdminVariant(session.token, product.id, variant.id), "Đã vô hiệu hóa variant.")}>Vô hiệu hóa</button></article>)}</div></section>
      </div>
      <aside className="admin-detail-side">
        <section className="admin-card admin-overview-card">{primary?.url ? <img src={primary.url} alt={primary.alt_text} /* eslint-disable-line @next/next/no-img-element */ /> : <div className="admin-overview-placeholder">Chưa có ảnh chính</div>}<div className="admin-overview-stats"><div><span>Trạng thái</span><strong>{product.status}</strong></div><div><span>Vector</span><strong>{primary?.index_status === "indexed" ? "Đã nạp" : "Chưa nạp"}</strong></div><div><span>Tồn kho</span><strong>{product.variants.reduce((total, item) => total + item.inventory_quantity, 0)}</strong></div></div></section>
        <section className="admin-card"><div className="admin-card-heading"><span className="admin-card-icon">IMG</span><div><h2>Hình ảnh</h2><p>{product.images.length} ảnh trong Storage</p></div></div><form className="admin-upload-form" onSubmit={upload}><input type="file" accept="image/jpeg,image/png,image/webp" required disabled={product.status === "archived"} onChange={(event) => selectImage(event.target.files?.[0] ?? null)} /><button className="button button-primary" disabled={busy || product.status === "archived"}>Tải ảnh</button></form><div className="admin-image-grid">{product.images.map((image) => <article key={image.id}>{image.url ? <img src={image.url} alt={image.alt_text} /* eslint-disable-line @next/next/no-img-element */ /> : <div className="image-placeholder">No preview</div>}<strong>{image.is_primary ? "Ảnh chính" : "Ảnh phụ"}</strong><small>{image.index_status}{image.index_error ? ` · ${image.index_error}` : ""}</small><div>{!image.is_primary ? <button className="text-button" disabled={product.status !== "draft" || busy} onClick={() => refreshAfter(() => updateAdminImage(session.token, product.id, image.id, { is_primary: true }), "Đã đổi ảnh chính.")}>Đặt làm chính</button> : null}{!image.is_primary ? <button className="text-button danger" disabled={busy || product.status === "archived"} onClick={() => refreshAfter(() => deleteAdminImage(session.token, product.id, image.id), "Đã xóa ảnh.")}>Xóa</button> : null}</div></article>)}</div></section>
      </aside>
    </div>
  </div>;
}

interface ProductFormProps {
  name: string; slug: string; brand: string; description: string; category: CategoryId;
  busy: boolean; locked: boolean; submitLabel: string; onName: (value: string) => void;
  onSlug: (value: string) => void; onBrand: (value: string) => void;
  onDescription: (value: string) => void; onCategory: (value: CategoryId) => void;
  onSubmit: (event: FormEvent) => void;
}
function ProductForm(props: ProductFormProps) {
  return <section className="admin-card"><div className="admin-card-heading"><span className="admin-card-icon">01</span><div><h2>Thông tin sản phẩm</h2><p>Dữ liệu authoritative lưu tại PostgreSQL</p></div></div><form className="admin-form" onSubmit={props.onSubmit}><label>Tên<input value={props.name} required disabled={props.locked} onChange={(event) => props.onName(event.target.value)} /></label><label>Slug<input value={props.slug} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" required disabled={props.locked} onChange={(event) => props.onSlug(event.target.value)} /></label><label>Thương hiệu<input value={props.brand} disabled={props.locked} onChange={(event) => props.onBrand(event.target.value)} /></label><label>Danh mục<select value={props.category} disabled={props.locked} onChange={(event) => props.onCategory(event.target.value as CategoryId)}>{Object.entries(CATEGORY_LABELS).map(([id, label]) => <option key={id} value={id}>{id} · {label}</option>)}</select></label><label className="span-2">Mô tả<textarea rows={5} value={props.description} disabled={props.locked} onChange={(event) => props.onDescription(event.target.value)} /></label><button className="button button-primary span-2" disabled={props.busy || props.locked}>{props.submitLabel}</button></form></section>;
}

function ProductDetailSkeleton() {
  return <div className="admin-shell container" aria-busy="true" aria-label="Đang tải chi tiết sản phẩm"><div className="admin-detail-loading"><span /><span /><span /></div><div className="admin-detail-grid"><div className="admin-detail-main"><div className="admin-card admin-skeleton-card" /><div className="admin-card admin-skeleton-card short" /></div><aside className="admin-detail-side"><div className="admin-card admin-skeleton-card image" /><div className="admin-card admin-skeleton-card short" /></aside></div></div>;
}

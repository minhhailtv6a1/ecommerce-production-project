"use client";

import Link from "next/link";
import { useState } from "react";
import type { ProductImage } from "@/types/product";

export function ProductThumbnail({
  image,
  loading,
  productName,
  href,
}: {
  image: ProductImage | null | undefined;
  loading: boolean;
  productName: string;
  href: string;
}) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const imageAvailable = image && failedUrl !== image.url;

  const content = imageAvailable ? (
    // Signed Storage hosts vary by environment, so the URL is used unchanged.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={image.url}
      alt={image.alt || productName}
      onError={() => setFailedUrl(image.url)}
    />
  ) : loading ? (
    <span className="commerce-thumb-skeleton skeleton" aria-hidden="true" />
  ) : (
    <span className="commerce-thumb-fallback" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none">
        <path
          d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11Z"
          stroke="currentColor"
          strokeWidth="1.6"
        />
        <path
          d="m5 17 4.2-4.2a1.5 1.5 0 0 1 2.12 0L13 14.48l1.18-1.18a1.5 1.5 0 0 1 2.12 0L20 17M15.5 9.5h.01"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );

  return (
    <Link
      className="commerce-product-thumb"
      href={href}
      aria-label={`Xem ${productName}`}
    >
      {content}
    </Link>
  );
}

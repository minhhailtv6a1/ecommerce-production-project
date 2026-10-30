const vndFormatter = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

export function formatPrice(value: number, currency: string): string {
  if (currency === "VND") {
    return vndFormatter.format(value);
  }
  return `${new Intl.NumberFormat("vi-VN").format(value)} ${currency}`;
}

export function formatSimilarity(score: number): string {
  return new Intl.NumberFormat("vi-VN", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(Math.max(0, score));
}

export function formatRetrievalTime(milliseconds: number): string {
  const safeMilliseconds = Math.max(0, milliseconds);
  return `${new Intl.NumberFormat("vi-VN", {
    maximumFractionDigits: 2,
  }).format(safeMilliseconds)} ms`;
}

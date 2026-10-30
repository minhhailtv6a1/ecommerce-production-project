export const VISUAL_SEARCH_PAGE_SIZE = 20;

export interface VisualSearchPage<T> {
  items: T[];
  page: number;
  pages: number;
  total: number;
}

export function paginateVisualSearchItems<T>(
  items: T[],
  requestedPage: number,
  pageSize = VISUAL_SEARCH_PAGE_SIZE,
): VisualSearchPage<T> {
  if (!Number.isInteger(pageSize) || pageSize <= 0) {
    throw new Error("pageSize must be a positive integer");
  }

  const pages = Math.ceil(items.length / pageSize);
  const page = pages === 0
    ? 1
    : Math.min(Math.max(1, Math.trunc(requestedPage)), pages);
  const start = (page - 1) * pageSize;

  return {
    items: items.slice(start, start + pageSize),
    page,
    pages,
    total: items.length,
  };
}

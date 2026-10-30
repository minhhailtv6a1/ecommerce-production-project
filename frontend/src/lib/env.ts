const LOCAL_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return (configured || LOCAL_API_BASE_URL).replace(/\/+$/, "");
}

export const SHOW_TEST_CATEGORIES =
  process.env.NEXT_PUBLIC_SHOW_TEST_CATEGORIES !== "false";

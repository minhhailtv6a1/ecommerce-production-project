import { getApiBaseUrl } from "@/lib/env";
import { parseApiError } from "./api-error";

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | object;
  token?: string | null;
}

function apiUrl(path: string): string {
  return `${getApiBaseUrl()}/${path.replace(/^\/+/, "")}`;
}

export async function requestJson(
  path: string,
  options: ApiRequestOptions = {},
): Promise<unknown> {
  const { body, token, headers: customHeaders, ...init } = options;
  const headers = new Headers(customHeaders);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let requestBody: BodyInit | undefined;
  if (body instanceof FormData) {
    requestBody = body;
  } else if (body !== undefined) {
    headers.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers,
      body: requestBody,
      cache: "no-store",
    });
  } catch (error) {
    throw parseApiError(error, null);
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : null;

  if (!response.ok) {
    throw parseApiError(payload, response.status);
  }
  return payload;
}

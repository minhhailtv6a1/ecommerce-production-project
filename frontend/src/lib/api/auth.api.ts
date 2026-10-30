import type { AuthCredentials, AuthUser, TokenResponse } from "@/types/auth";
import { requestJson } from "./http-client";
import {
  booleanValue,
  invalidResponse,
  numberValue,
  record,
  stringValue,
} from "./parse";

function parseUser(value: unknown): AuthUser {
  const data = record(value, "người dùng");
  return {
    id: stringValue(data.id, "user.id"),
    email: stringValue(data.email, "user.email"),
    is_active: booleanValue(data.is_active, "user.is_active"),
    created_at: stringValue(data.created_at, "user.created_at"),
  };
}

function parseToken(value: unknown): TokenResponse {
  const data = record(value, "xác thực");
  const tokenType = stringValue(data.token_type, "auth.token_type");
  if (tokenType !== "bearer") {
    return invalidResponse("Backend trả về token_type không được hỗ trợ.");
  }
  return {
    access_token: stringValue(data.access_token, "auth.access_token"),
    token_type: tokenType,
    expires_in: numberValue(data.expires_in, "auth.expires_in"),
    user: parseUser(data.user),
  };
}

async function authenticate(
  path: "/auth/login" | "/auth/register",
  credentials: AuthCredentials,
  signal?: AbortSignal,
): Promise<TokenResponse> {
  return parseToken(
    await requestJson(path, {
      method: "POST",
      body: credentials,
      signal,
    }),
  );
}

export function login(credentials: AuthCredentials, signal?: AbortSignal) {
  return authenticate("/auth/login", credentials, signal);
}

export function register(credentials: AuthCredentials, signal?: AbortSignal) {
  return authenticate("/auth/register", credentials, signal);
}

export async function getMe(token: string, signal?: AbortSignal): Promise<AuthUser> {
  return parseUser(await requestJson("/auth/me", { token, signal }));
}

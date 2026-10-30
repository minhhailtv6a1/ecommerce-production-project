import { ApiError } from "./api-error";

export function invalidResponse(message: string): never {
  throw new ApiError(
    {
      code: "INVALID_RESPONSE",
      message,
      field_errors: {},
      request_id: null,
    },
    null,
  );
}

export function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidResponse(`Phản hồi ${label} không đúng định dạng.`);
  }
  return value as Record<string, unknown>;
}

export function stringValue(value: unknown, field: string): string {
  if (typeof value !== "string") {
    return invalidResponse(`Trường ${field} không đúng định dạng.`);
  }
  return value;
}

export function nullableString(
  value: unknown,
  field: string,
): string | null {
  if (value === null) return null;
  return stringValue(value, field);
}

export function numberValue(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return invalidResponse(`Trường ${field} không đúng định dạng.`);
  }
  return value;
}

export function nullableNumber(
  value: unknown,
  field: string,
): number | null {
  if (value === null) return null;
  return numberValue(value, field);
}

export function booleanValue(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") {
    return invalidResponse(`Trường ${field} không đúng định dạng.`);
  }
  return value;
}

export function arrayValue(value: unknown, field: string): unknown[] {
  if (!Array.isArray(value)) {
    return invalidResponse(`Trường ${field} không đúng định dạng.`);
  }
  return value;
}

export function stringArray(value: unknown, field: string): string[] {
  return arrayValue(value, field).map((item, index) =>
    stringValue(item, `${field}.${index}`),
  );
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  field_errors: Record<string, string>;
  request_id: string | null;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly fieldErrors: Record<string, string>;
  readonly requestId: string | null;

  constructor(payload: ApiErrorPayload, status: number | null) {
    super(payload.message);
    this.name = "ApiError";
    this.code = payload.code;
    this.status = status;
    this.fieldErrors = payload.field_errors;
    this.requestId = payload.request_id;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseFieldErrors(value: unknown): Record<string, string> {
  if (!isRecord(value)) return {};
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, detail]) =>
      typeof detail === "string" ? [[key, detail]] : [],
    ),
  );
}

export function parseApiError(
  value: unknown,
  status: number | null,
): ApiError {
  if (status === null) {
    return new ApiError(
      {
        code: "NETWORK_ERROR",
        message: "Cửa hàng đang tạm thời gián đoạn. Vui lòng thử lại sau ít phút.",
        field_errors: {},
        request_id: null,
      },
      null,
    );
  }

  if (isRecord(value)) {
    const message =
      typeof value.message === "string"
        ? value.message
        : typeof value.detail === "string"
          ? value.detail
          : "Yêu cầu không thành công.";
    return new ApiError(
      {
        code:
          typeof value.code === "string"
            ? value.code
            : `HTTP_${status}`,
        message,
        field_errors: parseFieldErrors(value.field_errors),
        request_id:
          typeof value.request_id === "string" ? value.request_id : null,
      },
      status,
    );
  }

  return new ApiError(
    {
      code: `HTTP_${status}`,
      message: "Máy chủ trả về phản hồi không hợp lệ.",
      field_errors: {},
      request_id: null,
    },
    status,
  );
}

export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError(
      {
        code: "ABORTED",
        message: "Yêu cầu đã được hủy.",
        field_errors: {},
        request_id: null,
      },
      null,
    );
  }
  return parseApiError(error, null);
}

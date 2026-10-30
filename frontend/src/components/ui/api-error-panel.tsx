import type { ApiError } from "@/lib/api/api-error";

export function ApiErrorPanel({
  error,
  onRetry,
  title = "Không thể tải dữ liệu",
}: {
  error: ApiError;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div className="state-panel state-error" role="alert">
      <span className="state-icon" aria-hidden="true">
        !
      </span>
      <div>
        <h3>{title}</h3>
        <p>{error.message}</p>
        {error.requestId ? (
          <p className="request-id">Mã hỗ trợ: {error.requestId}</p>
        ) : null}
        {onRetry ? (
          <button className="button button-secondary" type="button" onClick={onRetry}>
            Thử lại
          </button>
        ) : null}
      </div>
    </div>
  );
}

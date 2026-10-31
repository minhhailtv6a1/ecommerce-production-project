"""FastAPI application entry point."""

import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.commerce import router as commerce_router
from app.api.routes.categories import router as categories_router
from app.api.routes.health import router as health_router
from app.api.routes.image_search import router as image_search_router
from app.api.routes.image_classification import router as image_classification_router
from app.api.routes.products import router as products_router
from app.core.config import settings


logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def attach_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    structured_detail = exc.detail if isinstance(exc.detail, dict) else None
    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else str(structured_detail.get("message", "Request failed"))
        if structured_detail is not None
        else "Request failed"
    )
    code = (
        str(structured_detail.get("code"))
        if structured_detail is not None and structured_detail.get("code")
        else _error_code(exc.status_code)
    )
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content=_error_payload(
            request,
            code=code,
            message=message,
        ),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    field_errors = {
        ".".join(str(part) for part in error["loc"] if part != "body"): error[
            "msg"
        ]
        for error in exc.errors()
    }
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            request,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            field_errors=field_errors,
        ),
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled API error (request_id=%s)", request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            request,
            code="INTERNAL_ERROR",
            message="An unexpected server error occurred",
        ),
    )


def _error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    field_errors: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "field_errors": field_errors or {},
        "request_id": getattr(request.state, "request_id", str(uuid4())),
    }


def _error_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, f"HTTP_{status_code}")


app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(categories_router, prefix=settings.api_prefix)
app.include_router(products_router, prefix=settings.api_prefix)
app.include_router(commerce_router, prefix=settings.api_prefix)
app.include_router(image_search_router, prefix=settings.api_prefix)
app.include_router(image_classification_router, prefix=settings.api_prefix)

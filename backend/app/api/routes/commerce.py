"""Authenticated cart and order endpoints."""

from collections.abc import Callable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_commerce_service
from app.api.routes.auth import require_current_user
from app.repositories.commerce import (
    CartItemUnavailableError,
    CommerceRepositoryError,
    EmptyCartError,
    MixedCurrencyCartError,
)
from app.repositories.users import UserRecord
from app.schemas.commerce import (
    AddCartItemRequest,
    CartResponse,
    CheckoutRequest,
    OrderListResponse,
    OrderResponse,
    UpdateCartItemRequest,
)
from app.services.commerce import (
    CartItemNotFoundError,
    CartQuantityLimitError,
    CommerceService,
    InsufficientStockError,
    OrderNotFoundError,
    VariantUnavailableError,
)


router = APIRouter(tags=["commerce"])
T = TypeVar("T")


@router.get("/cart", response_model=CartResponse)
def get_cart(
    user: Annotated[UserRecord, Depends(require_current_user)],
    service: Annotated[CommerceService, Depends(get_commerce_service)],
) -> CartResponse:
    return _run(lambda: service.get_cart(user.id))


@router.post("/cart/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    request: AddCartItemRequest,
    user: Annotated[UserRecord, Depends(require_current_user)],
    service: Annotated[CommerceService, Depends(get_commerce_service)],
) -> CartResponse:
    return _run(lambda: service.add_cart_item(user.id, request.variant_id, request.quantity))


@router.patch("/cart/items/{variant_id}", response_model=CartResponse)
def update_cart_item(
    variant_id: UUID,
    request: UpdateCartItemRequest,
    user: Annotated[UserRecord, Depends(require_current_user)],
    service: Annotated[CommerceService, Depends(get_commerce_service)],
) -> CartResponse:
    return _run(lambda: service.update_cart_item(user.id, variant_id, request.quantity))


@router.delete("/cart/items/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cart_item(
    variant_id: UUID,
    user: Annotated[UserRecord, Depends(require_current_user)],
    service: Annotated[CommerceService, Depends(get_commerce_service)],
) -> Response:
    _run(lambda: service.remove_cart_item(user.id, variant_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def checkout(
    request: CheckoutRequest,
    user: Annotated[UserRecord, Depends(require_current_user)],
    service: Annotated[CommerceService, Depends(get_commerce_service)],
) -> OrderResponse:
    return _run(lambda: service.checkout(user.id, request))


@router.get("/orders", response_model=OrderListResponse)
def list_orders(
    user: Annotated[UserRecord, Depends(require_current_user)],
    service: Annotated[CommerceService, Depends(get_commerce_service)],
) -> OrderListResponse:
    return _run(lambda: service.list_orders(user.id))


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    user: Annotated[UserRecord, Depends(require_current_user)],
    service: Annotated[CommerceService, Depends(get_commerce_service)],
) -> OrderResponse:
    return _run(lambda: service.get_order(user.id, order_id))


def _run(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except (VariantUnavailableError, CartItemUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product variant is no longer available",
        ) from exc
    except InsufficientStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested quantity exceeds available stock",
        ) from exc
    except CartQuantityLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cart item quantity cannot exceed 99",
        ) from exc
    except EmptyCartError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cart is empty",
        ) from exc
    except MixedCurrencyCartError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cart items must use one currency",
        ) from exc
    except CartItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        ) from exc
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        ) from exc
    except CommerceRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cart and order database is unavailable",
        ) from exc

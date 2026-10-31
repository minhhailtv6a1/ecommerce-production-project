import { orderStatusLabel } from "./commerce-utils";
import type { OrderStatus } from "@/types/commerce";

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={`order-status status-${status}`}>
      {orderStatusLabel(status)}
    </span>
  );
}

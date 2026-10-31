export interface CartItem {
  variant_id: string;
  product_id: string;
  product_name: string;
  product_slug: string;
  sku: string;
  color: string | null;
  size: string | null;
  unit_price: number;
  currency: string;
  quantity: number;
  inventory_quantity: number;
  available: boolean;
  line_total: number;
}

export interface Cart {
  items: CartItem[];
  item_count: number;
  subtotal: number;
  currency: string | null;
}

export interface CheckoutInput {
  receiver_name: string;
  phone: string;
  shipping_address: string;
  note?: string | null;
}

export type OrderStatus =
  | "pending"
  | "confirmed"
  | "shipping"
  | "completed"
  | "cancelled";

export interface OrderItem {
  id: string;
  product_id: string;
  variant_id: string;
  product_name: string;
  sku: string;
  color: string | null;
  size: string | null;
  unit_price: number;
  quantity: number;
  line_total: number;
}

export interface Order {
  id: string;
  status: OrderStatus;
  payment_method: "cod";
  receiver_name: string;
  phone: string;
  shipping_address: string;
  note: string | null;
  total_amount: number;
  currency: string;
  created_at: string;
  items: OrderItem[];
}

export interface OrderListResponse {
  items: Order[];
}

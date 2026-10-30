"use server";

import { redirect } from "next/navigation";

import {
  ApiError,
  addToCart as apiAddToCart,
  placeOrder as apiPlaceOrder,
  removeFromCart as apiRemoveFromCart,
} from "@/lib/api";
import { getCartKey, getOrCreateCartKey } from "@/lib/session";

const field = (formData, name) => String(formData.get(name) ?? "").trim();

// redirect() бросает специальное исключение, поэтому вызываем его вне блока try.
export async function addToCart(formData) {
  const productId = field(formData, "productId");
  const cartKey = await getOrCreateCartKey();
  try {
    await apiAddToCart(cartKey, productId);
  } catch (e) {
    if (e instanceof ApiError) {
      redirect(`/products/${productId}?error=${encodeURIComponent(e.message)}`);
    }
    throw e;
  }
  redirect("/cart");
}

export async function removeFromCart(formData) {
  const cartKey = await getCartKey();
  if (cartKey) await apiRemoveFromCart(cartKey, field(formData, "productId"));
  redirect("/cart");
}

export async function placeOrder(formData) {
  const cartKey = await getCartKey();
  if (!cartKey) redirect("/cart");

  let orderId;
  try {
    const order = await apiPlaceOrder(
      cartKey,
      {
        customer_name: field(formData, "name"),
        phone: field(formData, "phone"),
        address: field(formData, "address"),
      },
      field(formData, "idempotencyKey"),
    );
    orderId = order.id;
  } catch (e) {
    if (e instanceof ApiError) redirect(`/checkout?error=${encodeURIComponent(e.message)}`);
    throw e;
  }
  redirect(`/orders/${orderId}`);
}

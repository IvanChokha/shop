import { randomUUID } from "node:crypto";

import { redirect } from "next/navigation";

import { placeOrder } from "@/app/actions";
import SubmitButton from "@/components/SubmitButton";
import { getCart } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { getCartKey } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function CheckoutPage({ searchParams }) {
  const { error } = await searchParams;
  const cartKey = await getCartKey();
  const cart = cartKey ? await getCart(cartKey) : null;
  if (!cart || cart.items.length === 0) redirect("/cart");

  // Новый ключ на каждый показ формы: двойной клик или повтор запроса не создадут
  // второй заказ — backend идемпотентен по этому ключу.
  const idempotencyKey = randomUUID();

  return (
    <>
      <h1>Оформление заказа</h1>
      <p>Сумма заказа: {formatPrice(cart.total_cents)}. Оплаты нет — это демо.</p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <form action={placeOrder} className="stack">
        <input type="hidden" name="idempotencyKey" value={idempotencyKey} />
        <label>
          Имя
          <input name="name" required maxLength={200} autoComplete="name" />
        </label>
        <label>
          Телефон
          <input name="phone" type="tel" required minLength={3} maxLength={50} autoComplete="tel" />
        </label>
        <label>
          Адрес доставки
          <textarea name="address" rows={3} maxLength={1000} autoComplete="street-address" />
        </label>
        <SubmitButton>Оформить заказ</SubmitButton>
      </form>
    </>
  );
}

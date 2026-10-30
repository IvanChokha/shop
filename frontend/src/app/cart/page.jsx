import Link from "next/link";

import { removeFromCart } from "@/app/actions";
import SubmitButton from "@/components/SubmitButton";
import { getCart } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { getCartKey } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function CartPage() {
  const cartKey = await getCartKey();
  const cart = cartKey ? await getCart(cartKey) : { items: [], total_cents: 0 };

  if (cart.items.length === 0) {
    return (
      <>
        <h1>Корзина</h1>
        <p>
          Корзина пуста. <Link href="/">Перейти в каталог</Link>
        </p>
      </>
    );
  }

  return (
    <>
      <h1>Корзина</h1>
      <table>
        <thead>
          <tr>
            <th>Товар</th>
            <th>Кол-во</th>
            <th>Сумма</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {cart.items.map((item) => (
            <tr key={item.product.id}>
              <td>
                <Link href={`/products/${item.product.id}`}>{item.product.title}</Link>
              </td>
              <td>{item.qty}</td>
              <td>{formatPrice(item.subtotal_cents)}</td>
              <td>
                <form action={removeFromCart}>
                  <input type="hidden" name="productId" value={item.product.id} />
                  <SubmitButton>Убрать</SubmitButton>
                </form>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        <strong>Итого: {formatPrice(cart.total_cents)}</strong>
      </p>
      <p>
        <Link href="/checkout">Оформить заказ</Link>
      </p>
    </>
  );
}

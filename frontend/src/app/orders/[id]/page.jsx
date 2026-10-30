import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiError, getOrder } from "@/lib/api";
import { formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function OrderPage({ params }) {
  const { id } = await params;

  let order;
  try {
    order = await getOrder(id);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }

  return (
    <>
      <h1>Заказ оформлен</h1>
      <p>
        Номер заказа: <code>{order.id}</code>
      </p>
      <table>
        <thead>
          <tr>
            <th>Товар</th>
            <th>Кол-во</th>
            <th>Сумма</th>
          </tr>
        </thead>
        <tbody>
          {order.items.map((item) => (
            <tr key={item.product_id}>
              <td>{item.title}</td>
              <td>{item.qty}</td>
              <td>{formatPrice(item.unit_price_cents * item.qty)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        <strong>Итого: {formatPrice(order.total_cents)}</strong>
      </p>
      <p>
        {order.customer_name}, {order.phone}
        {order.address && `, ${order.address}`}
      </p>
      <p>
        <Link href="/">Вернуться в каталог</Link>
      </p>
    </>
  );
}

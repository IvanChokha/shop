import { notFound } from "next/navigation";

import { addToCart } from "@/app/actions";
import SubmitButton from "@/components/SubmitButton";
import { ApiError, getProduct } from "@/lib/api";
import { formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ProductPage({ params, searchParams }) {
  const { id } = await params;
  const { error } = await searchParams;

  let product;
  try {
    product = await getProduct(id);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }

  return (
    <article>
      <h1>{product.title}</h1>
      {product.image_url && <img src={product.image_url} alt={product.title} />}
      <p>{product.description}</p>
      <p>
        <strong>{formatPrice(product.price_cents)}</strong>
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {product.stock > 0 ? (
        <form action={addToCart}>
          <input type="hidden" name="productId" value={product.id} />
          <SubmitButton>В корзину</SubmitButton>
        </form>
      ) : (
        <p className="muted">Нет в наличии</p>
      )}
    </article>
  );
}

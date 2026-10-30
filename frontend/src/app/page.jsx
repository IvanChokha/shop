import Link from "next/link";

import { getProducts } from "@/lib/api";
import { formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 12;

export default async function CatalogPage({ searchParams }) {
  const { page } = await searchParams;
  const current = Math.max(1, Number(page) || 1);
  const { items, total } = await getProducts(PAGE_SIZE, (current - 1) * PAGE_SIZE);
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <h1>Каталог</h1>
      {items.length === 0 && <p>Товаров пока нет.</p>}
      <div className="grid">
        {items.map((p) => (
          <Link key={p.id} href={`/products/${p.id}`} className="card">
            {/* Обычный <img>, не next/image: оптимизатор кэширует картинки на локальном диске инстанса. */}
            {p.image_url && <img src={p.image_url} alt={p.title} />}
            <h2>{p.title}</h2>
            <div>{formatPrice(p.price_cents)}</div>
          </Link>
        ))}
      </div>
      {pages > 1 && (
        <nav className="pager" aria-label="Страницы каталога">
          {current > 1 && <Link href={`/?page=${current - 1}`}>Назад</Link>}
          <span>
            Страница {current} из {pages}
          </span>
          {current < pages && <Link href={`/?page=${current + 1}`}>Дальше</Link>}
        </nav>
      )}
    </>
  );
}

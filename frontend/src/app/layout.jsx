import Link from "next/link";
import { hostname } from "node:os";

import "./globals.css";

export const metadata = { title: "Магазин" };
// Все страницы зависят от данных API и cookie — никакой статики и ISR-кэша на диске инстанса.
export const dynamic = "force-dynamic";

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body>
        <header className="container nav">
          <Link href="/">Каталог</Link>
          <Link href="/cart">Корзина</Link>
        </header>
        <main className="container">{children}</main>
        <footer className="container muted">Страницу отдал инстанс {hostname()}</footer>
      </body>
    </html>
  );
}

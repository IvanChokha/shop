import { randomBytes } from "node:crypto";
import { cookies } from "next/headers";

// «Сессия» = непрозрачный ключ в HttpOnly-cookie. Сама корзина лежит в БД за FastAPI,
// поэтому любой инстанс Next.js и любая реплика API обслужат любой запрос.
const CART_COOKIE = "cart_key";

export async function getCartKey() {
  const store = await cookies();
  return store.get(CART_COOKIE)?.value;
}

// Вызывать только из Server Action / Route Handler: в Server Component cookie менять нельзя.
export async function getOrCreateCartKey() {
  const store = await cookies();
  const existing = store.get(CART_COOKIE)?.value;
  if (existing) return existing;

  const key = `web_${randomBytes(24).toString("base64url")}`;
  store.set(CART_COOKIE, key, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.COOKIE_SECURE === "true", // true за HTTPS
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return key;
}

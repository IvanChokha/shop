// Клиент к FastAPI. Работает только на сервере Next.js (API_URL не попадает в браузер).
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body, cartKey, headers = {} } = {}) {
  const finalHeaders = { Accept: "application/json", ...headers };
  if (body !== undefined) finalHeaders["Content-Type"] = "application/json";
  if (cartKey) finalHeaders["X-Cart-Key"] = cartKey;

  const res = await fetch(`${API_URL}/api/v1${path}`, {
    method,
    headers: finalHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
    // Никакого Data Cache: он у каждого инстанса Next.js свой, и реплики показывали бы разное.
    cache: "no-store",
  });

  if (!res.ok) {
    let message = res.statusText || "Ошибка сервиса";
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") message = data.detail;
      else if (res.status === 422) message = "Проверьте введённые данные";
    } catch {
      // тело не JSON — оставляем statusText
    }
    throw new ApiError(res.status, message);
  }
  return res.json();
}

export const getProducts = (limit, offset) => request(`/products?limit=${limit}&offset=${offset}`);
export const getProduct = (id) => request(`/products/${encodeURIComponent(id)}`);
export const getCart = (cartKey) => request("/cart", { cartKey });
export const addToCart = (cartKey, productId, qty = 1) =>
  request("/cart/items", { method: "POST", cartKey, body: { product_id: productId, qty } });
export const removeFromCart = (cartKey, productId) =>
  request(`/cart/items/${encodeURIComponent(productId)}`, { method: "DELETE", cartKey });
export const placeOrder = (cartKey, body, idempotencyKey) =>
  request("/orders", {
    method: "POST",
    cartKey,
    body,
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
  });
export const getOrder = (id) => request(`/orders/${encodeURIComponent(id)}`);

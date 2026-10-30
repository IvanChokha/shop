const rub = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB" });

// Деньги приходят в копейках.
export const formatPrice = (cents) => rub.format(cents / 100);

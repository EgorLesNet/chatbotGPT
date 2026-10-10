const formatter = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function rub(value: number | string): string {
  const n = Number(value);
  return formatter.format(Number.isFinite(n) ? n : 0);
}

export function parseAmount(value: string): number {
  return Number(value.replace(/\s/g, "").replace(",", "."));
}

export const QUOTE_PREVIEW_PAGE_WIDTH_MM = 210;
export const QUOTE_PREVIEW_PADDING_MM = 1.6;

export const QUOTE_PREVIEW_COLUMN_WIDTHS_MM = [
  15,
  18.4,
  53.4,
  18.3,
  18.4,
  17.6,
  10.4,
  14.4,
  12.6,
  28.3,
] as const;

export const QUOTE_PREVIEW_ROW_HEIGHTS_MM = {
  title: 20,
  header: 7.2,
  intro: 22.6,
  tableHeader: 6.6,
  item: 8.8,
  subtotal: 6.6,
  total: 6.6,
  amount: 7.2,
  notice: 12,
  terms: 23.4,
  invoice: 37,
  bank: 28.6,
} as const;

export const QUOTE_PREVIEW_TABLE_WIDTH_MM = QUOTE_PREVIEW_COLUMN_WIDTHS_MM.reduce(
  (total, width) => total + width,
  0,
);

export function millimeters(value: number) {
  return `${value}mm`;
}

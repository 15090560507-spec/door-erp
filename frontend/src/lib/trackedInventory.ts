import type { TrackedProductionInventoryItem } from "./inventoryTypes";

export function filterTrackedInventory(
  items: TrackedProductionInventoryItem[],
  filters: { warehouseId: string; q: string; lowOnly: boolean },
) {
  if (filters.lowOnly) return [];
  const terms = filters.q.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return items.filter((item) => {
    if (filters.warehouseId && String(item.warehouse_id ?? "") !== filters.warehouseId) return false;
    const text = [item.production_no, item.item_name, item.door_type, item.specification, item.customer, item.project]
      .join(" ").toLocaleLowerCase();
    return terms.every((term) => text.includes(term));
  });
}

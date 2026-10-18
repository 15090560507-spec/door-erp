"""Door counts are independent of each item's per-door area or accessory use."""


def quote_door_quantity(group: dict) -> int:
    quantity = group.get('doorQuantity', 1)
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError('同规格门樘数必须为大于0的整数')
    return quantity

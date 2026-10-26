def canonical_asset_category(value: str) -> str:
    return {
        "门扇": "门扇款式",
        "款式": "门扇款式",
        "包套": "门套款式",
        "门套": "门套款式",
    }.get(value, value)

"""Quantity units offered for each food category."""

from apps.common.choices import FoodCategory

# First entry is the default when the client does not pick a unit.
CATEGORY_UNITS: dict[str, tuple[str, ...]] = {
    FoodCategory.COOKED_MEAL: ("plate", "box", "pack"),
    FoodCategory.RICE: ("plate", "pack", "box"),
    FoodCategory.NOODLES: ("bowl", "pack", "box"),
    FoodCategory.BREAD_BAKERY: ("piece", "loaf", "pack"),
    FoodCategory.VEGETABLES: ("pack",),
    FoodCategory.FRUITS: ("piece", "pack"),
    FoodCategory.PROTEIN: ("piece", "pack"),
    FoodCategory.SOUP: ("bowl", "cup", "pack"),
    FoodCategory.DESSERT: ("piece", "cup", "slice"),
    FoodCategory.DRINKS: ("cup", "glass", "bottle"),
    FoodCategory.PACKAGED: ("pack", "box", "bottle"),
    FoodCategory.OTHER: ("pack", "piece", "box"),
}

_UNIT_ALIASES = {
    "glasses": "glass",
    "boxes": "box",
    "loaves": "loaf",
    "pieces": "piece",
    "packs": "pack",
    "plates": "plate",
    "bowls": "bowl",
    "cups": "cup",
    "bottles": "bottle",
    "bags": "bag",
    "slices": "slice",
}

_IRREGULAR_PLURALS = {
    "glass": "glasses",
    "box": "boxes",
    "loaf": "loaves",
    "kg": "kg",
}


def units_for_category(category: str) -> tuple[str, ...]:
    return CATEGORY_UNITS.get(category, CATEGORY_UNITS[FoodCategory.OTHER])


def list_food_categories() -> list[dict]:
    return [
        {
            "code": category.value,
            "label": category.label,
            "default_unit": units_for_category(category)[0],
            "units": list(units_for_category(category)),
        }
        for category in FoodCategory
    ]


def _canonical_unit(unit: str) -> str:
    text = unit.strip().lower()
    return _UNIT_ALIASES.get(text, text)


def resolve_unit(category: str, unit: str | None) -> str:
    """Use a chosen unit when it belongs to the category; otherwise the default."""
    allowed = units_for_category(category)
    if unit and str(unit).strip():
        canonical = _canonical_unit(str(unit))
        if canonical in allowed:
            return canonical
    return allowed[0]


def pluralize_unit(unit: str | None, quantity: int) -> str:
    word = (unit or "pack").strip() or "pack"
    if quantity == 1:
        return word
    lower = word.lower()
    if lower in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[lower]
    if lower.endswith("s"):
        return word
    return f"{word}s"


def format_quantity_unit(quantity: int, unit: str | None) -> str:
    return f"{quantity} {pluralize_unit(unit, quantity)}"

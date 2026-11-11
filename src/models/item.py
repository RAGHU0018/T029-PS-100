from dataclasses import dataclass
from enum import Enum
import math

class ItemClass(Enum):
    LIFE_SAVING = "LIFE_SAVING"
    FOOD = "FOOD"
    SHELTER = "SHELTER"

@dataclass
class Item:
    item_id: str
    name: str
    unit: str
    daily_norm: float
    shelf_life_days: int
    item_class: ItemClass
    is_medicine: bool = False
    unit_weight_kg: float = 0.0

    def __post_init__(self):
        for value, label in ((self.item_id, "Item ID"), (self.name, "Item name"), (self.unit, "Unit")):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} cannot be empty.")
        if not math.isfinite(self.daily_norm) or self.daily_norm <= 0:
            raise ValueError("Daily norm must be a positive finite number.")
        if not isinstance(self.shelf_life_days, int) or isinstance(self.shelf_life_days, bool) or self.shelf_life_days <= 0:
            raise ValueError("Shelf life must be a positive integer.")
        if not isinstance(self.item_class, ItemClass):
            raise ValueError("Invalid item class.")
        if not isinstance(self.is_medicine, bool):
            raise ValueError("is_medicine must be a boolean.")
        if not math.isfinite(self.unit_weight_kg) or self.unit_weight_kg < 0:
            raise ValueError("Unit weight must be finite and non-negative.")

    @property
    def item_name(self):
        return self.name

    @property
    def daily_norm_per_person(self):
        return self.daily_norm

    @property
    def priority_class(self):
        return self.item_class

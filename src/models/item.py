
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

    def __post_init__(self):
        if not self.item_id.strip():
            raise ValueError("Item ID cannot be empty.")

        if not self.name.strip():
            raise ValueError("Item name cannot be empty.")

        if not self.unit.strip():
            raise ValueError("Item unit cannot be empty.")

        if not math.isfinite(self.daily_norm) or self.daily_norm <= 0:
            raise ValueError("Daily norm must be a positive finite number.")

        if self.shelf_life_days <= 0:
            raise ValueError("Shelf life must be greater than zero.")

        if not isinstance(self.item_class, ItemClass):
            raise ValueError("Invalid item class.")

        if not isinstance(self.is_medicine, bool):
            raise ValueError("is_medicine must be a boolean.")

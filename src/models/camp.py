from dataclasses import dataclass
from datetime import datetime

@dataclass
class Camp:
    camp_id: str
    zone_id: str
    capacity: int
    occupancy: int
    vulnerable_count: int = 0
    camp_name: str = ""
    children: int = 0
    elderly: int = 0
    pregnant: int = 0
    opened_ts: datetime | None = None

    def __post_init__(self):
        if not self.camp_id.strip() or not self.zone_id.strip():
            raise ValueError("Camp ID and zone ID cannot be empty.")
        if not isinstance(self.capacity, int) or isinstance(self.capacity, bool) or self.capacity <= 0:
            raise ValueError("Camp capacity must be a positive integer.")
        if not isinstance(self.occupancy, int) or isinstance(self.occupancy, bool) or self.occupancy < 0:
            raise ValueError("Occupancy must be a non-negative integer.")
        for field_name in ("children", "elderly", "pregnant", "vulnerable_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")
        category_total = self.children + self.elderly + self.pregnant
        if category_total and self.vulnerable_count and category_total != self.vulnerable_count:
            raise ValueError("Vulnerable count must equal children + elderly + pregnant.")
        if category_total:
            self.vulnerable_count = category_total
        if self.vulnerable_count > self.occupancy:
            raise ValueError("Vulnerable count cannot exceed occupancy.")
        if self.opened_ts is not None and not isinstance(self.opened_ts, datetime):
            raise ValueError("opened_ts must be a datetime.")
        if not isinstance(self.camp_name, str):
            raise ValueError("Camp name must be a string.")

    @property
    def occupancy_percentage(self) -> float:
        return self.occupancy / self.capacity * 100

    @property
    def is_overflow(self) -> bool:
        return self.occupancy_percentage > 120

    @property
    def requires_redirection(self) -> bool:
        return self.occupancy_percentage > 150

    @property
    def excess_occupancy(self) -> int:
        return max(0, self.occupancy - self.capacity) if self.is_overflow else 0

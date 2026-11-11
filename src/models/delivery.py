from dataclasses import dataclass
from datetime import datetime

@dataclass
class Delivery:
    delivery_id: str
    request_id: str = ""
    vehicle_id: str = ""
    depot_id: str = ""
    camp_id: str = ""
    item_id: str = ""
    batch_id: str = ""
    dispatched_quantity: int = 0
    delivered_quantity: int = 0
    returned_quantity: int = 0
    dispatch_time: datetime | None = None
    delivered_at: datetime | None = None
    trip_id: str = ""

    def __post_init__(self):
        if not isinstance(self.delivery_id, str) or not self.delivery_id.strip():
            raise ValueError("delivery_id cannot be empty.")
        for name in ("request_id", "vehicle_id", "depot_id", "camp_id", "item_id", "batch_id", "trip_id"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string.")
        for name in ("dispatched_quantity", "delivered_quantity", "returned_quantity"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative whole number.")
        if self.dispatched_quantity and self.delivered_quantity + self.returned_quantity > self.dispatched_quantity:
            raise ValueError("Delivered and returned quantities cannot exceed dispatched quantity.")
        if self.dispatch_time is not None:
            self._validate_datetime(self.dispatch_time, "dispatch_time")
        if self.delivered_at is not None:
            self._validate_datetime(self.delivered_at, "delivered_at")
            if self.dispatch_time and self.delivered_at < self.dispatch_time:
                raise ValueError("Delivery time cannot be before dispatch time.")

    @staticmethod
    def _validate_datetime(value, name):
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be a timezone-aware datetime.")

    @property
    def shortfall_quantity(self):
        return self.dispatched_quantity - self.delivered_quantity - self.returned_quantity

    @property
    def discrepancy_percentage(self):
        if self.delivered_at is None or self.dispatched_quantity <= 0:
            return None
        return self.shortfall_quantity / self.dispatched_quantity * 100

    @property
    def has_discrepancy(self):
        value = self.discrepancy_percentage
        return value is not None and value > 2.0

    @property
    def delivered_qty(self):
        return self.delivered_quantity

    @property
    def returned_qty(self):
        return self.returned_quantity

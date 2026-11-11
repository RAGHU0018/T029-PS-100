
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Delivery:
    delivery_id: str
    request_id: str
    vehicle_id: str
    depot_id: str
    camp_id: str
    item_id: str
    batch_id: str
    dispatched_quantity: int
    delivered_quantity: int = 0
    returned_quantity: int = 0
    dispatch_time: datetime | None = None
    delivered_at: datetime | None = None

    def __post_init__(self):
        identifiers = {
            "delivery_id": self.delivery_id,
            "request_id": self.request_id,
            "vehicle_id": self.vehicle_id,
            "depot_id": self.depot_id,
            "camp_id": self.camp_id,
            "item_id": self.item_id,
            "batch_id": self.batch_id
        }

        for field_name, value in identifiers.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} cannot be empty.")

        quantities = {
            "dispatched_quantity": self.dispatched_quantity,
            "delivered_quantity": self.delivered_quantity,
            "returned_quantity": self.returned_quantity
        }

        for field_name, value in quantities.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{field_name} must be a whole number.")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        if self.dispatched_quantity <= 0:
            raise ValueError("Dispatched quantity must be positive.")

        if (
            self.delivered_quantity + self.returned_quantity
            > self.dispatched_quantity
        ):
            raise ValueError(
                "Delivered and returned quantities cannot exceed "
                "dispatched quantity."
            )

        if self.dispatch_time is not None:
            self._validate_datetime(self.dispatch_time, "dispatch_time")

        if self.delivered_at is not None:
            self._validate_datetime(self.delivered_at, "delivered_at")

            if self.dispatch_time is None:
                raise ValueError(
                    "Dispatch time is required before delivery completion."
                )

            if self.delivered_at < self.dispatch_time:
                raise ValueError(
                    "Delivery time cannot be before dispatch time."
                )

    @staticmethod
    def _validate_datetime(value: datetime, field_name: str):
        if not isinstance(value, datetime):
            raise ValueError(f"{field_name} must be a datetime.")

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                f"{field_name} must include timezone information."
            )

    @property
    def shortfall_quantity(self) -> int:
        return self.dispatched_quantity - self.delivered_quantity

    @property
    def discrepancy_percentage(self) -> float | None:
        if self.delivered_at is None:
            return None

        return (
            self.shortfall_quantity
            / self.dispatched_quantity
        ) * 100

    @property
    def has_discrepancy(self) -> bool:
        percentage = self.discrepancy_percentage

        return percentage is not None and percentage > 2.0

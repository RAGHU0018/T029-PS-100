
from dataclasses import dataclass
from datetime import datetime


def validate_aware_datetime(value: datetime, field_name: str):
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must include timezone information."
        )


@dataclass
class StockBatch:
    batch_id: str
    item_id: str
    depot_id: str
    quantity: int
    received_at: datetime
    expiry_date: datetime
    is_donation: bool = False
    requires_verification: bool = False
    verified: bool = False

    def __post_init__(self):
        if not self.batch_id.strip():
            raise ValueError("Batch ID cannot be empty.")

        if not self.item_id.strip():
            raise ValueError("Item ID cannot be empty.")

        if not self.depot_id.strip():
            raise ValueError("Depot ID cannot be empty.")

        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool):
            raise ValueError("Batch quantity must be a whole number.")

        if self.quantity <= 0:
            raise ValueError("Batch quantity must be greater than zero.")

        if not isinstance(self.is_donation, bool):
            raise ValueError("is_donation must be a boolean.")

        if not isinstance(self.requires_verification, bool):
            raise ValueError("requires_verification must be a boolean.")

        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean.")

        if self.requires_verification and not self.is_donation:
            raise ValueError(
                "Verification requirement applies to donated stock."
            )

        validate_aware_datetime(self.received_at, "received_at")
        validate_aware_datetime(self.expiry_date, "expiry_date")

        if self.expiry_date <= self.received_at:
            raise ValueError("Expiry date must be after receipt date.")

    @property
    def is_quarantined(self) -> bool:
        return self.requires_verification and not self.verified

    def is_expired(self, current_time: datetime) -> bool:
        validate_aware_datetime(current_time, "current_time")

        return current_time >= self.expiry_date

    def can_allocate(self, current_time: datetime) -> bool:
        return (
            self.quantity > 0
            and not self.is_expired(current_time)
            and not self.is_quarantined
        )

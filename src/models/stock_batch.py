from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class StockSource(Enum):
    GOVT = "GOVT"
    DONATION = "DONATION"

def validate_aware_datetime(value: datetime, field_name: str):
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information.")

@dataclass
class StockBatch:
    batch_id: str
    item_id: str
    depot_id: str
    quantity: int
    received_at: datetime | None
    expiry_date: datetime
    is_donation: bool = False
    requires_verification: bool = False
    verified: bool = False
    source: StockSource | None = None

    def __post_init__(self):
        for value, label in ((self.batch_id, "Batch ID"), (self.item_id, "Item ID"), (self.depot_id, "Depot ID")):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} cannot be empty.")
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool) or self.quantity <= 0:
            raise ValueError("Batch quantity must be a positive whole number.")
        if self.source is not None:
            if not isinstance(self.source, StockSource):
                raise ValueError("Invalid stock source.")
            self.is_donation = self.source == StockSource.DONATION
        else:
            self.source = StockSource.DONATION if self.is_donation else StockSource.GOVT
        if not all(isinstance(x, bool) for x in (self.is_donation, self.requires_verification, self.verified)):
            raise ValueError("Stock flags must be booleans.")
        if self.requires_verification and not self.is_donation:
            raise ValueError("Verification requirement applies to donated stock.")
        if self.is_donation and self.requires_verification is False and self.verified is False:
            # Non-medicine donations may be immediately usable; manager decides if quarantine applies.
            pass
        if self.received_at is not None:
            validate_aware_datetime(self.received_at, "received_at")
        validate_aware_datetime(self.expiry_date, "expiry_date")
        if self.received_at is not None and self.expiry_date <= self.received_at:
            raise ValueError("Expiry date must be after receipt date.")

    @property
    def expiry_ts(self):
        return self.expiry_date

    @property
    def qty(self):
        return self.quantity

    @property
    def is_quarantined(self):
        return self.requires_verification and not self.verified

    def is_expired(self, current_time):
        validate_aware_datetime(current_time, "current_time")
        return current_time >= self.expiry_date

    def can_allocate(self, current_time):
        return self.quantity > 0 and not self.is_expired(current_time) and not self.is_quarantined

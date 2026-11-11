from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class Urgency(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"

@dataclass
class Request:
    request_id: str
    camp_id: str
    item_id: str
    quantity: int
    urgency: Urgency
    requested_at: datetime
    stock_on_hand: int = 0

    def __post_init__(self):
        for value, label in ((self.request_id, "Request ID"), (self.camp_id, "Camp ID"), (self.item_id, "Item ID")):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} cannot be empty.")
        for value, label in ((self.quantity, "Request quantity"), (self.stock_on_hand, "Stock on hand")):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{label} must be a non-negative whole number.")
        if self.quantity == 0:
            raise ValueError("Request quantity must be greater than zero.")
        if not isinstance(self.urgency, Urgency):
            raise ValueError("Invalid request urgency.")
        if not isinstance(self.requested_at, datetime):
            raise ValueError("Request time must be a datetime.")
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("Request time must include timezone information.")

    @property
    def qty(self):
        return self.quantity

    @property
    def request_ts(self):
        return self.requested_at

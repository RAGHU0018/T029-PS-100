
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

    VALID_URGENCIES = set(Urgency)

    def __post_init__(self):
        if not self.request_id.strip():
            raise ValueError("Request ID cannot be empty.")

        if not self.camp_id.strip():
            raise ValueError("Camp ID cannot be empty.")

        if not self.item_id.strip():
            raise ValueError("Item ID cannot be empty.")

        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool):
            raise ValueError("Request quantity must be a whole number.")

        if self.quantity <= 0:
            raise ValueError("Request quantity must be greater than zero.")

        if not isinstance(self.urgency, Urgency):
            raise ValueError("Invalid request urgency.")

        if not isinstance(self.requested_at, datetime):
            raise ValueError("Request time must be a datetime.")

        if (
            self.requested_at.tzinfo is None
            or self.requested_at.utcoffset() is None
        ):
            raise ValueError("Request time must include timezone information.")

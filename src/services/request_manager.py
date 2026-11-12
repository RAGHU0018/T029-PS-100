"""Request need, trimming, allocation status and supersession management."""
from dataclasses import dataclass
from math import ceil

from src.models.item import Item
from src.models.camp import Camp
from src.models.request import Request


@dataclass
class ManagedRequest:
    request: Request
    need: int
    original_quantity: int
    trimmed_quantity: int
    allocated_quantity: int = 0
    superseded: bool = False

    @property
    def open_quantity(self):
        return max(0, self.trimmed_quantity - self.allocated_quantity)

    @property
    def status(self):
        if self.superseded:
            return "SUPERSEDED"
        if self.open_quantity == 0:
            return "FULFILLED"
        if self.allocated_quantity == 0 and self.was_trimmed:
            return "TRIMMED"
        return "OPEN" if self.allocated_quantity == 0 else "PARTIAL"

    @property
    def was_trimmed(self):
        return self.trimmed_quantity < self.original_quantity


class RequestManager:
    def __init__(self, camps: dict[str, Camp], items: dict[str, Item]):
        self.camps = camps
        self.items = items
        self.requests: dict[str, ManagedRequest] = {}
        self.active: dict[tuple[str, str], ManagedRequest] = {}
        self.rejected: dict[str, str] = {}

    def record_rejection(self, request_id: str, reason: str) -> None:
        if request_id:
            self.rejected[request_id] = reason

    @staticmethod
    def calculate_need(occupancy: int, daily_norm: float, stock_on_hand: int) -> int:
        if isinstance(occupancy, bool) or not isinstance(occupancy, int) or occupancy < 0:
            raise ValueError("Occupancy must be a non-negative integer.")
        if isinstance(stock_on_hand, bool) or not isinstance(stock_on_hand, int) or stock_on_hand < 0:
            raise ValueError("Stock on hand must be a non-negative integer.")
        if daily_norm <= 0:
            raise ValueError("Daily norm must be positive.")
        return max(0, ceil(occupancy * daily_norm * 2) - stock_on_hand)

    def register(self, request: Request) -> ManagedRequest:
        if not isinstance(request, Request):
            raise ValueError("A valid Request is required.")
        if request.request_id in self.requests:
            raise ValueError(f"Duplicate request ID: {request.request_id}")
        if request.camp_id not in self.camps:
            raise ValueError(f"Unknown camp: {request.camp_id}")
        if request.item_id not in self.items:
            raise ValueError(f"Unknown item: {request.item_id}")
        camp, item = self.camps[request.camp_id], self.items[request.item_id]
        need = self.calculate_need(camp.occupancy, item.daily_norm, request.stock_on_hand)
        trimmed = min(request.quantity, need)
        managed = ManagedRequest(request, need, request.quantity, trimmed)
        key = (request.camp_id, request.item_id)
        previous = self.active.get(key)
        if previous is not None:
            previous.superseded = True
        self.requests[request.request_id] = managed
        self.active[key] = managed
        return managed

    def record_allocation(self, request_id: str, quantity: int) -> ManagedRequest:
        managed = self.requests[request_id]
        if managed.superseded:
            raise ValueError("Cannot allocate to a superseded request.")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Allocation must be a positive integer.")
        if quantity > managed.open_quantity:
            raise ValueError("Allocation exceeds open request quantity.")
        managed.allocated_quantity += quantity
        return managed

    def open_requests(self):
        return [r for r in self.active.values() if not r.superseded and r.open_quantity > 0]

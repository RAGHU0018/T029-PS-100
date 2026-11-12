"""Camp overflow shelter requests and arrival redirection (BR-45–49)."""
from math import ceil

from src.models.request import Request, Urgency
from src.models.item import ItemClass


class OverflowManager:
    def __init__(self, camps, items, request_manager, distances=None):
        self.camps, self.items = camps, items
        self.request_manager = request_manager
        self.distances = distances or {}
        self.auto_sequence = 0

    def _distance(self, origin, destination):
        return self.distances.get((origin, destination), self.distances.get(f"{origin}-{destination}", float("inf")))

    def _shelter_item(self):
        matches = [item for item in self.items.values()
                   if item.item_class == ItemClass.SHELTER and item.item_id == "TARP"]
        if not matches:
            matches = [item for item in self.items.values() if item.item_class == ItemClass.SHELTER]
        if not matches:
            raise ValueError("No shelter item is registered for overflow requests.")
        return matches[0]

    def _create_overflow_request(self, camp, timestamp, excess):
        item = self._shelter_item()
        quantity = ceil(excess * item.daily_norm * 2)
        if quantity <= 0:
            return None
        key = (camp.camp_id, item.item_id)
        old = self.request_manager.active.get(key)
        if old and old.open_quantity:
            quantity += old.open_quantity
        self.auto_sequence += 1
        request = Request(f"AUTO-{self.auto_sequence:02d}", camp.camp_id, item.item_id,
                          quantity, Urgency.HIGH, timestamp, 0)
        return self.request_manager.register(request)

    def register_arrival(self, camp_id, timestamp, persons):
        camp = self.camps[camp_id]
        if isinstance(persons, bool) or not isinstance(persons, int) or persons <= 0:
            raise ValueError("Arrival persons must be a positive integer.")
        original = camp.occupancy
        redirected_to = None
        if camp.requires_redirection:
            candidates = [c for c in self.camps.values() if c.zone_id == camp.zone_id and c.camp_id != camp_id
                          and c.occupancy < c.capacity and c.capacity - c.occupancy >= persons]
            if candidates:
                candidates.sort(key=lambda c: (self._distance(camp_id, c.camp_id), c.camp_id))
                target = candidates[0]
                target.occupancy += persons
                redirected_to = target.camp_id
        if redirected_to is None:
            camp.occupancy += persons
        threshold = ceil(camp.capacity * 1.2)
        excess = max(0, camp.occupancy - threshold)
        overflow_request = self._create_overflow_request(camp, timestamp, excess) if excess else None
        return {"camp_id": camp_id, "timestamp": timestamp, "persons": persons,
                "previous_occupancy": original, "new_occupancy": camp.occupancy,
                "is_overflow": camp.is_overflow, "requires_redirection": camp.requires_redirection,
                "redirected_to": redirected_to,
                "overflow_request_id": overflow_request.request.request_id if overflow_request else None}

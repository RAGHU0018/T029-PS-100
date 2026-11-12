"""Two-pass fair allocation over FEFO inventory (allocation BR-24–30)."""
from dataclasses import dataclass
from datetime import datetime
from math import floor

from src.models.item import ItemClass


@dataclass(frozen=True)
class Allocation:
    cycle_ts: datetime
    request_id: str
    camp_id: str
    item_id: str
    score: float
    batch_id: str
    qty: int
    rule_ids: tuple[str, ...]


class AllocationEngine:
    CLASS_ORDER = (ItemClass.LIFE_SAVING, ItemClass.FOOD, ItemClass.SHELTER)
    RULE_IDS = ("BR-24", "BR-25", "BR-26", "BR-27", "BR-28", "BR-29", "BR-30")

    def __init__(self, inventory_manager, request_manager, priority_engine, camps, zones, items,
                 reachability_check=None):
        self.inventory = inventory_manager
        self.requests = request_manager
        self.priority = priority_engine
        self.camps, self.zones, self.items = camps, zones, items
        self.reachability_check = reachability_check
        self.records: list[Allocation] = []

    def allocate(self, cycle_ts: datetime) -> list[Allocation]:
        if cycle_ts.tzinfo is None:
            raise ValueError("Cycle timestamp must be timezone-aware.")
        start = len(self.records)
        item_order = {item_id: index for index, item_id in enumerate(self.items)}
        for item_class in self.CLASS_ORDER:
            class_items = [item_id for item_id, item in self.items.items() if item.item_class == item_class]
            class_items.sort(key=item_order.__getitem__)
            for item_id in class_items:
                by_depot = {}
                for managed in self.requests.open_requests():
                    if managed.request.item_id != item_id:
                        continue
                    camp = self.camps[managed.request.camp_id]
                    zone = self.zones[camp.zone_id]
                    if not zone.serving_depot_id:
                        continue
                    score = self.priority.score(managed, cycle_ts)
                    by_depot.setdefault(zone.serving_depot_id, []).append((managed, score))
                for depot_id, ranked in by_depot.items():
                    batches = self.inventory.get_allocatable_batches(depot_id, item_id, cycle_ts)
                    reachable = {}
                    if self.reachability_check is not None:
                        for managed, _ in ranked:
                            reachable[managed.request.request_id] = [batch for batch in batches
                                if self.reachability_check(batch, managed, cycle_ts)]
                        ranked = [(managed, score) for managed, score in ranked
                                  if reachable[managed.request.request_id]]
                        batches = [batch for batch in batches if any(batch in reachable[m.request.request_id]
                                                                     for m, _ in ranked)]
                    if not ranked:
                        continue
                    stock = sum(batch.quantity for batch in batches)
                    if stock <= 0:
                        continue
                    granted = {m.request.request_id: 0 for m, _ in ranked}
                    cap = floor(stock * .4) if len(ranked) > 1 else stock
                    self._pass(ranked, granted, stock, cap, limited=True)
                    left = stock - sum(granted.values())
                    if left:
                        self._pass(ranked, granted, left, None, limited=False)
                    ordered = sorted(ranked, key=lambda p: (-p[1], -self.camps[p[0].request.camp_id].occupancy,
                                                            p[0].request.camp_id))
                    batch_index = 0
                    batch_left = batches[0].quantity if batches else 0
                    for managed, score in ordered:
                        qty_left = granted[managed.request.request_id]
                        if not qty_left:
                            continue
                        request_batches = reachable.get(managed.request.request_id, batches)
                        allocated = 0
                        for batch in request_batches:
                            if qty_left <= 0:
                                break
                            if batch.quantity <= 0:
                                continue
                            amount = min(qty_left, batch.quantity)
                            batch.quantity -= amount
                            qty_left -= amount
                            allocated += amount
                            self.records.append(Allocation(cycle_ts, managed.request.request_id,
                                managed.request.camp_id, item_id, score, batch.batch_id, amount, self.RULE_IDS))
                        if allocated:
                            self.requests.record_allocation(managed.request.request_id, allocated)
        return self.records[start:]

    def _pass(self, ranked, granted, stock, cap, limited):
        bands = sorted({self.priority.band(score) for _, score in ranked}, reverse=True)
        remaining_stock = stock
        for band in bands:
            group = sorted(((m, score) for m, score in ranked if self.priority.band(score) == band),
                           key=lambda p: (-p[1], -self.camps[p[0].request.camp_id].occupancy,
                                          p[0].request.camp_id))
            needs = [min(m.open_quantity - granted[m.request.request_id], cap) if limited
                     else m.open_quantity - granted[m.request.request_id] for m, _ in group]
            needs = [max(0, n) for n in needs]
            total = sum(needs)
            if total <= remaining_stock:
                shares = needs
            elif total:
                shares = [floor(remaining_stock * n / total) for n in needs]
                residue = remaining_stock - sum(shares)
                for i in range(len(shares)):
                    if residue <= 0:
                        break
                    extra = min(residue, needs[i] - shares[i])
                    if extra > 0:
                        shares[i] += extra
                        residue -= extra
            else:
                shares = [0] * len(group)
            for (managed, _), amount in zip(group, shares):
                granted[managed.request.request_id] += amount
            remaining_stock -= sum(shares)
            if remaining_stock <= 0:
                break

"""Run an allocation and dispatch cycle while retaining pending work."""
from datetime import timedelta

from src.services.inventory_manager import InventoryError


class CycleEngine:
    def __init__(self, inventory_manager, allocation_engine, dispatch_engine, reconciliation_engine=None):
        self.inventory = inventory_manager
        self.allocation = allocation_engine
        self.dispatch = dispatch_engine
        self.reconciliation = reconciliation_engine
        self.cycles = []

    def run(self, cycle_ts):
        if isinstance(cycle_ts, str):
            try:
                cycle_ts = self.inventory._parse_timestamp(cycle_ts)
            except InventoryError as exc:
                raise ValueError(str(exc)) from exc
        if cycle_ts.tzinfo is None:
            raise ValueError("Cycle timestamp must be timezone-aware.")
        if self.cycles and cycle_ts <= self.cycles[-1]["cycle_ts"]:
            raise ValueError("Cycle timestamps must increase.")
        write_offs = self.inventory.write_off_expired(cycle_ts)
        if self.reconciliation is not None:
            self.reconciliation.record_write_offs(write_offs)
        allocations = self.allocation.allocate(cycle_ts)
        manifests = self.dispatch.plan(cycle_ts, allocations)
        result = {"cycle_ts": cycle_ts, "window_end": cycle_ts + timedelta(hours=6),
                  "write_offs": write_offs, "allocations": allocations, "manifests": manifests}
        self.cycles.append(result)
        return result

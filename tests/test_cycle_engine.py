from datetime import datetime, timedelta, timezone
import pytest

from src.engines.cycle_engine import CycleEngine
from src.models.item import Item, ItemClass
from src.models.stock_batch import StockBatch
from src.services.inventory_manager import InventoryManager


NOW = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)


class AllocationSpy:
    def __init__(self):
        self.calls = []
    def allocate(self, at):
        self.calls.append(at)
        return ["allocation"]


class DispatchSpy:
    def __init__(self):
        self.calls = []
    def plan(self, at, allocations):
        self.calls.append((at, allocations))
        return ["manifest"]


class ReconciliationSpy:
    def __init__(self):
        self.writeoffs = []
    def record_write_offs(self, rows):
        self.writeoffs.extend(rows)


def test_cycle_writes_off_then_allocates_and_dispatches():
    inventory = InventoryManager()
    inventory.register_item(Item("I", "Item", "unit", 1, 10, ItemClass.FOOD))
    inventory.add_batch(StockBatch("B", "I", "D", 5, NOW - timedelta(days=2), NOW))
    allocation, dispatch, recon = AllocationSpy(), DispatchSpy(), ReconciliationSpy()
    engine = CycleEngine(inventory, allocation, dispatch, recon)
    result = engine.run(NOW)
    assert result["write_offs"][0]["batch_id"] == "B"
    assert recon.writeoffs == result["write_offs"]
    assert allocation.calls == [NOW]
    assert dispatch.calls == [(NOW, ["allocation"])]
    assert result["window_end"] == NOW + timedelta(hours=6)


def test_invalid_or_nonincreasing_cycle_does_not_mutate_inventory():
    inventory = InventoryManager()
    inventory.register_item(Item("I", "Item", "unit", 1, 10, ItemClass.FOOD))
    inventory.add_batch(StockBatch("B", "I", "D", 5, NOW, NOW + timedelta(hours=2)))
    engine = CycleEngine(inventory, AllocationSpy(), DispatchSpy())
    with pytest.raises(ValueError):
        engine.run("bad timestamp")
    engine.run(NOW)
    with pytest.raises(ValueError):
        engine.run(NOW)
    assert inventory.batches["B"].quantity == 5

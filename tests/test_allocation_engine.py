from datetime import datetime, timedelta, timezone

from src.engines.allocation_engine import AllocationEngine
from src.engines.priority_engine import PriorityEngine
from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.models.request import Request, Urgency
from src.models.stock_batch import StockBatch
from src.models.zone import Zone
from src.services.inventory_manager import InventoryManager
from src.services.request_manager import RequestManager


NOW = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)


def make_system():
    camps = {"C01": Camp("C01", "Z1", 200, 100, opened_ts=NOW),
             "C02": Camp("C02", "Z1", 200, 100, opened_ts=NOW),
             "C03": Camp("C03", "Z2", 200, 100, opened_ts=NOW)}
    zones = {"Z1": Zone("Z1", severity_level=2, serving_depot_id="D1"),
             "Z2": Zone("Z2", severity_level=2, serving_depot_id="D2")}
    items = {"RICE": Item("RICE", "Rice", "kg", .5, 100, ItemClass.FOOD),
             "TARP": Item("TARP", "Tarpaulin", "unit", .1, 100, ItemClass.SHELTER)}
    reqs = RequestManager(camps, items)
    reqs.register(Request("R1", "C01", "RICE", 100, Urgency.HIGH, NOW))
    reqs.register(Request("R2", "C02", "RICE", 100, Urgency.HIGH, NOW))
    reqs.register(Request("R3", "C03", "RICE", 100, Urgency.HIGH, NOW))
    reqs.register(Request("R4", "C03", "TARP", 10, Urgency.HIGH, NOW))
    inv = InventoryManager()
    for item in items.values():
        inv.register_item(item)
    inv.add_batch(StockBatch("OLD", "RICE", "D1", 50, NOW, NOW + timedelta(days=1)))
    inv.add_batch(StockBatch("NEW", "RICE", "D1", 51, NOW, NOW + timedelta(days=5)))
    inv.add_batch(StockBatch("OTHER_DEPOT", "RICE", "D2", 100, NOW, NOW + timedelta(days=2)))
    inv.add_batch(StockBatch("TARP_STOCK", "TARP", "D2", 10, NOW, NOW + timedelta(days=2)))
    priority = PriorityEngine(camps, zones)
    return AllocationEngine(inv, reqs, priority, camps, zones, items), reqs, inv


def test_fairness_cap_second_pass_proportional_residue_and_fefo():
    engine, reqs, inventory = make_system()
    rows = engine.allocate(NOW)
    by_request = {rid: sum(r.qty for r in rows if r.request_id == rid) for rid in ("R1", "R2", "R3")}
    assert by_request == {"R1": 51, "R2": 50, "R3": 100}
    d1_rows = [r for r in rows if r.request_id in ("R1", "R2")]
    assert sum(r.qty for r in d1_rows if r.batch_id == "OLD") == 50
    assert sum(r.qty for r in d1_rows if r.batch_id == "NEW") == 51
    assert inventory.batches["NEW"].quantity == 0
    assert sum(r.qty for r in rows if r.request_id == "R4") == 10
    assert max(i for i, r in enumerate(rows) if r.item_id == "RICE") < min(
        i for i, r in enumerate(rows) if r.item_id == "TARP")
    assert reqs.requests["R1"].open_quantity == 49
    assert all("BR-30" in r.rule_ids for r in rows)


def test_expired_and_quarantined_batches_are_not_allocated():
    engine, reqs, inventory = make_system()
    inventory.batches["OLD"].expiry_date = NOW
    inventory.batches["OLD"].quantity = 101
    inventory.batches["NEW"].requires_verification = True
    inventory.batches["NEW"].is_donation = True
    inventory.batches["NEW"].verified = False
    rows = engine.allocate(NOW)
    assert not [r for r in rows if r.request_id in ("R1", "R2")]
    assert reqs.requests["R1"].allocated_quantity == 0


def test_single_request_has_no_fairness_reduction():
    engine, reqs, _ = make_system()
    reqs.requests["R2"].superseded = True
    reqs.requests["R3"].superseded = True
    rows = engine.allocate(NOW)
    assert sum(r.qty for r in rows if r.request_id == "R1") == 100

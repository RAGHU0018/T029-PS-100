from datetime import datetime, timedelta, timezone

from src.engines.allocation_engine import Allocation
from src.engines.dispatch_engine import DispatchEngine
from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.models.vehicle import Vehicle, VehicleType
from src.models.zone import RoadStatus, Zone
from src.models.stock_batch import StockBatch
from src.models.request import Request, Urgency
from src.services.request_manager import ManagedRequest


NOW = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)


def setup_dispatch(road=RoadStatus.OPEN, vehicles=None, camps=None, distances=None):
    camps = camps or {"C1": Camp("C1", "Z1", 500, 300), "C2": Camp("C2", "Z1", 500, 300)}
    zone = Zone("Z1", severity_level=3, road_status=road, serving_depot_id="D1")
    item = Item("WATER", "Water", "litre", 1, 100, ItemClass.LIFE_SAVING, unit_weight_kg=1)
    vehicles = vehicles or {"V1": Vehicle("V1", "D1", VehicleType.TRUCK, 5000, 30)}
    distances = distances or {("D1", "C1"): 7.5, ("D1", "C2"): 8.0, ("C1", "C2"): 3.0}
    return DispatchEngine(vehicles, camps, {"Z1": zone}, {"WATER": item}, distances)


def allocation(rid="R1", camp="C1", qty=100, at=NOW, item="WATER", batch="B1", score=80):
    return Allocation(at, rid, camp, item, score, batch, qty, ("BR-30",))


def test_driver_limit_refusal_and_eta_duration():
    vehicles = {"V1": Vehicle("V1", "D1", VehicleType.TRUCK, 5000, 30, duty_hours_today=11.5),
                "V2": Vehicle("V2", "D1", VehicleType.TRUCK, 5000, 30)}
    engine = setup_dispatch(vehicles=vehicles)
    rows = engine.plan(NOW, [allocation()])
    assert rows[0]["vehicle_id"] == "V2"
    assert rows[0]["trip_hours"] == 1.5
    assert rows[0]["eta_ts"] == NOW + timedelta(hours=1.25)
    assert any(r["vehicle_id"] == "V1" and r["reason"] == "DUTY_LIMIT" for r in engine.refusals)


def test_partial_road_halves_payload_and_retries_remainder():
    engine = setup_dispatch(road=RoadStatus.PARTIAL)
    line = allocation(qty=3000)
    first = engine.plan(NOW, [line])
    assert sum(row["qty"] for row in first) == 2500
    second = engine.plan(NOW + timedelta(hours=6))
    assert sum(row["qty"] for row in second) == 500
    assert len({r["trip_id"] for r in first + second}) == 2


def test_combine_camps_within_ten_kilometres():
    engine = setup_dispatch()
    rows = engine.plan(NOW, [allocation("R1", "C1", 100), allocation("R2", "C2", 100, batch="B2")])
    assert len(rows) == 2
    assert len({row["trip_id"] for row in rows}) == 1
    assert rows[0]["route"] == "D1>C1>C2>D1"
    assert rows[0]["trip_hours"] == (7.5 + 3 + 8) / 30 + 1


def test_helicopter_sortie_limit_and_blocked_zone_rules():
    camps = {f"C{i}": Camp(f"C{i}", "Z1", 100, 50) for i in range(1, 6)}
    distances = {("D1", cid): 1 for cid in camps}
    for a in camps:
        for b in camps:
            if a != b:
                distances[(a, b)] = 20
    heli = Vehicle("H1", "D1", VehicleType.HELICOPTER, 2000, 120)
    engine = setup_dispatch(road=RoadStatus.BLOCKED, vehicles={"H1": heli}, camps=camps, distances=distances)
    lines = [allocation(f"R{i}", f"C{i}", 1, batch=f"B{i}") for i in range(1, 6)]
    rows = engine.plan(NOW, lines)
    assert len(rows) == 4
    assert heli.sorties_today == 4
    assert any(refusal["reason"] == "SORTIE_LIMIT" for refusal in engine.refusals)


def test_batch_expiry_uses_actual_eta_and_48_hour_reachability_limit():
    engine = setup_dispatch(distances={("D1", "C1"): 165})
    managed = ManagedRequest(Request("R1", "C1", "WATER", 10, Urgency.HIGH, NOW), 10, 10, 10)
    batch = StockBatch("B1", "WATER", "D1", 10, NOW, NOW + timedelta(hours=48))
    assert engine.can_deliver_before_expiry(batch, managed, NOW)
    too_soon = StockBatch("B2", "WATER", "D1", 10, NOW, NOW + timedelta(hours=6))
    assert not engine.can_deliver_before_expiry(too_soon, managed, NOW)


def test_final_consolidated_eta_refuses_batch_that_expires_at_arrival():
    from src.services.inventory_manager import InventoryManager
    inventory = InventoryManager()
    item = Item("WATER", "Water", "litre", 1, 100, ItemClass.LIFE_SAVING, unit_weight_kg=1)
    inventory.register_item(item)
    expiry = NOW + timedelta(hours=1.25)
    batch = StockBatch("B1", "WATER", "D1", 100, NOW, expiry)
    inventory.add_batch(batch)
    engine = DispatchEngine({"V1": Vehicle("V1", "D1", VehicleType.TRUCK, 5000, 30)},
        {"C1": Camp("C1", "Z1", 500, 300)},
        {"Z1": Zone("Z1", road_status=RoadStatus.OPEN, serving_depot_id="D1")},
        {"WATER": item}, {("D1", "C1"): 7.5}, inventory_manager=inventory)
    assert engine.plan(NOW, [allocation()]) == []
    assert engine.refusals[0]["reason"] == "BATCH_EXPIRES_BEFORE_ARRIVAL"
    assert engine.pending[0].remaining == 100

from datetime import datetime, timedelta, timezone

from src.main import run_application
from src.engines.allocation_engine import Allocation
from src.engines.dispatch_engine import DispatchEngine
from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.models.request import Request, Urgency
from src.models.stock_batch import StockBatch
from src.models.vehicle import Vehicle, VehicleType
from src.models.zone import RoadStatus, Zone
from src.services.request_manager import ManagedRequest


def test_vehicle_return_time_survives_daily_duty_reset():
    day_one = datetime(2026, 8, 10, 21, tzinfo=timezone.utc)
    next_cycle = datetime(2026, 8, 11, 3, tzinfo=timezone.utc)
    camp = Camp("C1", "Z1", 500, 100)
    item = Item("WATER", "Water", "litre", 1, 100, ItemClass.LIFE_SAVING,
                unit_weight_kg=1)
    vehicles = {
        "V1": Vehicle("V1", "D1", VehicleType.TRUCK, 5000, 30),
        "V2": Vehicle("V2", "D1", VehicleType.TRUCK, 5000, 30),
    }
    engine = DispatchEngine(vehicles, {"C1": camp},
        {"Z1": Zone("Z1", road_status=RoadStatus.OPEN, serving_depot_id="D1")},
        {"WATER": item}, {("D1", "C1"): 120})

    first = Allocation(day_one, "R1", "C1", "WATER", 80, "B1", 1, ("BR-30",))
    first_manifest = engine.plan(day_one, [first])
    assert first_manifest[0]["vehicle_id"] == "V1"
    assert first_manifest[0]["return_ts"] == datetime(2026, 8, 11, 6, tzinfo=timezone.utc)

    second = Allocation(next_cycle, "R2", "C1", "WATER", 80, "B2", 1, ("BR-30",))
    second_manifest = engine.plan(next_cycle, [second])

    assert second_manifest[0]["vehicle_id"] == "V2"
    assert second_manifest[0]["depart_ts"] == next_cycle


def test_long_lived_stock_can_wait_for_daily_driver_duty_reset():
    cycle = datetime(2026, 8, 11, 21, tzinfo=timezone.utc)
    camp = Camp("C1", "Z1", 500, 100)
    item = Item("FOODPKT", "Food packet", "packet", 1, 100,
                ItemClass.FOOD, unit_weight_kg=0.5)
    vehicle = Vehicle("B1", "D1", VehicleType.BOAT, 1000, 20,
                      duty_hours_today=12)
    engine = DispatchEngine({"B1": vehicle}, {"C1": camp},
        {"Z1": Zone("Z1", road_status=RoadStatus.BLOCKED, serving_depot_id="D1")},
        {"FOODPKT": item}, {("D1", "C1"): 45})
    managed = ManagedRequest(Request("R1", "C1", "FOODPKT", 100,
        Urgency.NORMAL, cycle), 100, 100, 100)
    batch = StockBatch("B1", "FOODPKT", "D1", 300, cycle,
                       cycle + timedelta(days=7))

    assert engine.can_deliver_before_expiry(batch, managed, cycle)


def test_near_expiry_stock_does_not_use_future_duty_reset_for_reachability():
    cycle = datetime(2026, 8, 11, 21, tzinfo=timezone.utc)
    camp = Camp("C1", "Z1", 500, 100)
    item = Item("FOODPKT", "Food packet", "packet", 1, 100,
                ItemClass.FOOD, unit_weight_kg=0.5)
    vehicle = Vehicle("B1", "D1", VehicleType.BOAT, 1000, 20,
                      duty_hours_today=12)
    engine = DispatchEngine({"B1": vehicle}, {"C1": camp},
        {"Z1": Zone("Z1", road_status=RoadStatus.BLOCKED, serving_depot_id="D1")},
        {"FOODPKT": item}, {("D1", "C1"): 45})
    managed = ManagedRequest(Request("R1", "C1", "FOODPKT", 100,
        Urgency.NORMAL, cycle), 100, 100, 100)
    batch = StockBatch("B1", "FOODPKT", "D1", 300, cycle,
                       cycle + timedelta(hours=47))

    assert not engine.can_deliver_before_expiry(batch, managed, cycle)


def test_long_lived_stock_is_rejected_when_future_vehicle_eta_misses_expiry():
    cycle = datetime(2026, 8, 11, 21, tzinfo=timezone.utc)
    camp = Camp("C1", "Z1", 500, 100)
    item = Item("FOODPKT", "Food packet", "packet", 1, 100,
                ItemClass.FOOD, unit_weight_kg=0.5)
    vehicle = Vehicle("B1", "D1", VehicleType.BOAT, 1000, 20,
                      duty_hours_today=12)
    engine = DispatchEngine({"B1": vehicle}, {"C1": camp},
        {"Z1": Zone("Z1", road_status=RoadStatus.BLOCKED, serving_depot_id="D1")},
        {"FOODPKT": item}, {("D1", "C1"): 45})
    managed = ManagedRequest(Request("R1", "C1", "FOODPKT", 100,
        Urgency.NORMAL, cycle), 100, 100, 100)
    engine.available_at["B1"] = cycle + timedelta(days=3)
    batch = StockBatch("B1", "FOODPKT", "D1", 300, cycle,
                       cycle + timedelta(days=2))

    assert not engine.can_deliver_before_expiry(batch, managed, cycle)


def test_sample_allocates_long_lived_stock_to_requests_waiting_for_duty_reset(tmp_path):
    result = run_application("data/input", tmp_path / "output")
    allocations = result["components"]["allocation"].records

    assert any(a.request_id == "RQ-039" and a.batch_id == "B-033" and a.qty == 300
               for a in allocations)
    assert any(a.request_id == "RQ-097" and a.batch_id == "B-037" and a.qty == 264
               for a in allocations)
    assert len(result["components"]["delivery"].processed_ids) == 88
    assert not result["command_errors"]


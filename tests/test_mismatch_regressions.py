from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.engines.allocation_engine import Allocation
from src.engines.dispatch_engine import DispatchEngine
from src.engines.priority_engine import PriorityEngine
from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.models.request import Request, Urgency
from src.models.vehicle import Vehicle, VehicleType
from src.models.zone import RoadStatus, Zone
from src.services.request_manager import RequestManager


NOW = datetime(2026, 8, 10, 15, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_priority_engine_observes_delivery_history_updates():
    camp = Camp("C1", "Z1", 100, 50, opened_ts=NOW - timedelta(days=5))
    item = Item("WATER", "Water", "litre", 1, 100, ItemClass.LIFE_SAVING)
    managed = RequestManager({"C1": camp}, {"WATER": item}).register(
        Request("R1", "C1", "WATER", 10, Urgency.NORMAL, NOW))
    history = {}
    engine = PriorityEngine({"C1": camp}, {"Z1": Zone("Z1", severity_level=1)}, history)
    history[("C1", "WATER")] = NOW - timedelta(hours=6)
    assert engine.score(managed, NOW) == 16


def test_dispatch_uses_vehicle_id_when_candidates_are_available_at_cycle_start():
    camps = {"C1": Camp("C1", "Z1", 100, 50)}
    zones = {"Z1": Zone("Z1", road_status=RoadStatus.OPEN, serving_depot_id="D1")}
    items = {"WATER": Item("WATER", "Water", "litre", 1, 100, ItemClass.LIFE_SAVING)}
    vehicles = {
        "A-1": Vehicle("A-1", "D1", VehicleType.TRUCK, 5000, 30),
        "Z-1": Vehicle("Z-1", "D1", VehicleType.TRUCK, 5000, 30),
    }
    engine = DispatchEngine(vehicles, camps, zones, items, {("D1", "C1"): 5})
    engine.begin_cycle(NOW)
    engine.available_at["A-1"] = NOW - timedelta(hours=1)
    engine.available_at["Z-1"] = NOW - timedelta(hours=2)
    line = Allocation(NOW, "R1", "C1", "WATER", 50, "B1", 1, ("BR-30",))
    rows = engine.plan(NOW, [line])
    assert rows[0]["vehicle_id"] == "A-1"
    assert rows[0]["depart_ts"] == NOW

from datetime import datetime, timedelta, timezone

from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.models.request import Request, Urgency
from src.models.zone import Zone
from src.services.request_manager import RequestManager
from src.engines.priority_engine import PriorityEngine


NOW = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)


def test_score_components_wait_cap_and_band():
    camp = Camp("C1", "Z1", 100, 50, vulnerable_count=20, opened_ts=NOW - timedelta(hours=66))
    item = Item("WATER", "Water", "litre", 3, 100, ItemClass.LIFE_SAVING)
    managed = RequestManager({"C1": camp}, {"WATER": item}).register(
        Request("R1", "C1", "WATER", 10, Urgency.CRITICAL, NOW, 0))
    engine = PriorityEngine({"C1": camp}, {"Z1": Zone("Z1", severity_level=4)})
    assert engine.score(managed, NOW) == 40 + 25 + 6 + 10
    assert engine.band(engine.score(managed, NOW)) == 8


def test_tie_break_occupancy_then_camp_id():
    camps = {"C1": Camp("C1", "Z1", 100, 70, opened_ts=NOW),
             "C2": Camp("C2", "Z1", 100, 80, opened_ts=NOW),
             "C3": Camp("C3", "Z1", 100, 80, opened_ts=NOW)}
    items = {"I": Item("I", "Item", "unit", .1, 100, ItemClass.FOOD)}
    manager = RequestManager(camps, items)
    requests = [manager.register(Request("R" + cid, cid, "I", 1, Urgency.NORMAL, NOW))
                for cid in ("C1", "C2", "C3")]
    engine = PriorityEngine(camps, {"Z1": Zone("Z1", severity_level=1)})
    ranked = engine.rank(requests, NOW)
    assert [r.request.camp_id for _, r in ranked] == ["C2", "C3", "C1"]


def test_last_delivery_for_item_overrides_camp_open_time():
    camp = Camp("C1", "Z1", 100, 100, opened_ts=NOW - timedelta(days=5))
    item = Item("I", "Item", "unit", .1, 100, ItemClass.FOOD)
    managed = RequestManager({"C1": camp}, {"I": item}).register(
        Request("R", "C1", "I", 1, Urgency.NORMAL, NOW))
    engine = PriorityEngine({"C1": camp}, {"Z1": Zone("Z1")},
                            {("C1", "I"): NOW - timedelta(hours=12)})
    assert engine.score(managed, NOW) == 10 + 5 + 0 + 2

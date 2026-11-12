from datetime import datetime, timezone
import pytest

from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.models.request import Request, Urgency
from src.services.request_manager import RequestManager
from src.services.command_processor import CommandProcessor


NOW = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)


def setup_manager():
    camp = Camp("C1", "Z1", 100, 20, opened_ts=NOW)
    item = Item("WATER", "Water", "litre", 3, 100, ItemClass.LIFE_SAVING)
    return RequestManager({"C1": camp}, {"WATER": item})


def req(rid, qty=200, stock=0):
    return Request(rid, "C1", "WATER", qty, Urgency.HIGH, NOW, stock)


def test_need_rounding_and_nonnegative():
    assert RequestManager.calculate_need(3, .5, 1) == 2
    assert RequestManager.calculate_need(1, .5, 5) == 0


def test_trimming_and_partial_then_complete():
    manager = setup_manager()
    managed = manager.register(req("R1"))
    assert managed.need == 120
    assert managed.original_quantity == 200
    assert managed.trimmed_quantity == 120
    assert managed.status == "TRIMMED"
    manager.record_allocation("R1", 40)
    assert managed.open_quantity == 80 and managed.status == "PARTIAL"
    manager.record_allocation("R1", 80)
    assert managed.open_quantity == 0 and managed.status == "FULFILLED"


def test_superseding_request_and_open_request_retention():
    manager = setup_manager()
    first = manager.register(req("R1", 80))
    manager.record_allocation("R1", 20)
    second = manager.register(req("R2", 60))
    assert first.status == "SUPERSEDED"
    assert second.open_quantity == 60
    assert manager.open_requests() == [second]


def test_invalid_registration_and_allocation():
    manager = setup_manager()
    with pytest.raises(ValueError):
        manager.register(req("R1", qty=0))
    managed = manager.register(req("R2", qty=20))
    with pytest.raises(ValueError):
        manager.record_allocation("R2", managed.open_quantity + 1)


def test_command_processor_can_register_with_request_manager():
    manager = setup_manager()
    processor = CommandProcessor(
        request_rows=[{"request_id": "R1", "camp_id": "C1", "item_id": "WATER",
                       "qty": "200", "urgency": "HIGH", "stock_on_hand": "0",
                       "request_ts": "2026-08-10 03:00:00"}],
        camps=manager.camps,
        items=manager.items,
        request_manager=manager,
    )
    processor.execute_command("REQUEST|R1")
    assert manager.requests["R1"].trimmed_quantity == 120

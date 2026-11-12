from datetime import datetime, timezone

from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.services.overflow_manager import OverflowManager
from src.services.request_manager import RequestManager
from src.services.command_processor import CommandProcessor


NOW = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)


def managers(camps):
    tarp = Item("TARP", "Tarpaulin", "unit", .1, 100, ItemClass.SHELTER)
    request_manager = RequestManager(camps, {"TARP": tarp})
    return OverflowManager(camps, {"TARP": tarp}, request_manager,
                           {("C1", "C2"): 3, ("C1", "C3"): 1})


def test_exact_120_percent_does_not_trigger_and_excess_uses_tarpaulin_norm():
    camp = Camp("C1", "Z1", 250, 280)
    overflow = managers({"C1": camp})
    result = overflow.register_arrival("C1", NOW, 20)
    assert camp.occupancy == 300
    assert result["overflow_request_id"] is None
    result = overflow.register_arrival("C1", NOW, 18)
    request = overflow.request_manager.requests[result["overflow_request_id"]].request
    assert camp.occupancy == 318
    assert request.quantity == 4
    assert request.urgency.value == "HIGH"


def test_exact_150_percent_is_not_redirected():
    camp = Camp("C1", "Z1", 100, 145)
    other = Camp("C2", "Z1", 100, 50)
    overflow = managers({"C1": camp, "C2": other})
    result = overflow.register_arrival("C1", NOW, 5)
    assert result["redirected_to"] is None
    assert camp.occupancy == 150


def test_above_150_redirects_to_nearest_available_camp():
    camp = Camp("C1", "Z1", 100, 151)
    farther = Camp("C2", "Z1", 100, 20)
    nearer = Camp("C3", "Z1", 100, 20)
    overflow = managers({"C1": camp, "C2": farther, "C3": nearer})
    result = overflow.register_arrival("C1", NOW, 5)
    assert result["redirected_to"] == "C3"
    assert camp.occupancy == 151
    assert nearer.occupancy == 25


def test_redirection_ignores_other_zones():
    camp = Camp("C1", "Z1", 100, 151)
    other = Camp("C2", "Z2", 100, 10)
    overflow = managers({"C1": camp, "C2": other})
    result = overflow.register_arrival("C1", NOW, 5)
    assert result["redirected_to"] is None
    assert other.occupancy == 10


def test_command_processor_uses_optional_overflow_manager():
    camp = Camp("C1", "Z1", 100, 121)
    overflow = managers({"C1": camp})
    processor = CommandProcessor(camps={"C1": camp}, overflow_manager=overflow)
    result = processor.execute_command("ARRIVAL|C1|2026-08-10 03:00:00|2")
    assert camp.occupancy == 123
    assert result["overflow_request_id"] == "AUTO-01"


from datetime import datetime
from zoneinfo import ZoneInfo
from src.models.zone import Zone, RoadStatus
import pytest

from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.services.command_processor import (
    CommandProcessor,
    CommandProcessorError
)
from src.services.inventory_manager import InventoryManager


IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def processor():
    return CommandProcessor()


def test_parse_request(processor):
    result = processor.parse_command("REQUEST|RQ-001")

    assert result.command_type == "REQUEST"
    assert result.arguments == ["RQ-001"]


def test_parse_verify(processor):
    result = processor.parse_command(
        "VERIFY|B-031|2026-08-11 10:00:00"
    )

    assert result.command_type == "VERIFY"
    assert len(result.arguments) == 2


def test_parse_arrival(processor):
    result = processor.parse_command(
        "ARRIVAL|C-001|2026-08-11 10:00:00|100"
    )

    assert result.command_type == "ARRIVAL"
    assert result.arguments[2] == "100"


def test_parse_print_command(processor):
    result = processor.parse_command("PRINT_ALLOCATIONS")

    assert result.command_type == "PRINT_ALLOCATIONS"
    assert result.arguments == []


def test_reject_unknown_command(processor):
    with pytest.raises(CommandProcessorError):
        processor.parse_command("UNKNOWN|123")


def test_reject_missing_arguments(processor):
    with pytest.raises(CommandProcessorError):
        processor.parse_command("REQUEST")


def test_reject_extra_arguments(processor):
    with pytest.raises(CommandProcessorError):
        processor.parse_command("REQUEST|RQ-001|EXTRA")


def test_reject_empty_argument(processor):
    with pytest.raises(CommandProcessorError):
        processor.parse_command("REQUEST|")


def test_parse_commands_preserves_order(processor):
    commands = [
        "REQUEST|RQ-001",
        "RECEIVE|RC-001",
        "VERIFY|B-001|2026-08-11 10:00:00",
        "CYCLE|2026-08-11 11:00:00"
    ]

    results = processor.parse_commands(commands)

    assert [
        result.command_type for result in results
    ] == [
        "REQUEST",
        "RECEIVE",
        "VERIFY",
        "CYCLE"
    ]


# --------------------------------------------------
# Test helper functions
# --------------------------------------------------

def create_test_camp():
    return Camp(
        camp_id="C01",
        zone_id="Z1",
        camp_name="Bahadurpur Primary School",
        capacity=360,
        occupancy=300,
        children=66,
        elderly=42,
        pregnant=12,
        opened_ts=datetime(
            2026, 8, 8, 15, 0, tzinfo=IST
        )
    )


def create_test_item():
    return Item(
        item_id="WATER",
        name="Drinking water",
        unit="litre",
        unit_weight_kg=1.0,
        daily_norm=3,
        shelf_life_days=180,
        item_class=ItemClass.LIFE_SAVING,
        is_medicine=False
    )


def create_test_medicine():
    return Item(
        item_id="MED-01",
        name="Essential medicine",
        unit="tablet",
        unit_weight_kg=0.01,
        daily_norm=1,
        shelf_life_days=365,
        item_class=ItemClass.LIFE_SAVING,
        is_medicine=True
    )


def create_test_request_row(request_id="RQ-001"):
    return {
        "request_id": request_id,
        "camp_id": "C01",
        "item_id": "WATER",
        "qty": "1500",
        "urgency": "CRITICAL",
        "stock_on_hand": "300",
        "request_ts": "2026-08-10 01:00:00"
    }


def create_test_receipt_row(
    receipt_id="RC-001",
    batch_id="B-001",
    item_id="WATER",
    source="GOVT"
):
    return {
        "receipt_id": receipt_id,
        "batch_id": batch_id,
        "depot_id": "D01",
        "item_id": item_id,
        "qty": "100",
        "expiry_ts": "2026-09-01 10:00:00",
        "source": source,
        "received_ts": "2026-08-10 10:00:00"
    }


def create_test_inventory_manager(item=None):
    manager = InventoryManager()
    manager.register_item(item or create_test_item())
    return manager


# --------------------------------------------------
# REQUEST execution tests
# --------------------------------------------------

def test_execute_valid_request():
    processor = CommandProcessor(
        request_rows={"RQ-001": create_test_request_row()},
        camps={"C01": create_test_camp()},
        items={"WATER": create_test_item()}
    )

    request = processor.execute_request("RQ-001")

    assert request.request_id == "RQ-001"
    assert request.camp_id == "C01"
    assert request.item_id == "WATER"
    assert request.quantity == 1500
    assert request.urgency.value == "CRITICAL"
    assert request.stock_on_hand == 300
    assert request.requested_at.tzinfo is not None


def test_reject_unknown_request():
    processor = CommandProcessor()

    with pytest.raises(CommandProcessorError):
        processor.execute_request("RQ-999")


def test_reject_unknown_camp():
    processor = CommandProcessor(
        request_rows={"RQ-001": create_test_request_row()},
        camps={},
        items={"WATER": create_test_item()}
    )

    with pytest.raises(CommandProcessorError):
        processor.execute_request("RQ-001")


def test_reject_unknown_item():
    processor = CommandProcessor(
        request_rows={"RQ-001": create_test_request_row()},
        camps={"C01": create_test_camp()},
        items={}
    )

    with pytest.raises(CommandProcessorError):
        processor.execute_request("RQ-001")


def test_reject_duplicate_request_command():
    processor = CommandProcessor(
        request_rows={"RQ-001": create_test_request_row()},
        camps={"C01": create_test_camp()},
        items={"WATER": create_test_item()}
    )

    processor.execute_request("RQ-001")

    with pytest.raises(CommandProcessorError):
        processor.execute_request("RQ-001")


def test_new_request_supersedes_previous_request():
    first_row = create_test_request_row("RQ-001")
    second_row = create_test_request_row("RQ-005")
    second_row["qty"] = "2000"

    processor = CommandProcessor(
        request_rows={
            "RQ-001": first_row,
            "RQ-005": second_row
        },
        camps={"C01": create_test_camp()},
        items={"WATER": create_test_item()}
    )

    processor.execute_request("RQ-001")
    processor.execute_request("RQ-005")

    active = processor.active_requests[("C01", "WATER")]

    assert active.request_id == "RQ-005"
    assert active.quantity == 2000
    assert len(processor.request_history) == 2


# --------------------------------------------------
# RECEIVE execution tests
# --------------------------------------------------

def test_execute_valid_receipt():
    manager = create_test_inventory_manager()

    processor = CommandProcessor(
        inventory_manager=manager,
        receipt_rows={
            "RC-001": create_test_receipt_row()
        }
    )

    batch = processor.execute_receive("RC-001")

    assert batch.batch_id == "B-001"
    assert batch.item_id == "WATER"
    assert batch.quantity == 100
    assert "B-001" in manager.batches


def test_reject_unknown_receipt():
    manager = create_test_inventory_manager()

    processor = CommandProcessor(
        inventory_manager=manager,
        receipt_rows={}
    )

    with pytest.raises(CommandProcessorError):
        processor.execute_receive("RC-999")


def test_reject_duplicate_receipt():
    manager = create_test_inventory_manager()

    processor = CommandProcessor(
        inventory_manager=manager,
        receipt_rows={
            "RC-001": create_test_receipt_row()
        }
    )

    processor.execute_receive("RC-001")

    with pytest.raises(CommandProcessorError):
        processor.execute_receive("RC-001")


def test_donated_medicine_remains_quarantined():
    manager = create_test_inventory_manager(
        create_test_medicine()
    )

    receipt = create_test_receipt_row(
        item_id="MED-01",
        source="DONATION"
    )

    processor = CommandProcessor(
        inventory_manager=manager,
        receipt_rows={"RC-001": receipt}
    )

    batch = processor.execute_receive("RC-001")

    assert batch.is_donation is True
    assert batch.requires_verification is True
    assert batch.verified is False
    assert batch.is_quarantined is True


# --------------------------------------------------
# VERIFY execution tests
# --------------------------------------------------

def test_execute_valid_verification():
    manager = create_test_inventory_manager(
        create_test_medicine()
    )

    receipt = create_test_receipt_row(
        item_id="MED-01",
        source="DONATION"
    )

    manager.process_receipt(receipt)

    processor = CommandProcessor(
        inventory_manager=manager
    )

    batch = processor.execute_verify(
        "B-001",
        "2026-08-11 10:00:00"
    )

    assert batch.verified is True
    assert batch.requires_verification is False
    assert batch.is_quarantined is False

    assert "B-001" in manager.verification_times


def test_reject_premature_verification():
    manager = create_test_inventory_manager(
        create_test_medicine()
    )

    receipt = create_test_receipt_row(
        item_id="MED-01",
        source="DONATION"
    )

    manager.process_receipt(receipt)

    processor = CommandProcessor(
        inventory_manager=manager
    )

    with pytest.raises(CommandProcessorError):
        processor.execute_verify(
            "B-001",
            "2026-08-09 10:00:00"
        )

    assert manager.batches["B-001"].verified is False

def test_dispatch_request_command():
    processor = CommandProcessor(
        request_rows={"RQ-001": create_test_request_row()},
        camps={"C01": create_test_camp()},
        items={"WATER": create_test_item()}
    )

    result = processor.execute_command("REQUEST|RQ-001")

    assert result.request_id == "RQ-001"


def test_dispatch_receive_command():
    manager = create_test_inventory_manager()

    processor = CommandProcessor(
        inventory_manager=manager,
        receipt_rows={
            "RC-001": create_test_receipt_row()
        }
    )

    result = processor.execute_command("RECEIVE|RC-001")

    assert result.batch_id == "B-001"


def test_dispatch_verify_command():
    manager = create_test_inventory_manager(
        create_test_medicine()
    )

    receipt = create_test_receipt_row(
        item_id="MED-01",
        source="DONATION"
    )

    manager.process_receipt(receipt)

    processor = CommandProcessor(
        inventory_manager=manager
    )

    result = processor.execute_command(
        "VERIFY|B-001|2026-08-11 10:00:00"
    )

    assert result.verified is True

# --------------------------------------------------
# ARRIVAL execution tests
# --------------------------------------------------

def test_execute_valid_arrival():
    camp = create_test_camp()

    processor = CommandProcessor(
        camps={"C01": camp}
    )

    result = processor.execute_command(
        "ARRIVAL|C01|2026-08-11 10:00:00|100"
    )

    assert camp.occupancy == 400
    assert result["persons"] == 100
    assert result["previous_occupancy"] == 300
    assert result["new_occupancy"] == 400
    assert len(processor.arrival_history) == 1


def test_arrival_triggers_overflow():
    camp = create_test_camp()

    processor = CommandProcessor(
        camps={"C01": camp}
    )

    processor.execute_command(
        "ARRIVAL|C01|2026-08-11 10:00:00|150"
    )

    assert camp.occupancy == 450
    assert camp.is_overflow is True
    assert camp.requires_redirection is False


def test_arrival_triggers_redirection():
    camp = create_test_camp()

    processor = CommandProcessor(
        camps={"C01": camp}
    )

    processor.execute_command(
        "ARRIVAL|C01|2026-08-11 10:00:00|250"
    )

    assert camp.occupancy == 550
    assert camp.is_overflow is True
    assert camp.requires_redirection is True


def test_reject_arrival_unknown_camp():
    processor = CommandProcessor(camps={})

    with pytest.raises(CommandProcessorError):
        processor.execute_command(
            "ARRIVAL|C99|2026-08-11 10:00:00|100"
        )


@pytest.mark.parametrize("persons", ["0", "-10", "abc"])
def test_reject_invalid_arrival_persons(persons):
    camp = create_test_camp()

    processor = CommandProcessor(
        camps={"C01": camp}
    )

    with pytest.raises(CommandProcessorError):
        processor.execute_command(
            f"ARRIVAL|C01|2026-08-11 10:00:00|{persons}"
        )

    assert camp.occupancy == 300


# --------------------------------------------------
# ROAD_STATUS execution tests
# --------------------------------------------------

def test_execute_valid_road_status():
    zone = Zone(zone_id="Z1")

    processor = CommandProcessor(
        zones={"Z1": zone}
    )

    result = processor.execute_command(
        "ROAD_STATUS|Z1|2026-08-11 10:00:00|BLOCKED"
    )

    assert zone.road_status == RoadStatus.BLOCKED
    assert result["previous_status"] == RoadStatus.OPEN
    assert result["new_status"] == RoadStatus.BLOCKED
    assert len(processor.road_status_history) == 1


def test_road_status_can_be_updated():
    zone = Zone(zone_id="Z1")

    processor = CommandProcessor(
        zones={"Z1": zone}
    )

    processor.execute_command(
        "ROAD_STATUS|Z1|2026-08-11 10:00:00|BLOCKED"
    )

    processor.execute_command(
        "ROAD_STATUS|Z1|2026-08-11 11:00:00|PARTIAL"
    )

    assert zone.road_status == RoadStatus.PARTIAL
    assert len(processor.road_status_history) == 2


def test_reject_road_status_unknown_zone():
    processor = CommandProcessor(zones={})

    with pytest.raises(CommandProcessorError):
        processor.execute_command(
            "ROAD_STATUS|Z99|2026-08-11 10:00:00|BLOCKED"
        )


def test_reject_invalid_road_status():
    zone = Zone(zone_id="Z1")

    processor = CommandProcessor(
        zones={"Z1": zone}
    )

    with pytest.raises(CommandProcessorError):
        processor.execute_command(
            "ROAD_STATUS|Z1|2026-08-11 10:00:00|CLOSED"
        )

    assert zone.road_status == RoadStatus.OPEN


def test_road_status_accepts_all_valid_values():
    zone = Zone(zone_id="Z1")

    processor = CommandProcessor(
        zones={"Z1": zone}
    )

    for status in ["OPEN", "PARTIAL", "BLOCKED"]:
        processor.execute_command(
            f"ROAD_STATUS|Z1|2026-08-11 10:00:00|{status}"
        )

        assert zone.road_status == RoadStatus(status)

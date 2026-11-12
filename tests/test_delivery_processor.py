from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from src.engines.reconciliation_engine import ReconciliationEngine
from src.models.item import Item, ItemClass
from src.models.stock_batch import StockBatch
from src.models.vehicle import Vehicle, VehicleType
from src.services.delivery_processor import DeliveryProcessor, DeliveryProcessorError
from src.services.inventory_manager import InventoryManager


NOW = datetime(2026, 8, 10, 3, tzinfo=ZoneInfo("Asia/Kolkata"))
EXPIRY = NOW + timedelta(days=100)


def setup(delivered=98, returned=0, dispatched=100):
    inventory = InventoryManager()
    inventory.register_item(Item("WATER", "Water", "litre", 1, 365, ItemClass.LIFE_SAVING))
    inventory.add_batch(StockBatch("B1", "WATER", "D1", 40, NOW, EXPIRY))
    vehicle = Vehicle("V1", "D1", VehicleType.TRUCK, 5000, 30)
    vehicles = {"V1": vehicle}
    dispatch = type("Dispatch", (), {"manifests": [{"trip_id": "V1-T1", "vehicle_id": "V1",
        "depot_id": "D1", "camp_id": "C1", "item_id": "WATER", "batch_id": "B1",
        "qty": dispatched, "depart_ts": NOW}],
        "mark_delivered": lambda self, *args: None})()
    reconciliation = ReconciliationEngine(inventory, vehicles)
    rows = [{"delivery_id": "DL1", "trip_id": "V1-T1", "camp_id": "C1", "item_id": "WATER",
             "batch_id": "B1", "delivered_qty": str(delivered), "returned_qty": str(returned),
             "delivered_ts": "2026-08-10 06:00:00"}]
    return DeliveryProcessor(rows, dispatch, reconciliation), inventory, vehicle, reconciliation


def test_exactly_two_percent_is_not_discrepancy():
    processor, _, vehicle, reconciliation = setup(delivered=98)
    row = processor.process("DL1")
    assert row["short"] == 2 and row["status"] == "OK"
    assert vehicle.discrepancy_count == 0
    assert reconciliation.last_deliveries[("C1", "WATER")] is not None


def test_returns_restore_original_batch_without_changing_expiry():
    processor, inventory, _, _ = setup(delivered=90, returned=10)
    expiry = inventory.batches["B1"].expiry_date
    processor.process("DL1")
    assert inventory.batches["B1"].quantity == 50
    assert inventory.batches["B1"].expiry_date == expiry


def test_above_two_percent_tracks_discrepancies_and_grounds_vehicle():
    processor, _, vehicle, reconciliation = setup(delivered=97)
    for i in range(3):
        manifest = dict(processor.dispatch.manifests[0], trip_id=f"V1-T{i+1}")
        processor.dispatch.manifests.append(manifest)
        row = dict(processor.delivery_rows["DL1"], delivery_id=f"DL{i+1}", trip_id=f"V1-T{i+1}")
        processor.delivery_rows[row["delivery_id"]] = row
        processor.process(row["delivery_id"])
    assert vehicle.discrepancy_count == 3
    assert vehicle.is_grounded
    assert sum(r["status"] == "DISCREPANCY" for r in reconciliation.records) == 3


def test_missing_duplicate_and_overdelivered_rows_are_rejected_without_mutation():
    processor, inventory, _, _ = setup(delivered=90)
    before = inventory.batches["B1"].quantity
    processor.process("DL1")
    with pytest.raises(DeliveryProcessorError):
        processor.process("DL1")
    with pytest.raises(DeliveryProcessorError):
        processor.process("MISSING")
    processor.delivery_rows["DL2"] = dict(processor.delivery_rows["DL1"], delivery_id="DL2", delivered_qty="90")
    with pytest.raises(DeliveryProcessorError):
        processor.process("DL2")
    bad, bad_inventory, _, _ = setup(delivered=101)
    with pytest.raises(DeliveryProcessorError):
        bad.process("DL1")
    assert bad_inventory.batches["B1"].quantity == 40
    assert inventory.batches["B1"].quantity == before

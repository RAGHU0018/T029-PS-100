from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.engines.reconciliation_engine import ReconciliationEngine
from src.models.delivery import Delivery
from src.models.item import Item, ItemClass
from src.models.stock_batch import StockBatch
from src.models.vehicle import Vehicle, VehicleType
from src.services.inventory_manager import InventoryManager


NOW = datetime(2026, 8, 10, 3, tzinfo=ZoneInfo("Asia/Kolkata"))


def engine():
    inventory = InventoryManager()
    inventory.register_item(Item("WATER", "Water", "litre", 1, 365, ItemClass.LIFE_SAVING))
    inventory.add_batch(StockBatch("B1", "WATER", "D1", 10, NOW, NOW + timedelta(days=30)))
    vehicle = Vehicle("V1", "D1", VehicleType.TRUCK, 5000, 30)
    return ReconciliationEngine(inventory, {"V1": vehicle}), inventory, vehicle


def test_reconcile_shortfall_threshold_and_return_inventory():
    reconciler, inventory, vehicle = engine()
    manifest = {"trip_id": "V1-T1", "vehicle_id": "V1", "qty": 100, "batch_id": "B1",
        "camp_id": "C1", "item_id": "WATER"}
    delivery = Delivery("DL1", vehicle_id="V1", depot_id="D1", camp_id="C1", item_id="WATER",
        batch_id="B1", trip_id="V1-T1", dispatched_quantity=100,
        delivered_quantity=88, returned_quantity=10,
        dispatch_time=NOW, delivered_at=NOW + timedelta(hours=3))
    record = reconciler.reconcile(delivery, manifest)
    assert record["short"] == 2 and record["status"] == "OK"
    assert inventory.batches["B1"].quantity == 20
    assert vehicle.discrepancy_count == 0


def test_write_off_reconciliation_record():
    reconciler, _, _ = engine()
    reconciler.record_write_offs([{"batch_id": "B9", "item_id": "WATER", "quantity": 12}])
    assert reconciler.records == [{"record": "WRITE_OFF", "trip_id": "", "camp_id": "",
        "item_id": "WATER", "batch_id": "B9", "dispatched": 0, "delivered": 0,
        "returned": 0, "short": 12, "status": "WRITTEN_OFF"}]

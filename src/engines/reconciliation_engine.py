"""Reconcile dispatch manifests with delivery reports (BR-50–54)."""
from datetime import datetime

from src.models.delivery import Delivery


class ReconciliationError(Exception):
    pass


class ReconciliationEngine:
    def __init__(self, inventory_manager, vehicles):
        self.inventory = inventory_manager
        self.vehicles = vehicles
        self.records = []
        self.delivery_history = []
        self.vehicle_discrepancies = []
        self.last_deliveries = {}

    def reconcile(self, delivery: Delivery, manifest: dict):
        if not isinstance(delivery, Delivery):
            raise ReconciliationError("A valid delivery is required.")
        dispatched = manifest["qty"]
        accounted = delivery.delivered_quantity + delivery.returned_quantity
        if accounted > dispatched:
            raise ReconciliationError("Delivered and returned quantity exceeds manifest quantity.")
        for field in ("trip_id", "camp_id", "item_id", "batch_id"):
            if getattr(delivery, field) != manifest[field]:
                raise ReconciliationError(f"Delivery does not match its manifest {field}.")
        batch = self.inventory.batches.get(delivery.batch_id)
        vehicle = self.vehicles.get(manifest["vehicle_id"])
        if batch is None or vehicle is None:
            raise ReconciliationError("Manifest references an unknown batch or vehicle.")
        short = dispatched - accounted
        discrepancy = dispatched > 0 and short / dispatched > .02
        # All checks are complete before state changes.
        batch.quantity += delivery.returned_quantity
        if discrepancy:
            vehicle.record_discrepancy()
            self.vehicle_discrepancies.append({"vehicle_id": vehicle.vehicle_id,
                "delivery_id": delivery.delivery_id, "timestamp": delivery.delivered_at,
                "discrepancy_count": vehicle.discrepancy_count})
        self.last_deliveries[(delivery.camp_id, delivery.item_id)] = delivery.delivered_at
        record = {"record": delivery.delivery_id, "trip_id": delivery.trip_id,
            "camp_id": delivery.camp_id, "item_id": delivery.item_id, "batch_id": delivery.batch_id,
            "dispatched": dispatched, "delivered": delivery.delivered_quantity,
            "returned": delivery.returned_quantity, "short": short,
            "status": "DISCREPANCY" if discrepancy else "OK"}
        self.records.append(record)
        self.delivery_history.append(delivery)
        return record

    def record_write_offs(self, write_offs):
        for row in write_offs:
            self.records.append({"record": "WRITE_OFF", "trip_id": "", "camp_id": "",
                "item_id": row["item_id"], "batch_id": row["batch_id"],
                "dispatched": 0, "delivered": 0, "returned": 0,
                "short": row["quantity"], "status": "WRITTEN_OFF"})

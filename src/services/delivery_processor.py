"""Execute DELIVERY commands against planned manifest lines."""
from datetime import datetime
from zoneinfo import ZoneInfo

from src.models.delivery import Delivery
from src.engines.reconciliation_engine import ReconciliationError


class DeliveryProcessorError(Exception):
    pass


class DeliveryProcessor:
    def __init__(self, delivery_rows, dispatch_engine, reconciliation_engine):
        self.delivery_rows = {row["delivery_id"]: row for row in (delivery_rows or [])}
        self.dispatch = dispatch_engine
        self.reconciliation = reconciliation_engine
        self.processed_ids = set()
        self.reconciled_manifest_keys = set()

    @staticmethod
    def _timestamp(value):
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        except (TypeError, ValueError) as exc:
            raise DeliveryProcessorError(f"Invalid delivery timestamp: {value}") from exc

    def process(self, delivery_id):
        if delivery_id in self.processed_ids:
            raise DeliveryProcessorError(f"Delivery '{delivery_id}' was already processed.")
        row = self.delivery_rows.get(delivery_id)
        if row is None:
            raise DeliveryProcessorError(f"Unknown delivery ID: {delivery_id}")
        try:
            delivered = int(row["delivered_qty"])
            returned = int(row["returned_qty"])
            delivered_ts = self._timestamp(row["delivered_ts"])
        except (KeyError, ValueError) as exc:
            raise DeliveryProcessorError(f"Invalid delivery '{delivery_id}': {exc}") from exc
        key = (row["trip_id"], row["camp_id"], row["item_id"], row["batch_id"])
        if key in self.reconciled_manifest_keys:
            raise DeliveryProcessorError("Matching manifest lines were already reconciled.")
        matches = [manifest for manifest in self.dispatch.manifests
                   if (manifest["trip_id"], manifest["camp_id"], manifest["item_id"], manifest["batch_id"]) == key]
        if not matches:
            raise DeliveryProcessorError("No planned manifest line matches this delivery.")
        dispatched = sum(manifest["qty"] for manifest in matches)
        manifest = matches[0]
        try:
            delivery = Delivery(delivery_id=delivery_id, trip_id=row["trip_id"],
                vehicle_id=manifest["vehicle_id"], depot_id=manifest["depot_id"],
                camp_id=row["camp_id"], item_id=row["item_id"], batch_id=row["batch_id"],
                dispatched_quantity=dispatched, delivered_quantity=delivered,
                returned_quantity=returned, dispatch_time=manifest["depart_ts"], delivered_at=delivered_ts)
            result = self.reconciliation.reconcile(delivery, manifest if len(matches) == 1 else
                {**manifest, "qty": dispatched})
        except (ValueError, ReconciliationError) as exc:
            raise DeliveryProcessorError(str(exc)) from exc
        self.processed_ids.add(delivery_id)
        self.reconciled_manifest_keys.add(key)
        self.dispatch.mark_delivered(*key)
        return result

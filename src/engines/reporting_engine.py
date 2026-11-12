"""Write the five evaluation CSV reports using the official column order."""
import csv
from pathlib import Path


class ReportingEngine:
    COLUMNS = {
        "allocations.csv": ("cycle_ts", "request_id", "camp_id", "item_id", "score", "batch_id", "qty", "rule_ids"),
        "manifests.csv": ("trip_id", "vehicle_id", "depot_id", "depart_ts", "return_ts", "trip_hours", "route", "camp_id", "item_id", "batch_id", "qty", "eta_ts", "escalated"),
        "dispatch_refusals.csv": ("cycle_ts", "allocation_line", "vehicle_id", "reason"),
        "reconciliation.csv": ("record", "trip_id", "camp_id", "item_id", "batch_id", "dispatched", "delivered", "returned", "short", "status"),
        "request_status.csv": ("request_id", "status", "need", "trimmed_qty", "allocated", "open"),
    }

    @staticmethod
    def _time(value):
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""

    def write(self, output_dir, allocation_engine, dispatch_engine, reconciliation_engine, request_manager):
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        output = {}
        rows = {
            "allocations.csv": [{"cycle_ts": r.cycle_ts, "request_id": r.request_id, "camp_id": r.camp_id,
                "item_id": r.item_id, "score": f"{r.score:.2f}", "batch_id": r.batch_id,
                "qty": r.qty, "rule_ids": ";".join(r.rule_ids)} for r in allocation_engine.records],
            "manifests.csv": dispatch_engine.manifests,
            "dispatch_refusals.csv": dispatch_engine.refusals,
            "reconciliation.csv": reconciliation_engine.records,
            "request_status.csv": [{"request_id": rid, "status": r.status, "need": r.need,
                "trimmed_qty": r.trimmed_quantity, "allocated": r.allocated_quantity, "open": r.open_quantity}
                for rid, r in request_manager.requests.items()] +
                [{"request_id": rid, "status": "REJECTED", "need": 0,
                  "trimmed_qty": 0, "allocated": 0, "open": 0}
                 for rid in request_manager.rejected if rid not in request_manager.requests],
        }
        datetime_fields = {"cycle_ts", "depart_ts", "return_ts", "eta_ts"}
        for filename, columns in self.COLUMNS.items():
            path = target / filename
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                for row in rows[filename]:
                    serialized = dict(row)
                    for name in datetime_fields:
                        if name in serialized:
                            serialized[name] = self._time(serialized[name])
                    if "escalated" in serialized:
                        serialized["escalated"] = str(serialized["escalated"]).lower()
                    writer.writerow(serialized)
            output[filename] = path
        return output

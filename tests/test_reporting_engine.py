import csv
from datetime import datetime, timezone

from src.engines.allocation_engine import Allocation
from src.engines.reporting_engine import ReportingEngine
from src.models.camp import Camp
from src.models.item import Item, ItemClass
from src.models.request import Request, Urgency
from src.services.request_manager import RequestManager


def test_writes_required_files_and_exact_headers(tmp_path):
    at = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)
    camp = Camp("C1", "Z1", 100, 50)
    item = Item("I", "Item", "unit", 1, 10, ItemClass.FOOD)
    manager = RequestManager({"C1": camp}, {"I": item})
    managed = manager.register(Request("R1", "C1", "I", 20, Urgency.HIGH, at))
    manager.record_allocation("R1", 5)
    manager.record_rejection("R2", "UNKNOWN_ITEM")
    allocation = type("AllocationEngineStub", (), {"records": [Allocation(at, "R1", "C1", "I", 50,
        "B1", 5, ("BR-30",))]})()
    dispatch = type("DispatchEngineStub", (), {"manifests": [], "refusals": []})()
    reconciliation = type("ReconciliationEngineStub", (), {"records": []})()
    output = ReportingEngine().write(tmp_path, allocation, dispatch, reconciliation, manager)
    assert set(output) == set(ReportingEngine.COLUMNS)
    for filename, columns in ReportingEngine.COLUMNS.items():
        with open(output[filename], newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            assert tuple(reader.fieldnames) == columns
            rows = list(reader)
            if filename == "request_status.csv":
                assert rows[0]["status"] == "PARTIAL"
                assert rows[1]["status"] == "REJECTED"

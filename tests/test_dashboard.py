from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard.data import load_csv, load_reports, opening_inventory_view, reconciliation_counts


def test_missing_dashboard_csv_is_non_fatal(tmp_path):
    frame, warning = load_csv(tmp_path, "missing.csv", ["record", "status"])

    assert frame.empty
    assert list(frame.columns) == ["record", "status"]
    assert "Missing" in warning


def test_reconciliation_kpis_are_derived_from_report_rows():
    report = pd.DataFrame([
        {"record": "DL-001", "status": "OK"},
        {"record": "DL-002", "status": "DISCREPANCY"},
        {"record": "WRITE_OFF", "status": "WRITTEN_OFF"},
    ])

    assert reconciliation_counts(report) == {
        "deliveries": 2, "ok": 1, "discrepancy": 1, "other": 0
    }


def test_opening_inventory_balance_uses_report_movements_and_quarantine():
    batches = pd.DataFrame([
        {"batch_id": "B1", "depot_id": "D1", "item_id": "WATER", "qty": 100,
         "expiry_ts": "2027-01-01 00:00:00", "source": "GOVT", "verified": "true"},
        {"batch_id": "B2", "depot_id": "D1", "item_id": "MEDKIT", "qty": 30,
         "expiry_ts": "2027-01-01 00:00:00", "source": "DONATION", "verified": "false"},
    ])
    allocations = pd.DataFrame([{"batch_id": "B1", "qty": 60}])
    reconciliation = pd.DataFrame([
        {"record": "DL-001", "batch_id": "B1", "returned": 5, "short": 5},
        {"record": "WRITE_OFF", "batch_id": "B1", "returned": 0, "short": 10},
    ])
    items = pd.DataFrame([
        {"item_id": "WATER", "medicine": "false"},
        {"item_id": "MEDKIT", "medicine": "true"},
    ])

    view = opening_inventory_view(
        batches, allocations, reconciliation, items, as_of="2026-08-01 00:00:00"
    ).set_index("batch_id")

    assert view.loc["B1", "projected_qty"] == 35
    assert view.loc["B1", "available_qty"] == 35
    assert view.loc["B2", "available_qty"] == 0
    assert view.loc["B2", "status"] == "Quarantined"


def test_dashboard_renders_with_current_report_files():
    app_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()

    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["OK"] == "82"
    assert metrics["Discrepancy"] == "6"


def test_dashboard_handles_missing_output_reports(tmp_path):
    reports, warnings = load_reports(tmp_path)

    assert len(reports) == 5
    assert len(warnings) == 5
    assert all(frame.empty for frame in reports.values())

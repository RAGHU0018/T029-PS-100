"""CSV loading and report-derived dashboard summaries."""

from pathlib import Path

import pandas as pd


REPORT_COLUMNS = {
    "allocations.csv": [
        "cycle_ts", "request_id", "camp_id", "item_id", "score", "batch_id", "qty", "rule_ids"
    ],
    "manifests.csv": [
        "trip_id", "vehicle_id", "depot_id", "depart_ts", "return_ts", "trip_hours", "route",
        "camp_id", "item_id", "batch_id", "qty", "eta_ts", "escalated"
    ],
    "dispatch_refusals.csv": ["cycle_ts", "allocation_line", "vehicle_id", "reason"],
    "reconciliation.csv": [
        "record", "trip_id", "camp_id", "item_id", "batch_id", "dispatched", "delivered",
        "returned", "short", "status"
    ],
    "request_status.csv": ["request_id", "status", "need", "trimmed_qty", "allocated", "open"],
}

INPUT_COLUMNS = {
    "camps.csv": [
        "camp_id", "zone_id", "camp_name", "capacity", "occupancy", "children", "elderly",
        "pregnant", "opened_ts"
    ],
    "zones.csv": ["zone_id", "zone_name", "severity", "road_status", "serving_depot_id"],
    "items.csv": [
        "item_id", "item_name", "unit", "unit_weight_kg", "daily_norm_per_person",
        "shelf_life_days", "priority_class", "medicine"
    ],
    "stock_batches.csv": ["batch_id", "depot_id", "item_id", "qty", "expiry_ts", "source", "verified"],
    "stock_receipts.csv": [
        "receipt_id", "batch_id", "depot_id", "item_id", "qty", "expiry_ts", "source", "received_ts"
    ],
}


def load_csv(directory, filename, required_columns):
    """Load a CSV and return (dataframe, warning); missing files are non-fatal."""
    path = Path(directory) / filename
    empty = pd.DataFrame(columns=required_columns)
    if not path.is_file():
        return empty, f"Missing {path}"
    try:
        frame = pd.read_csv(path)
    except (OSError, UnicodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        return empty, f"Could not read {path}: {exc}"

    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        return frame, f"{path.name} is missing required column(s): {', '.join(missing)}"
    return frame, None


def load_reports(output_dir):
    reports, warnings = {}, []
    for filename, columns in REPORT_COLUMNS.items():
        reports[filename], warning = load_csv(output_dir, filename, columns)
        if warning:
            warnings.append(warning)
    return reports, warnings


def load_metadata(input_dir):
    metadata, warnings = {}, []
    for filename, columns in INPUT_COLUMNS.items():
        metadata[filename], warning = load_csv(input_dir, filename, columns)
        if warning:
            warnings.append(warning)
    return metadata, warnings


def delivery_rows(reconciliation):
    """Exclude write-off audit rows from delivery totals."""
    if "record" not in reconciliation.columns:
        return reconciliation.iloc[0:0].copy()
    return reconciliation[reconciliation["record"].astype(str).str.startswith("DL-")].copy()


def reconciliation_counts(reconciliation):
    deliveries = delivery_rows(reconciliation)
    counts = deliveries.get("status", pd.Series(dtype=str)).fillna("").value_counts()
    return {
        "deliveries": len(deliveries),
        "ok": int(counts.get("OK", 0)),
        "discrepancy": int(counts.get("DISCREPANCY", 0)),
        "other": int(len(deliveries) - counts.get("OK", 0) - counts.get("DISCREPANCY", 0)),
    }


def opening_inventory_view(
    stock_batches, allocations, reconciliation, items, as_of=None, verified_batch_ids=None
):
    """Calculate a transparent balance for opening batches from report movements.

    This does not claim to include receipt-created batches: the five output reports
    do not expose receipt acceptance status or a complete inventory snapshot.
    """
    if stock_batches.empty:
        return pd.DataFrame(columns=[
            "batch_id", "depot_id", "item_id", "opening_qty", "allocated_qty", "returned_qty",
            "written_off_qty", "projected_qty", "available_qty", "expiry_ts", "status"
        ])

    batches = stock_batches.copy()
    batches["opening_qty"] = pd.to_numeric(batches["qty"], errors="coerce").fillna(0)
    allocated = allocations.copy()
    if not allocated.empty and {"batch_id", "qty"}.issubset(allocated.columns):
        allocated["qty"] = pd.to_numeric(allocated["qty"], errors="coerce").fillna(0)
        allocated = allocated.groupby("batch_id", as_index=False)["qty"].sum().rename(
            columns={"qty": "allocated_qty"}
        )
    else:
        allocated = pd.DataFrame(columns=["batch_id", "allocated_qty"])

    returned = pd.DataFrame(columns=["batch_id", "returned_qty"])
    written_off = pd.DataFrame(columns=["batch_id", "written_off_qty"])
    if not reconciliation.empty and "batch_id" in reconciliation.columns:
        rows = reconciliation.copy()
        for column in ("returned", "short"):
            if column not in rows.columns:
                rows[column] = 0
            rows[column] = pd.to_numeric(rows[column], errors="coerce").fillna(0)
        delivery = rows[rows.get("record", pd.Series(index=rows.index, dtype=str)).astype(str).str.startswith("DL-")]
        returned = delivery.groupby("batch_id", as_index=False)["returned"].sum().rename(
            columns={"returned": "returned_qty"}
        )
        writeoff = rows[rows.get("record", pd.Series(index=rows.index, dtype=str)).eq("WRITE_OFF")]
        written_off = writeoff.groupby("batch_id", as_index=False)["short"].sum().rename(
            columns={"short": "written_off_qty"}
        )

    view = batches.merge(allocated, on="batch_id", how="left")
    view = view.merge(returned, on="batch_id", how="left")
    view = view.merge(written_off, on="batch_id", how="left")
    for column in ("allocated_qty", "returned_qty", "written_off_qty"):
        if column not in view.columns:
            view[column] = 0
        view[column] = pd.to_numeric(view[column], errors="coerce").fillna(0)
    view["projected_qty"] = (
        view["opening_qty"] - view["allocated_qty"] + view["returned_qty"] - view["written_off_qty"]
    )
    view["available_qty"] = view["projected_qty"].clip(lower=0)

    medicine = items.set_index("item_id")["medicine"].astype(str).str.lower().eq("true") if not items.empty else pd.Series(dtype=bool)
    verified = view["verified"].astype(str).str.lower().eq("true")
    if verified_batch_ids:
        verified = verified | view["batch_id"].isin(verified_batch_ids)
    quarantined = (
        view["source"].astype(str).str.upper().eq("DONATION")
        & ~verified
        & view["item_id"].map(medicine).fillna(False)
    )
    expired = pd.Series(False, index=view.index)
    if as_of is not None:
        expired = pd.to_datetime(view["expiry_ts"], errors="coerce") <= pd.Timestamp(as_of)
    view.loc[quarantined | expired, "available_qty"] = 0
    view["status"] = "Available"
    view.loc[view["projected_qty"] < 0, "status"] = "Negative projected balance"
    view.loc[quarantined, "status"] = "Quarantined"
    view.loc[expired, "status"] = "Expired"
    return view[[
        "batch_id", "depot_id", "item_id", "opening_qty", "allocated_qty", "returned_qty",
        "written_off_qty", "projected_qty", "available_qty", "expiry_ts", "status"
    ]]

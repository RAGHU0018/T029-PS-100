"""Read-only Streamlit dashboard for existing PS-100 CSV reports."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.data import (  # noqa: E402
    INPUT_COLUMNS,
    REPORT_COLUMNS,
    load_metadata,
    load_reports,
    opening_inventory_view,
    reconciliation_counts,
)


st.set_page_config(
    page_title="T029-PS-100 Relief Operations",
    page_icon=":ambulance:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _number(frame, column):
    if column not in frame.columns:
        return pd.Series(0, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0)


def _cycle_metadata(commands_path):
    path = Path(commands_path)
    if not path.is_file():
        return 0, None, set()
    cycles, last_cycle, verified_batches = 0, None, set()
    try:
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            parts = raw.strip().split("|")
            if parts[0] == "CYCLE" and len(parts) == 2:
                cycles += 1
                last_cycle = parts[1]
            elif parts[0] == "VERIFY" and len(parts) >= 2:
                verified_batches.add(parts[1])
    except OSError:
        return 0, None, set()
    return cycles, last_cycle, verified_batches


def _filter_table(frame, key, height=360):
    if frame is None:
        frame = pd.DataFrame()
    query = st.text_input("Filter rows", key=f"filter-{key}", placeholder="Search any column")
    view = frame
    if query and not frame.empty:
        mask = frame.astype(str).apply(
            lambda column: column.str.contains(query, case=False, regex=False, na=False)
        ).any(axis=1)
        view = frame[mask]
    st.caption(f"Showing {len(view):,} of {len(frame):,} rows")
    st.dataframe(view, width="stretch", hide_index=True, height=height)


def _show_report(frame, filename, key=None):
    st.subheader(filename)
    _filter_table(frame, key or filename.replace(".", "-"), height=440)


st.title("Disaster Relief Operations")
st.caption("T029-PS-100 | Allocation, dispatch, inventory movement, and delivery reconciliation")

with st.sidebar:
    st.header("Report sources")
    output_dir = st.text_input("Output CSV directory", str(PROJECT_ROOT / "data" / "output"))
    input_dir = st.text_input("Input/reference CSV directory", str(PROJECT_ROOT / "data" / "input"))
    if st.button("Refresh report data", width="stretch"):
        st.rerun()
    st.caption("The dashboard reads CSV files only. It does not run the allocation or dispatch engine.")

reports, report_warnings = load_reports(output_dir)
metadata, metadata_warnings = load_metadata(input_dir)
for warning in report_warnings + metadata_warnings:
    st.warning(warning)

allocations = reports["allocations.csv"]
manifests = reports["manifests.csv"]
refusals = reports["dispatch_refusals.csv"]
reconciliation = reports["reconciliation.csv"]
requests = reports["request_status.csv"]
delivery_data = reconciliation[reconciliation.get(
    "record", pd.Series(index=reconciliation.index, dtype=str)
).astype(str).str.startswith("DL-")].copy()
counts = reconciliation_counts(reconciliation)
cycle_count, last_cycle, verified_batches = _cycle_metadata(Path(input_dir) / "commands.txt")

trip_count = int(manifests["trip_id"].nunique()) if "trip_id" in manifests else 0
allocated_units = int(_number(allocations, "qty").sum())
open_units = int(_number(requests, "open").sum())
open_request_count = int((_number(requests, "open") > 0).sum())

st.subheader("Operations overview")
cards = st.columns(6)
cards[0].metric("Camps", f"{len(metadata['camps.csv']):,}")
cards[1].metric("Zones", f"{len(metadata['zones.csv']):,}")
cards[2].metric("Trips planned", f"{trip_count:,}")
cards[3].metric("Deliveries accounted", f"{counts['deliveries']:,}")
cards[4].metric("OK", f"{counts['ok']:,}")
cards[5].metric("Discrepancy", f"{counts['discrepancy']:,}")
st.caption(
    f"Allocation reports show {allocated_units:,} units allocated. "
    f"{open_request_count:,} requests have {open_units:,} units still open. "
    f"Source cycles: {cycle_count:,}" + (f" | latest: {last_cycle}" if last_cycle else "")
)

overview, camp_zone, inventory, allocation_tab, dispatch_tab, delivery_tab, raw_reports = st.tabs([
    "Overview", "Camps & zones", "Inventory", "Allocations", "Dispatch", "Reconciliation", "All reports"
])

with overview:
    left, right = st.columns((1.2, 1))
    with left:
        st.subheader("Delivery outcomes")
        status_counts = pd.DataFrame({
            "Records": [counts["ok"], counts["discrepancy"], counts["other"]],
        }, index=["OK", "DISCREPANCY", "Other"])
        st.bar_chart(status_counts, color="#167d8d")
        st.caption("Counts are calculated from delivery rows in reconciliation.csv; write-off rows are excluded.")
    with right:
        st.subheader("Allocation by item")
        if not allocations.empty and {"item_id", "qty"}.issubset(allocations.columns):
            item_totals = allocations.assign(_qty=_number(allocations, "qty")).groupby(
                "item_id", as_index=True
            )["_qty"].sum().sort_values(ascending=False)
            st.bar_chart(item_totals, color="#d18c35")
        else:
            st.info("Allocation data is not available yet.")

with camp_zone:
    camps = metadata["camps.csv"].copy()
    zones = metadata["zones.csv"].copy()
    if not camps.empty and {"camp_id", "zone_id", "capacity", "occupancy"}.issubset(camps.columns):
        camps["capacity"] = _number(camps, "capacity")
        camps["occupancy"] = _number(camps, "occupancy")
        camps["occupancy_pct"] = (camps["occupancy"].div(camps["capacity"].replace(0, pd.NA)) * 100).fillna(0)
        if not zones.empty and {"zone_id", "zone_name", "road_status", "severity"}.issubset(zones.columns):
            camp_view = camps.merge(
                zones[["zone_id", "zone_name", "road_status", "severity"]],
                on="zone_id", how="left", validate="many_to_one"
            )
        else:
            camp_view = camps.copy()
        zone_summary = camp_view.groupby("zone_id", as_index=True).agg(
            camps=("camp_id", "count"), occupancy=("occupancy", "sum"), capacity=("capacity", "sum")
        )
        zone_summary["occupancy_pct"] = (
            zone_summary["occupancy"].div(zone_summary["capacity"].replace(0, pd.NA)) * 100
        ).fillna(0)
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.subheader("Occupancy by zone")
        st.bar_chart(zone_summary[["occupancy", "capacity"]])
        with chart_right:
            st.subheader("Zone conditions")
            if not zones.empty:
                _filter_table(zones, "zones", height=260)
            else:
                st.info("Zone reference file is not available.")
        st.subheader("Camp occupancy")
        _filter_table(camp_view, "camps", height=420)
    else:
        st.info("Camp overview requires camps.csv with camp, zone, capacity, and occupancy columns.")

with inventory:
    st.subheader("Opening batch balances")
    inventory_view = opening_inventory_view(
        metadata["stock_batches.csv"], allocations, reconciliation, metadata["items.csv"],
        as_of=last_cycle, verified_batch_ids=verified_batches
    )
    if not inventory_view.empty:
        inv_kpis = st.columns(3)
        inv_kpis[0].metric("Opening batch units", f"{int(_number(inventory_view, 'opening_qty').sum()):,}")
        inv_kpis[1].metric("Projected opening balance", f"{int(_number(inventory_view, 'projected_qty').sum()):,}")
        inv_kpis[2].metric("Usable opening units", f"{int(_number(inventory_view, 'available_qty').sum()):,}")
        if {"item_id", "available_qty"}.issubset(inventory_view.columns):
            by_item = inventory_view.groupby("item_id")["available_qty"].sum().sort_values(ascending=False)
            st.bar_chart(by_item, color="#167d8d")
        _filter_table(inventory_view, "opening-inventory", height=440)
    else:
        st.info("Opening stock batch data is not available.")
    st.caption(
        "Balances are calculated for stock_batches.csv opening batches using allocation, returned, and write-off "
        "report rows. Receipt-created batches are shown separately because these five reports do not include a "
        "receipt acceptance ledger or a complete ending-inventory snapshot."
    )
    receipts = metadata["stock_receipts.csv"]
    if not receipts.empty:
        with st.expander("Receipt records from input (listed quantities, not acceptance status)"):
            _filter_table(receipts, "receipt-input", height=300)

with allocation_tab:
    st.subheader("Allocated resources")
    if not allocations.empty and {"cycle_ts", "qty", "item_id", "camp_id"}.issubset(allocations.columns):
        chart_left, chart_right = st.columns(2)
        with chart_left:
            by_item = allocations.assign(_qty=_number(allocations, "qty")).groupby(
                "item_id", as_index=True
            )["_qty"].sum().sort_values(ascending=False)
            st.markdown("**Allocated quantity by item**")
            st.bar_chart(by_item, color="#d18c35")
        with chart_right:
            by_cycle = allocations.assign(
                _qty=_number(allocations, "qty"),
                _cycle=pd.to_datetime(allocations["cycle_ts"], errors="coerce"),
            ).dropna(subset=["_cycle"]).groupby("_cycle")["_qty"].sum().sort_index()
            st.markdown("**Allocation volume by cycle**")
            st.line_chart(by_cycle, color="#167d8d")
        by_camp = allocations.assign(_qty=_number(allocations, "qty")).groupby(
            "camp_id", as_index=True
        )["_qty"].sum().sort_values(ascending=False).head(10)
        st.markdown("**Top camps by allocated quantity**")
        st.bar_chart(by_camp, color="#167d8d")
    else:
        st.info("Allocation report is missing or contains no allocation rows.")
    _show_report(allocations, "allocations.csv", key="allocation-summary")

with dispatch_tab:
    st.subheader("Vehicle dispatch and trip manifests")
    if not manifests.empty and {"vehicle_id", "trip_id", "qty"}.issubset(manifests.columns):
        by_vehicle = manifests.groupby("vehicle_id").agg(
            trips=("trip_id", "nunique"), manifest_lines=("trip_id", "size"),
            planned_units=("qty", lambda values: pd.to_numeric(values, errors="coerce").fillna(0).sum()),
        ).sort_values("trips", ascending=False)
        st.bar_chart(by_vehicle[["trips"]], color="#167d8d")
        vehicle_ids = ["All vehicles"] + sorted(manifests["vehicle_id"].dropna().unique().tolist())
        selected_vehicle = st.selectbox("Filter by vehicle", vehicle_ids)
        selected_manifests = manifests if selected_vehicle == "All vehicles" else manifests[
            manifests["vehicle_id"] == selected_vehicle
        ]
        _filter_table(selected_manifests, "manifest-lines", height=430)
    else:
        st.info("Manifest data is not available yet.")
    with st.expander("Dispatch refusals"):
        _filter_table(refusals, "dispatch-refusals", height=320)

with delivery_tab:
    st.subheader("Delivery reconciliation")
    delivery_kpis = st.columns(3)
    delivery_kpis[0].metric("Accounted deliveries", f"{counts['deliveries']:,}")
    delivery_kpis[1].metric("OK", f"{counts['ok']:,}")
    delivery_kpis[2].metric("Discrepancy", f"{counts['discrepancy']:,}")
    if counts["discrepancy"]:
        st.warning(
            "DISCREPANCY means the exact planned quantity was reconciled and the shortfall exceeded the "
            "documented 2% threshold. These rows remain accounted and auditable."
        )
    discrepancy_rows = delivery_data[
        delivery_data.get("status", pd.Series(index=delivery_data.index, dtype=str)).eq("DISCREPANCY")
    ]
    if not discrepancy_rows.empty:
        st.markdown("**Discrepancy records**")
        _filter_table(discrepancy_rows, "discrepancy-rows", height=260)
    _show_report(delivery_data, "reconciliation.csv | deliveries", key="delivery-summary")

with raw_reports:
    st.subheader("Interactive output report tables")
    report_tabs = st.tabs(list(REPORT_COLUMNS))
    for tab, filename in zip(report_tabs, REPORT_COLUMNS):
        with tab:
            _show_report(reports[filename], filename, key=f"all-{filename.replace('.', '-')}")
    with st.expander("Request status report"):
        _show_report(requests, "request_status.csv")

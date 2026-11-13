# T029-PS-100

## Disaster Relief Resource Allocation and Priority Dispatch Engine

T029-PS-100 is a Python application for allocating relief supplies to camps and planning deliveries from depots. It processes requests, stock receipts, road and arrival changes, allocation cycles, and delivery records in command-file order. Allocation, dispatch, delivery, and inventory decisions are written to CSV reports for review.

The project implements PS-100 business rules BR-01 through BR-59 as documented in [docs/DESIGN_DOCUMENT.md](docs/DESIGN_DOCUMENT.md). The official sample pack, its data dictionary, edge cases, and output conventions are documented in [data/input/README.md](data/input/README.md).

## Current validation

- Python test suite: **159 passed** (154 existing project tests and 5 dashboard tests).
- Official sample: **16 cycles executed**; all **88 of 88 delivery records accounted for**; zero command errors.
- Reconciliation: **82 `OK`** and **6 `DISCREPANCY`** records. Discrepancy rows are reconciled and auditable; they are not rejected deliveries. Details are below and in [docs/DELIVERY_SCHEDULE_RECONSTRUCTION.md](docs/DELIVERY_SCHEDULE_RECONSTRUCTION.md).
- The application writes all five required output reports under `data/output/` by default.

These are results for the included official sample and current test suite. They do not guarantee identical results for untested input sets.

## Architecture

Commands are read and executed in file order. `CYCLE` triggers write-offs, allocation, and dispatch planning for the next six-hour window. Delivery commands reconcile only against manifests already planned when the command is reached.

| Component | Location | Responsibility |
|---|---|---|
| Application entry point | `src/main.py` | Loads the input pack, creates the domain state and services, processes commands, writes reports. |
| CSV data loader | `src/services/data_loader.py` | Reads the official CSV files and command stream. |
| Command processor | `src/services/command_processor.py` | Parses and executes request, receipt, verification, arrival, road-status, cycle, delivery, and print commands. |
| Domain models | `src/models/` | Represents camps, zones, depots, items, requests, stock batches, vehicles, and deliveries. |
| Inventory manager | `src/services/inventory_manager.py` | Tracks stock batches, receipts, verification, FEFO availability, expiry, and returns. |
| Request manager | `src/services/request_manager.py` | Validates requests, calculates need and trimming, tracks allocation/open quantities, and supersedes earlier requests. |
| Priority engine | `src/engines/priority_engine.py` | Scores and orders active requests using severity, urgency, vulnerability, waiting time, and documented tie-breaks. |
| Allocation engine | `src/engines/allocation_engine.py` | Applies item-class order, priority bands, fairness caps, proportional allocation, FEFO, and audit rule IDs. |
| Dispatch engine | `src/engines/dispatch_engine.py` | Selects eligible vehicles, checks capacity/duty/availability/expiry, consolidates camps, plans trips, and creates manifests/refusals. |
| Cycle engine | `src/engines/cycle_engine.py` | Coordinates expiry write-offs, allocation, and dispatch at each `CYCLE`. |
| Overflow manager | `src/services/overflow_manager.py` | Creates overflow shelter requests and redirects arrivals under the documented thresholds. |
| Delivery processor | `src/services/delivery_processor.py` | Matches delivery rows to planned trip, camp, item, and batch manifest lines. |
| Reconciliation engine | `src/engines/reconciliation_engine.py` | Validates delivered/returned amounts, records shortfalls/discrepancies, restores returns, and tracks vehicle history. |
| Reporting engine | `src/engines/reporting_engine.py` | Writes the five output CSVs using the official column order. |
| Read-only dashboard | `dashboard/app.py` | Displays the generated reports and reference input data; does not run or modify the application engines. |

## Requirements

- Python **3.10 or later**.
- Packages listed in [`requirements.txt`](requirements.txt): `pytest` for tests, `tzdata` for portable IANA timezone data, and `pandas`/`streamlit` for the dashboard.
- No database or network connection is required.

The application uses the Python standard library at runtime in addition to timezone data. Pytest is required to run the test suite.

## Setup and execution

Run commands from the repository root. The examples below use Windows PowerShell and work in the VS Code integrated terminal.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m src.main --input-dir data/input --output-dir data/output
```

If using Command Prompt, create the environment with `py -3.10 -m venv .venv`, activate it with `.venv\Scripts\activate.bat`, then run `python -m pip install -r requirements.txt`, `python -m pytest -v`, and `python -m src.main --input-dir data/input --output-dir data/output`.

In VS Code, open the repository root folder, select the `.venv` interpreter with **Python: Select Interpreter**, then run the commands in the integrated terminal. Activation is optional when calling `.venv\Scripts\python.exe` directly.

On macOS or Linux, use `python3 -m venv .venv`, `source .venv/bin/activate`, `python -m pip install -r requirements.txt`, `python -m pytest -v`, and `python -m src.main --input-dir data/input --output-dir data/output`.

The CLI prints the number of cycles and reports written. It returns a nonzero exit code when command errors occur; reports are still written so the results can be inspected. A normal official sample run prints `Completed 16 cycles; wrote 5 reports.` and no command errors.

### Run the read-only dashboard

After installing requirements and generating the reports, run this command from the repository root:

```powershell
\.venv\Scripts\Activate.ps1
streamlit run dashboard/app.py
```

If PowerShell activation is restricted, call the environment's executable directly: `.venv\Scripts\streamlit.exe run dashboard/app.py`.

The dashboard reads the five CSVs in `data/output/` and uses camp, zone, item, and opening batch reference files from `data/input/`. It does not execute a cycle or write operational reports. Missing report files are shown as warnings and the corresponding dashboard sections remain empty. The opening-stock panel reconciles opening batches against allocation, return, and write-off report rows; receipt-created batches are shown separately because the five output reports do not include a receipt acceptance ledger or a full ending-inventory snapshot.

The application overwrites report files with the same names in the selected output directory on each run. Preserve or copy any reports you need before rerunning with that directory.

## Input files

The default input directory is `data/input/`. CSV timestamps use local IST values in `YYYY-MM-DD HH:MM:SS` format without an offset; the application interprets them as `Asia/Kolkata`.

| File | Contents |
|---|---|
| `depots.csv` | Depot identifiers and names. |
| `zones.csv` | Zone severity, road status, and serving depot. Camps are supplied by their zone's serving depot. |
| `camps.csv` | Camp zone, capacity, current occupancy, vulnerable population counts, and opening timestamp. |
| `distances.csv` | Road distances between depots and camps and between camps; distances are symmetric. |
| `items.csv` | Item names, units, unit weights, daily per-person norms, shelf life, item class, and medicine flag. |
| `vehicles.csv` | Vehicle depot, type, capacity, speed, driver name, and duty hours already used at operation start. |
| `stock_batches.csv` | Opening stock batch quantities, depots, expiry, source, and verification state. |
| `stock_receipts.csv` | Receipts that create stock batches, with quantities, expiry, source, and receipt time. A `RECEIVE` command activates a receipt according to its rules. |
| `requests.csv` | Request ID, camp, item, requested quantity, urgency, reported stock-on-hand, and request time. A `REQUEST` command registers the row. |
| `deliveries.csv` | Delivery ID and claimed trip/camp/item/batch, delivered and returned quantities, and delivery timestamp. A `DELIVERY` command processes the row against the manifest available at that command position. |
| `commands.txt` | Ordered operations: requests, receipts, verification, arrivals, road-status changes, cycles, deliveries, and report-print commands. Blank lines and comments are ignored. |

See [data/input/README.md](data/input/README.md) for exact CSV columns, sample row counts, command formats, planted scenarios, and binding rule choices. Do not change the official schemas when preparing another input pack.

## Output reports

The default output directory is `data/output/`. Column names and ordering are fixed:

| File | Purpose | Columns, in order |
|---|---|---|
| `allocations.csv` | Allocated batch lines with request, score, quantity, and rule audit IDs. | `cycle_ts`, `request_id`, `camp_id`, `item_id`, `score`, `batch_id`, `qty`, `rule_ids` |
| `manifests.csv` | One row per dispatched trip line, including vehicle, route, quantities, ETA, and escalation state. | `trip_id`, `vehicle_id`, `depot_id`, `depart_ts`, `return_ts`, `trip_hours`, `route`, `camp_id`, `item_id`, `batch_id`, `qty`, `eta_ts`, `escalated` |
| `dispatch_refusals.csv` | Vehicle refusal reasons for an allocation line. | `cycle_ts`, `allocation_line`, `vehicle_id`, `reason` |
| `reconciliation.csv` | Delivery reconciliation rows and inventory write-off rows. | `record`, `trip_id`, `camp_id`, `item_id`, `batch_id`, `dispatched`, `delivered`, `returned`, `short`, `status` |
| `request_status.csv` | Current status and quantities for each registered or rejected request. | `request_id`, `status`, `need`, `trimmed_qty`, `allocated`, `open` |

The output formats follow the official sample README. The separate [docs/DELIVERY_DISPATCH_TRACE.csv](docs/DELIVERY_DISPATCH_TRACE.csv) is an investigation artifact, not one of the five application reports.

## Delivery status and discrepancies

Reconciliation checks that delivered plus returned quantity does not exceed the exact planned manifest quantity. It calculates `short = dispatched - delivered - returned`. A delivery is marked `DISCREPANCY` only when the shortfall is **strictly greater than 2%** of dispatched quantity; an exact 2% shortfall is not flagged. Returns are restored to their original batch.

In the validated sample, the six discrepancy records are **DL-004, DL-037, DL-039, DL-059, DL-063, and DL-087**. Each has a matching planned manifest and is included in the reconciliation report. `DISCREPANCY` describes a delivery variance; it does not mean the delivery was rejected or omitted. The other 82 deliveries are `OK`.

## Known assumptions and limitations

- The sample and documented bindings define local timestamps as IST (`Asia/Kolkata`); timestamps are not treated as UTC.
- Commands execute in file order. A delivery can only match a manifest already planned when its command is processed; the application does not invent or retrospectively add trips.
- Priority, fairness, FEFO, service-depot, road, vehicle, duty, capacity, six-hour cycle window, and discrepancy behavior follow the documented rules and sample README bindings. See the design document for the authoritative rule set.
- If a vehicle is temporarily duty-limited, long-lived stock may remain eligible when a compatible vehicle can serve it after the next daily cycle and estimated arrival is before expiry. Near-expiry stock keeps the stricter reachability constraint. Actual dispatch still checks ETA against expiry.
- A `CYCLE` plans dispatch for its next six-hour window. Irregularly spaced cycle inputs are accepted only if timestamps increase; the included official sample uses six-hour steps.
- The sample README does not provide golden output files. Validation is against its documented rules, planted cases, and the project test suite.
- `manifests.csv` records trip lines, not request IDs. Allocation lineage can be followed by camp, item, batch, and cycle in `allocations.csv`; the supplemental delivery trace joins the sample records for audit.
- Reports are overwritten when rerunning into the same output directory. Use `--output-dir` to retain separate runs.

## Project documentation

- [Business rules and design](docs/DESIGN_DOCUMENT.md)
- [Model schema alignment](docs/MODEL_SCHEMA_UPDATE.md)
- [Final delivery schedule reconstruction and validation](docs/DELIVERY_SCHEDULE_RECONSTRUCTION.md)
- [Historical delivery timeline investigation](docs/DELIVERY_TIMELINE_ROOT_CAUSE.md)

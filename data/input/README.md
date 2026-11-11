# PS-100 – Disaster Relief Resource Allocation and Priority Dispatch Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T029.

## Files

| File | What it holds | Row count |
|---|---|---|
| `depots.csv` | 3 depots | 3 data rows |
| `zones.csv` | 8 flood-affected zones: severity, road status and serving depot | 8 data rows |
| `camps.csv` | 15 relief camps: capacity, occupancy, vulnerable persons and opening time | 15 data rows |
| `distances.csv` | Road km depot-camp and camp-camp | 150 data rows |
| `items.csv` | 12 relief items: unit, weight, daily norm per person, shelf life, class, medicine flag | 12 data rows |
| `vehicles.csv` | 10 vehicles (trucks, boats, helicopter) with duty hours already used on 2026-08-10 | 10 data rows |
| `stock_batches.csv` | Opening stock batches per depot with expiry | 27 data rows |
| `stock_receipts.csv` | Government stock and donations received during the operation (each creates a batch) | 13 data rows |
| `requests.csv` | Camp requests: item, quantity, urgency and stock on hand reported by the camp | 180 data rows |
| `deliveries.csv` | Delivery records against planned trips | 88 data rows |
| `commands.txt` | Requests, receipts, verification, arrivals, road status changes, 16 cycles, deliveries and prints | 316 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable" and only occurs in columns whose notes say so.

### `depots.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| depot_id | string | D-n | — | — |
| depot_name | string | — | — | — |

### `zones.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| zone_id | string | Zn | — | — |
| zone_name | string | — | — | — |
| severity | int | — | 1-5 | 10 points per level |
| road_status | enum | — | OPEN, PARTIAL, BLOCKED | changes via ROAD_STATUS |
| serving_depot_id | string | — | depots.csv | camps of the zone are supplied only from it |

### `camps.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| camp_id | string | Cnn | — | — |
| zone_id | string | — | zones.csv | — |
| camp_name | string | — | — | — |
| capacity | int | persons | — | — |
| occupancy | int | persons | — | at the start |
| children | int | — | — | — |
| elderly | int | — | — | — |
| pregnant | int | — | — | — |
| opened_ts | timestamp | — | — | stands in for the last delivery before the first one |

### `distances.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| from_id | string | — | — | depot or camp |
| to_id | string | — | — | — |
| km | decimal | km | — | symmetric |

### `items.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| item_id | string | — | — | — |
| item_name | string | — | — | — |
| unit | string | — | — | — |
| unit_weight_kg | decimal | kg | — | — |
| daily_norm_per_person | decimal | units | — | need = ceil(occupancy x norm x 2) - stock on hand |
| shelf_life_days | int | days | — | — |
| priority_class | enum | — | LIFE_SAVING, FOOD, SHELTER | — |
| medicine | bool | — | — | donated medicine -> QUARANTINE |

### `vehicles.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| vehicle_id | string | V-nn | — | — |
| depot_id | string | — | depots.csv | — |
| vehicle_type | enum | — | TRUCK, BOAT, HELICOPTER | — |
| capacity_kg | int | kg | — | truck halved on PARTIAL roads |
| speed_kmph | int | km/h | — | — |
| driver_name | string | — | — | — |
| duty_hours_used | decimal | h | — | already used on 2026-08-10 |

### `stock_batches.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| batch_id | string | B-nnn | — | — |
| depot_id | string | — | depots.csv | — |
| item_id | string | — | items.csv | — |
| qty | int | units | — | — |
| expiry_ts | timestamp | — | — | — |
| source | enum | — | GOVT, DONATION | — |
| verified | bool | — | — | — |

### `stock_receipts.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| receipt_id | string | RC-nn | — | — |
| batch_id | string | — | — | batch created on acceptance |
| depot_id | string | — | — | — |
| item_id | string | — | items.csv | — |
| qty | int | units | — | — |
| expiry_ts | timestamp | — | — | — |
| source | enum | — | GOVT, DONATION | — |
| received_ts | timestamp | — | — | — |

### `requests.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| request_id | string | RQ-nnn | — | — |
| camp_id | string | — | camps.csv | — |
| item_id | string | — | — | may be unregistered |
| qty | int | units | — | — |
| urgency | enum | — | CRITICAL, HIGH, NORMAL | — |
| stock_on_hand | int | units | — | reported by the camp |
| request_ts | timestamp | — | — | — |

### `deliveries.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| delivery_id | string | DL-nnn | — | — |
| trip_id | string | <vehicle>-T<n> | — | n-th trip of that vehicle |
| camp_id | string | — | camps.csv | — |
| item_id | string | — | — | — |
| batch_id | string | — | — | — |
| delivered_qty | int | units | — | — |
| returned_qty | int | units | — | back to the batch |
| delivered_ts | timestamp | — | — | — |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. An empty argument (two pipes in a row) means "not supplied". Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `REQUEST` | `request_id` | Register a camp request (need, trimming) |
| `RECEIVE` | `receipt_id` | Receive stock (donation shelf-life and quarantine rules) |
| `VERIFY` | `batch_id|timestamp` | Release a quarantined donated medicine batch |
| `ARRIVAL` | `camp_id|timestamp|persons` | New arrivals (overflow / redirect rules) |
| `ROAD_STATUS` | `zone_id|timestamp|status` | Road status change |
| `CYCLE` | `timestamp` | Write-offs, allocation, dispatch planning for the next 6 hours |
| `DELIVERY` | `delivery_id` | Reconcile one delivered line |
| `PRINT_ALLOCATIONS` | `` | Allocation decisions per cycle with rule ids |
| `PRINT_MANIFESTS` | `` | Dispatch manifests |
| `PRINT_RECONCILIATION` | `` | Reconciliation, discrepancies, write-offs |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Two camps with identical score and occupancy - camp-id tie-break**
  - Cycle 1 (2026-08-10 03:00): RQ-005 (C03) and RQ-006 (C04) both score 75.50 with occupancy 320, need 100 ORS each, D-1 holds B-002 = 101: pass 1 cap floor(40% x 101) = 40 each, pass 2 splits the 21 left 10 / 10 and the 1-unit residue goes to the tie-break winner C03 (lower camp id) -> C03 51, C04 50 — `requests.csv RQ-005 (row 5); requests.csv RQ-006 (row 6); stock_batches.csv B-002 (row 2)`
- **EC-02 Fairness cap leaving stock that only one camp still needs**
  - Cycle 1: D-2 rice B-012 = 100 kg; RQ-007 (C08) needs 90, RQ-008 (C12) needs 10: the 40% cap holds C08 to 40 in pass 1 (C12 gets its 10), the 50 kg left is re-offered without the cap and only C08 still needs it -> C08 90 in total — `requests.csv RQ-007 (row 7); requests.csv RQ-008 (row 8); stock_batches.csv B-012 (row 12)`
- **EC-03 Stock expiring in exactly 48 hours with the camp reachable in exactly 12 hours**
  - Cycle 5 (2026-08-11 03:00): batch B-021 expires 2026-08-13 03:00:00 = exactly 48 hours later -> restricted to camps reachable within 12 hours; C13 is 165 km from D-3 on an OPEN road: 2 x 165 / 30 + 1 = 12.0 hours exactly -> allowed, so FEFO gives RQ-038 its 300 packets from that batch — `requests.csv RQ-038 (row 38); stock_batches.csv B-021 (row 21); distances.csv D-3-C13 (row 43)`
- **EC-04 Helicopter 5th sortie request for a CRITICAL water allocation**
  - V-05 (helicopter, D-2) flies 4 sorties on 2026-08-10 (V-05-T1, V-05-T2, V-05-T3, V-05-T4); in cycle 2 the CRITICAL water allocation for C06 (RQ-010) would be its 5th sortie that day -> refused (max 4); the boat V-06 is over its 12 duty hours -> the allocation waits and is escalated once 6 hours old — `requests.csv RQ-010 (row 10)`
- **EC-05 Driver at 11 hours with a round trip of 1 hour 30 minutes**
  - Cycle 1: V-01 has 11.0 duty hours on 2026-08-10; the top D-1 allocation (RQ-001, C01 at 7.5 km) is a 2 x 7.5 / 30 + 1 = 1 h 30 min round trip -> 12.5 > 12 -> V-01 refused; the trip goes to V-02 (V-02-T1) — `requests.csv RQ-001 (row 1); vehicles.csv V-01 (row 1)`
- **EC-06 Camp at exactly 120 percent occupancy**
  - C11: capacity 250, occupancy 280; ARRIVAL of 20 (line 46) -> 300 = exactly 120% -> not above -> no OVERFLOW, no automatic request. The later ARRIVAL of 18 (line 133) -> 318 > 120% -> OVERFLOW and automatic SHELTER request AUTO-01: excess 18 persons -> ceil(18 x 0.1 x 2) = 4 tarpaulins — `camps.csv C11 (row 11); commands.txt lines 46, 133`
- **EC-07 Delivery short by exactly 2 percent**
  - DL-041: trip V-09-T4 dispatched 200 ORS sachets to C14 (request RQ-050); 196 delivered, none returned -> short by exactly 2% -> not more than 2% -> no DISCREPANCY — `deliveries.csv DL-041 (row 41); requests.csv RQ-050 (row 50)`
- **EC-08 Proportional allocation where every request rounds down to zero**
  - Cycle 1: D-1 has only 2 medicine kits (B-003); RQ-002, RQ-003 and RQ-004 (scores 67.00, 65.50, 64.00, all band 60-69) need 6 each: the cap floor(40% x 2) = 0 gives nothing in pass 1; in pass 2 each proportional share floor(2 x 6 / 18) = 0 -> the residue 2 goes to the highest score (C01) — `requests.csv RQ-002 (row 2); requests.csv RQ-003 (row 3); requests.csv RQ-004 (row 4); stock_batches.csv B-003 (row 3)`
- **Extra traps (not in the brief, but realistic):**
  - RC-05: donated food packets expiring 6 days 23 h 59 min after receipt -> less than 7 days -> REJECTED; RC-06: donation with exactly 7 days shelf life -> accepted. RC-04: donated medicine kits held in QUARANTINE until the VERIFY command; RQ-057 (C08 medicine kits) cannot draw on them before that — `stock_receipts.csv RC-05 (row 5); stock_receipts.csv RC-06 (row 6); stock_receipts.csv RC-04 (row 4); requests.csv RQ-057 (row 57)`
  - RQ-012: GENERATOR is not a registered item -> REJECTED; RQ-014: asks for 59 but the need is 50 -> trimmed to the need, tagged TRIMMED — `requests.csv RQ-012 (row 12); requests.csv RQ-014 (row 14)`
  - Line 109: ARRIVAL at C09, which holds 310 against capacity 200 (155% > 150%) -> the 12 new arrivals are redirected to C08, the nearest camp of zone Z4 with spare capacity — `commands.txt line 109; camps.csv C09 (row 9)`
  - DL-004, DL-037 and DL-039: deliveries by V-07 short by more than 2% -> three DISCREPANCY records -> V-07 is grounded and gets no trips after 2026-08-11 11:16:40 — `deliveries.csv DL-004 (row 4); deliveries.csv DL-037 (row 37); deliveries.csv DL-039 (row 39)`
  - B-015: D-2 biscuits expire 2026-08-12 10:00 unused -> written off at the start of cycle 11 (2026-08-12 15:00:00): 400 packs — `stock_batches.csv B-015 (row 15)`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `allocations.csv`

One row per allocated batch line.

Columns, in order: `cycle_ts`, `request_id`, `camp_id`, `item_id`, `score`, `batch_id`, `qty`, `rule_ids`

### `manifests.csv`

One row per trip line.

Columns, in order: `trip_id`, `vehicle_id`, `depot_id`, `depart_ts`, `return_ts`, `trip_hours`, `route`, `camp_id`, `item_id`, `batch_id`, `qty`, `eta_ts`, `escalated`

### `dispatch_refusals.csv`

One row per vehicle refused for a line.

Columns, in order: `cycle_ts`, `allocation_line`, `vehicle_id`, `reason`

### `reconciliation.csv`

One row per delivery and per write-off.

Columns, in order: `record`, `trip_id`, `camp_id`, `item_id`, `batch_id`, `dispatched`, `delivered`, `returned`, `short`, `status`

### `request_status.csv`

One row per request.

Columns, in order: `request_id`, `status`, `need`, `trimmed_qty`, `allocated`, `open`

Binding choices where the brief is silent: (1) camps are supplied only from their zone's serving depot; allocation runs per depot and item, items in class order then items.csv order. (2) Score = 10 x severity + urgency + 15 x vulnerable / occupancy (cap 15, exact) + floor(hours since the last delivery of the item, or since opened_ts, / 6) capped at 10; bands are floor(score / 10). (3) Cap = floor(40% of the depot's usable units), not applied when one camp requests; pass 1 with the cap, pass 2 without; within a band, if stock is short, floor(remaining x need / band need) and the residue to the highest-ranked request, then the next. (4) A request stays open for its unallocated remainder; a new request for the same camp and item supersedes it. (5) 'Reachable within 12 hours' = round trip depot-camp-depot + 1 h by truck (OPEN / PARTIAL) or boat (BLOCKED); the 48 h test is expiry_ts - cycle_ts <= 48 h. (6) Trucks serve only OPEN / PARTIAL zones, boats and the helicopter (helicopter speed 120 km/h) only BLOCKED zones. Within a cycle a vehicle may run several trips back to back, each starting before the next cycle; the line order is escalated, class, score, camp, item; the vehicle is the one available first (then vehicle id) that passes duty and sortie limits; lines for camps within 10 km of the first camp are consolidated in that order, split to whole units by remaining capacity. Arrival = departure + 1 h + travel. (7) Discrepancy if dispatched - delivered - returned > 2% of dispatched. (8) Overflow request = ceil(excess persons above 120% x tarpaulin norm x 2), urgency HIGH.

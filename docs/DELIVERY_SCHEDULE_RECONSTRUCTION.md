# Official delivery schedule reconstruction

## Result

The complete 88-delivery trace is in [DELIVERY_DISPATCH_TRACE.csv](DELIVERY_DISPATCH_TRACE.csv). It contains the requested delivery key, quantity and time, allocation lineage, manifest quantity, vehicle, departure, ETA, return, command line, reconciliation status, whether the exact manifest existed when the command ran, and any rejection reason.

After the corrections below, all 88 delivery commands have an exact manifest at command time. There are 16 cycles, 88 manifest lines, and no delivery command errors. All delivery timestamps are at or after their matched manifest ETA. The reconciliation report contains 88 delivery rows plus two write-off rows: 82 delivery rows are `OK` and six are `DISCREPANCY`. A discrepancy is an accounted delivery with a shortfall above the documented threshold; it is not a rejected delivery.

## First divergence and sequence analysis

The first rejected delivery in the earlier run was DL-046 at command line 136. In that run, its claimed V-05-T7 manifest was missing because that dispatch was planned in the later 21:00 cycle, after the row's 16:47 delivery time. In the corrected run, RQ-059 is allocated at the 15:00 cycle; V-05-T7 is planned before command line 136, departs at 15:00, and reaches C07 at 16:22:30. The delivery record at 16:47:42 reconciles. The trace shows no delivery command preceding its exact manifest in the corrected run.

The other earlier trip and quantity mismatches were downstream of allocation availability and vehicle schedule state. Reconstructing the sequences shows the planner's existing sort and trip-counter logic then generate the delivery schedule expected by the sample when the proper allocations are retained:

- Allocation lines are ordered by item class and item-file order; within the request competition the priority bands and score/tie-break rules apply. Dispatch sorts pending lines by escalation, class, descending score, camp, item, then batch as its final deterministic tie-break. That last tie only applies after all README binding fields tie and did not produce a sample mismatch.
- Each line selects the eligible vehicle with the earliest dispatch time, then vehicle ID. Vehicle availability is carried between cycles and across midnight; daily duty/sortie counters reset on the next operational day without declaring an active vehicle available.
- Consolidation scans the same ordered pending lines, uses the first camp as the 10 km reference, and splits quantities against remaining vehicle capacity. The trip counter increments only after a nonempty feasible trip is finalized, once per vehicle trip; it is vehicle-specific and persists across cycles.
- Comparing all delivery commands in input order against manifests created so far found the earlier first mismatch at DL-046. In the corrected run, the exact manifest exists by that command. The generated departure and ETA precede all matched delivery timestamps.

## Proven allocation eligibility defect

`AllocationEngine.allocate` invokes its reachability callback for every candidate request and batch. `DispatchEngine.can_deliver_before_expiry` returned false when the currently compatible vehicle could not complete a trip with the duty hours already used that day. That excluded a request from the priority competition even when its batch had days or months before expiry and a suitable vehicle could serve it after the next daily duty reset. Lower-priority camps then consumed the stock.

The official binding applies the 12-hour reachability restriction to stock expiring within 48 hours. For longer-lived stock, the callback now estimates the next daily cycle for compatible vehicles that can complete the round trip within a fresh 12-hour duty allowance. It admits the batch only when the estimated arrival is still before expiry. Grounded vehicles, incompatible vehicle/road combinations, insufficient capacity, trips longer than the daily duty maximum, near-expiry reachability limits, and actual dispatch-time ETA/expiry checks remain enforced.

The official records demonstrate the consequences and corrected outcomes:

| Earlier mismatch | Earlier planning issue | Corrected allocation and manifest | Final result |
|---|---|---|---|
| DL-046 | In the earlier run RQ-059 was allocated at 21:00, after the delivery command. | RQ-059, B-014, 10 units; V-05-T7 departs 15:00, ETA 16:22:30. | `OK` |
| DL-055 | B-033 went to C09 while higher-priority RQ-039/C07 was filtered for current boat duty; V-08's trip order shifted. | V-08-T4, C08 WATER/B-028, 276 units. | `OK` |
| DL-058 | Same V-08 trip shift; the correct partial quantity was 46. | V-08-T4, C09 RICE/B-030, 46 units. | `OK` |
| DL-059 | The changed cycle allocation and dispatch schedule now produce the actual planned quantity. | V-09-T5, C14 WATER/B-023, 880 dispatched; 838 delivered. | `DISCREPANCY` (42 short) |
| DL-060 | Earlier allocation had only 105 available on the line; the corrected cycle allocation matches the official dispatch. | V-06-T3, C06 RICE/B-030, 147 dispatched/delivered. | `OK` |
| DL-061 | D3 vehicle availability and line order were shifted by the earlier schedule state. | V-10-T3, C13 TARP/B-035, 22 units. | `OK` |
| DL-065 | Earlier allocation/dispatch line was 13; the corrected plan allocates and dispatches 28. | V-06-T4, C07 MOSQNET/B-018, 28 units. | `OK` |
| DL-067 | RQ-039 was removed from allocation competition while V-06 was duty-limited; its B-033 line was absent. | RQ-039 receives 300 B-033 units at 15:00 Aug 11; V-06-T4 carries them to C07. | `OK` |
| DL-072 | V-08 trip numbering shifted after the earlier B-033 assignment. | V-08-T5, C12 ORS/B-039, 27 units. | `OK` |
| DL-077, DL-078 | Later V-08 trip numbering shifted. | Both lines are on V-08-T6: C09 DAL/B-016 (1) and MEDKIT/B-036 (7). | `OK` |
| DL-080, DL-081, DL-082 | D3 allocation and vehicle schedules placed C15 cargo on a different trip. | V-10-T4 carries C15 RICE/B-024 (60), FOODPKT/B-022 (262), and FOODPKT/B-040 (4). | `OK` |
| DL-083 | D3 trip numbering/assignment was shifted. | V-09-T7, C13 FOODPKT/B-022, 238 units. | `OK` |
| DL-084 | RQ-097/C13 was excluded while both D3 trucks were duty-limited; B-037 went to other camps. | RQ-097 receives 264 B-037 units at 09:00 Aug 12; V-09-T7 carries them to C13. | `OK` |
| DL-087 | Correct quantity came from RQ-130 but the trip assignment changed with the schedule. | V-10-T5, C14 ORS/B-020, 208 dispatched; 198 delivered. | `DISCREPANCY` (10 short) |
| DL-088 | V-08 trip numbering shifted. | V-08-T7, C12 MEDKIT/B-036, 1 unit. | `OK` |

DL-059 and DL-087 are not over-delivery cases in the corrected plan. Their quantities are within dispatched amounts and remain auditable as discrepancies. Reconciliation validation was not changed.

## Changes and validation

- `src/engines/dispatch_engine.py`: preserves each vehicle's scheduled return time at a day reset; allows expiry-safe long-lived stock to remain eligible when current daily duty or sortie usage is the only temporary barrier.
- `tests/test_dispatch_availability_regression.py`: covers cross-midnight vehicle availability, long-lived stock waiting for a duty reset, the near-expiry boundary, and the official sample outcomes.
- `docs/DELIVERY_DISPATCH_TRACE.csv`: full 88-row delivery audit trace.
- `docs/DELIVERY_SCHEDULE_RECONSTRUCTION.md`: this findings report.

Validation: 154 tests passed; the official sample processed all 88 delivery commands over 16 cycles with zero command errors; all five expected output CSVs were written with their official headers; `git diff --check` passed. The six discrepancy records are DL-004, DL-037, DL-039, DL-059, DL-063 and DL-087. No delivery remains rejected or unaccounted for.

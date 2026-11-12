# Official delivery timeline root-cause investigation

Read-only investigation of the 18 delivery commands rejected by the current official sample run. Command positions below are physical lines in `data/input/commands.txt` (comments included). “Last cycle” is the preceding CYCLE command. A manifest listed as a final candidate was compared by camp, item and batch; it is an exact match only if its trip ID also matches.

## Findings

The source of the unresolved records is **multiple connected components (F)**:

1. `AllocationEngine` creates planned quantities that can be smaller than the quantity recorded in a delivery row. This is visible directly in allocation and manifest quantities; reconciliation is correctly rejecting over-delivery.
2. `DispatchEngine` assigns vehicle-specific trip numbers from its runtime dispatch order. The sample’s delivery rows frequently name a different vehicle/trip than the planned manifest, although camp/item/batch allocations exist. Counters are per vehicle, persist across cycles, and are not reset by daily duty resets. This numbering implementation is stable but the actual vehicle assignment order differs from the sample’s implied trips.
3. The command stream/data timing is inconsistent for at least DL-046 and DL-080–082. DL-046 is commanded before the cycle that plans its claimed trip; DL-080–082 have delivery timestamps before the departure of the matching final candidate trip.
4. `DeliveryProcessor` uses the documented composite identity `(trip_id, camp_id, item_id, batch_id)` and strict quantity validation. Those checks are exposing upstream assignment/timing/quantity differences; weakening them would conceal invalid records.

`CycleEngine.run` is called only when a CYCLE command is reached, in command-file order. It writes off, allocates, and calls dispatch for that cycle. The trip counter is incremented only in `DispatchEngine._create_trip`; `trip_counts` is initialized once in the constructor and is not reset in `_reset_day` or `begin_cycle`. IDs are therefore vehicle-specific and monotonic for the life of the engine. A change in earlier dispatch decisions can change which vehicle receives later work and thus which vehicle-specific trip number a delivery row needs.

The README explicitly says expected outputs are not provided and delivery records are “against planned trips.” It defines order and vehicle availability policy, and says dispatch happens for a six-hour window. It does not authorize synthesizing manifests from delivery rows. The design rules require reconciliation against dispatched quantities and auditable records. The model schema note likewise says dispatched quantity comes from the manifest.

## Per-record chronology and exact-key candidates

The following are the current run’s rejected rows. Candidate quantities and departure times are from the final `data/output/manifests.csv`; a candidate in that file may have been created after the delivery command, so it is not automatically evidence that it existed at processing time.

| ID | Command line; last cycle | Delivery time; claimed trip/key | Final same camp/item/batch candidate(s) | Finding at command time / cause |
|---|---|---|---|---|
| DL-046 | 136; 15:00 Aug 11 | 16:47; V-05-T7, C07/MEDKIT/B-014, 10 | V-05-T7, 10, departs 21:00 Aug 11 | **Not yet planned.** The command precedes the 21:00 cycle (line 149) that creates the final candidate. The delivery timestamp also precedes planned departure. Timing/command stream conflict; do not pre-create the manifest. |
| DL-055 | 177; 03:00 Aug 12 | 04:48; V-08-T4, C08/WATER/B-028, 276 | V-08-T5, 276, departs 03:00 Aug 12 | A same-quantity exact camp/item/batch line was planned by the preceding cycle, but under T5, not T4. Dispatch assignment/trip ID divergence. |
| DL-058 | 181; 03:00 Aug 12 | 05:20; V-08-T4, C09/RICE/B-030, 46 | V-08-T5, 54, departs 03:00 Aug 12 | Trip ID differs and the planned quantity is 54 versus delivered 46. This is a partial delivery if matched to T5, but matching the wrong trip is impermissible. |
| DL-059 | 182; 03:00 Aug 12 | 05:51; V-09-T5, C14/WATER/B-023, 838 | V-09-T5, 528, departs 03:00 Aug 12 | Exact key exists; delivered quantity exceeds dispatched quantity by 310 and was correctly rejected. Quantity trace below. |
| DL-060 | 184; 03:00 Aug 12 | 06:03; V-06-T3, C06/RICE/B-030, 147 | V-06-T3, 105, departs 03:00 Aug 12 | Exact key exists; delivered exceeds dispatched by 42. Quantity trace below. |
| DL-061 | 195; 09:00 Aug 12 | 09:52; V-10-T3, C13/TARP/B-035, 22 | V-10-T5, 22, departs 03:00 Aug 13 | **No corresponding trip planned yet at command time.** Final candidate is from the following day’s 03:00 cycle. Trip assignment differs; delivery timestamp also predates the final candidate. |
| DL-065 | 202; 09:00 Aug 12 | 11:25; V-06-T4, C07/MOSQNET/B-018, 28 | V-06-T4, 13, departs 08:00 Aug 12 | Exact key exists; delivered exceeds dispatched by 15. Quantity trace below. |
| DL-067 | 204; 09:00 Aug 12 | 11:32; V-06-T4, C07/FOODPKT/B-033, 300 | None | V-06-T4 exists, but it carries C07/MOSQNET/B-018, 13, not this item/batch. Allocation output has no C07 FOODPKT/B-033 line. No matching allocation or manifest exists; this is not a history overwrite. |
| DL-072 | 217; 15:00 Aug 12 | 17:19; V-08-T5, C12/ORS/B-039, 27 | V-08-T6, 27, departs 15:00 Aug 12 | Matching quantity planned in that cycle, but assigned T6 instead of T5. Dispatch assignment/trip ID divergence. |
| DL-077 | 262; 03:00 Aug 13 | 05:01; V-08-T6, C09/DAL/B-016, 1 | V-08-T7, 1, departs 03:00 Aug 13 | Matching line planned in the preceding cycle, but under T7. Dispatch assignment/trip ID divergence. |
| DL-078 | 263; 03:00 Aug 13 | 05:06; V-08-T6, C09/MEDKIT/B-036, 7 | V-08-T7, 7, departs 03:00 Aug 13 | Matching line planned in the preceding cycle, but under T7. Dispatch assignment/trip ID divergence. |
| DL-080 | 269; 03:00 Aug 13 | 06:20; V-10-T4, C15/RICE/B-024, 60 | V-09-T2, 116, departs Aug 10 21:00; V-09-T8, 60, departs Aug 13 07:12 | No exact key. T8 was planned in the Aug 13 03:00 cycle, but its departure is after this delivery timestamp. T2 is a different trip and quantity. Timing plus vehicle/trip assignment divergence. |
| DL-081 | 270; 03:00 Aug 13 | 06:26; V-10-T4, C15/FOODPKT/B-022, 262 | V-09-T8, 262, departs Aug 13 07:12 | Candidate is planned in the preceding cycle but leaves after the delivery timestamp; claimed trip is different. Timing and assignment divergence. |
| DL-082 | 271; 03:00 Aug 13 | 06:26; V-10-T4, C15/FOODPKT/B-040, 4 | V-09-T8, 4, departs Aug 13 07:12 | Same trip/timing issue as DL-081. |
| DL-083 | 279; 09:00 Aug 13 | 09:41; V-09-T7, C13/FOODPKT/B-022, 238 | V-10-T5, 238, departs Aug 13 03:00 | Matching quantity and batch planned before command, but under V-10-T5. Dispatch assignment/trip ID divergence. |
| DL-084 | 280; 09:00 Aug 13 | 09:54; V-09-T7, C13/WATER/B-037, 264 | None | No C13 WATER/B-037 allocation or manifest exists in the output. No trip line to reconcile; allocation/stock planning or sample-row inconsistency remains to be identified. |
| DL-087 | 287; 09:00 Aug 13 | 11:06; V-10-T5, C14/ORS/B-020, 198 | V-09-T4, 200, departs Aug 11 09:00; V-09-T7, 208, departs Aug 13 03:00 | No exact key. RQ-050 allocated 200 and V-09-T4 planned 200; 198 would be a valid 1% shortfall against that line, but the delivery names V-10-T5. A later 208-unit line is RQ-130 and is not interchangeable. Dispatch assignment/key divergence, not a quantity overrun. |
| DL-088 | 288; 09:00 Aug 13 | 11:08; V-08-T7, C12/MEDKIT/B-036, 1 | V-08-T8, 1, departs Aug 13 09:00 | Matching line planned before command, but under T8. Dispatch assignment/trip ID divergence. |

## Quantity lineage

The allocation report persists request ID, score, batch, quantity, cycle and rule IDs. Manifest rows preserve the batch and planned quantity, but do not include request ID; the trace below joins camp/item/batch and the recorded allocation output.

| Delivery | Original request and Request Manager outcome | Priority/allocation and batch | Dispatch manifest | Delivery row | Exact divergence |
|---|---|---|---|---|---|
| DL-059 | RQ-063, C14 WATER, submitted 1608, CRITICAL, stock-on-hand 226. Request status shows need/trimmed 1274; later superseded. | Allocation score 69.20, B-023, 528 at Aug 12 03:00; a later allocation of 396 from B-037 is separate. | V-09-T5, B-023, 528. | 838 delivered, same V-09-T5/B-023. | Delivery reports 310 more than the exact trip/batch allocation. Neither the separate B-037 line nor an open request remainder can augment B-023’s manifest quantity. The allocation and manifest agree; source delivery quantity/key is inconsistent. |
| DL-060 | RQ-067, C06 RICE, submitted 175, NORMAL, stock-on-hand 77. Need/trimmed 147; later superseded. | Allocation score 68.75, B-030, 105 at Aug 12 03:00. | V-06-T3, B-030, 105. | 147 delivered. | Delivery equals total need but exceeds the allocated/dispatched amount by 42. The short allocation is preserved as open demand; it does not authorize delivery of the remainder. |
| DL-065 | RQ-060, C07 MOSQNET, submitted 87, NORMAL, stock-on-hand 49. Need/trimmed 81; later superseded. | Allocation score 68.75, B-018, 13 at Aug 12 03:00. | V-06-T4, B-018, 13. | 28 delivered. | Delivery exceeds the allocated/dispatched amount by 15. Remaining need is not dispatched stock. |
| DL-087 | RQ-050, C14 ORS, submitted/need/trimmed 200, HIGH. | Allocation score 59.20, B-020, 200 at Aug 11 09:00. A distinct RQ-130 later receives 208 from B-020. | RQ-050 appears as V-09-T4/200; RQ-130 as V-09-T7/208. | 198 delivered under V-10-T5. | Quantity 198 is within RQ-050’s 200 planned units; the failure is the trip key. Do not merge the second request’s allocation into this delivery. |

## Component responsibility and minimal correction

- **Allocation Engine:** It records 528, 105 and 13 for the three exact-key over-deliveries, which match their manifests. There is no evidence in these rows of an allocation/manifest mismatch. It also has no output line for DL-067 or DL-084; investigate their same-cycle request eligibility, stock availability and batch assignment separately before changing allocation logic.
- **Priority Engine:** The shared live delivery-history dictionary fix is present and retained. It does not explain these exact trip key or over-dispatch discrepancies by itself.
- **Dispatch Engine:** Per-vehicle counters are monotonic and vehicle-specific as required by `<vehicle>-T<n>`. The output manifests show vehicle assignment differs from many delivery rows. The README binding order is the authoritative dispatch policy; compare allocation ordering, vehicle readiness, consolidation and trip creation against it. Do not force trip IDs to match deliveries.
- **Cycle Engine:** Processing is ordered correctly: each CYCLE plans only when its command is reached. It does not pre-plan later cycles. DL-046’s claimed trip is generated only by a later cycle, so the record’s command/timestamp chronology conflicts with the planner. For DL-080–082, a manifest was planned in the 03:00 cycle but departure is 07:12, later than the recorded 06:20–06:26 delivery times.
- **Delivery Processor / Reconciliation Engine:** Exact four-field matching and delivered-plus-returned <= dispatched checks are appropriate. Reconciliation checks that delivery timestamp is not before dispatch time once an exact manifest is found. No weakening or heuristic matching is justified.

### Smallest reliable next correction

Do not alter reconciliation or delivery quantities. First add a read-only trace/test fixture that compares, cycle by cycle, the ordered allocation lines and vehicle-ready candidates with the README’s binding dispatch rules and reports the first divergence in trip creation. Correct only that demonstrated dispatch-order/readiness or consolidation defect, if one is established. Separately flag the sample chronology defects (DL-046, DL-080–082) and no-allocation rows (DL-067, DL-084) as input/planning discrepancies; do not fabricate their manifests. Re-run the official sample and require every delivery to either reconcile to its actual manifest or remain explicitly rejected with its reason.

This report does not assert that all 88 delivery records validate. In the investigated run, 70 are processed and 18 delivery commands are rejected.

## Dispatch availability correction and revalidation

The first proven dispatch-state divergence was vehicle availability across a calendar-day reset. In the pre-correction sample output, V-10-T1 departed at 2026-08-10 21:00 and returned at 2026-08-11 09:00, but V-10-T2 was planned to depart at 2026-08-11 03:00. `DispatchEngine._reset_day` had reset every `available_at` value to the new cycle timestamp when the date changed, even when an earlier trip was still active.

The minimal correction initializes `available_at` on the first operational day only. A later day still resets that day's duty and sortie counters, but retains each vehicle's actual scheduled return time. A regression test starts a nine-hour trip at 21:00, advances to a 03:00 cycle, and verifies that the still-busy vehicle is not selected ahead of a vehicle available at 03:00.

After the correction, V-10-T2 departs at 09:00, exactly when V-10-T1 returns. A scan of generated manifests found no same-vehicle trip overlaps. The official sample still runs all 16 cycles and writes all five reports. It processes 70 deliveries and rejects the same 18 IDs: DL-046, DL-055, DL-058, DL-059, DL-060, DL-061, DL-065, DL-067, DL-072, DL-077, DL-078, DL-080, DL-081, DL-082, DL-083, DL-084, DL-087 and DL-088. Thus this is a genuine dispatch defect correction, but it does not resolve the remaining sample-record discrepancies and does not establish full sample validation.

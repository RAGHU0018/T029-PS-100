"""Vehicle assignment, trip planning, manifests and refusals (BR-31–44)."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import inf

from src.models.item import ItemClass
from src.models.vehicle import VehicleType
from src.models.zone import RoadStatus


@dataclass
class PendingLine:
    allocation: object
    remaining: int


class DispatchEngine:
    WINDOW = timedelta(hours=6)
    ESCALATION_HOURS = {ItemClass.LIFE_SAVING: 6, ItemClass.FOOD: 24, ItemClass.SHELTER: 48}

    def __init__(self, vehicles, camps, zones, items, distances, inventory_manager=None):
        self.vehicles, self.camps, self.zones, self.items = vehicles, camps, zones, items
        self.distances = distances
        self.inventory = inventory_manager
        self.manifests = []
        self.refusals = []
        self.pending = []
        self.available_at = {}
        self.trip_counts = {vehicle_id: 0 for vehicle_id in vehicles}
        self.day = None
        self.outstanding = {}

    def _distance(self, a, b):
        if a == b:
            return 0.0
        value = self.distances.get((a, b))
        if value is None:
            value = self.distances.get((b, a))
        return float(value) if value is not None else inf

    def _reset_day(self, at):
        if self.day == at.date():
            return
        if self.day is not None:
            for vehicle in self.vehicles.values():
                vehicle.duty_hours_today = 0.0
                vehicle.sorties_today = 0
        else:
            self.available_at = {vid: at for vid in self.vehicles}
        self.day = at.date()

    def begin_cycle(self, at):
        self._reset_day(at)

    def _zone(self, camp_id):
        return self.zones[self.camps[camp_id].zone_id]

    def _compatible(self, vehicle, camp_id, item_id):
        zone = self._zone(camp_id)
        item = self.items[item_id]
        if vehicle.is_grounded:
            return False, "GROUNDED"
        if vehicle.vehicle_type == VehicleType.TRUCK:
            return (True, "") if zone.road_status in (RoadStatus.OPEN, RoadStatus.PARTIAL) else (False, "ROAD_STATUS")
        if zone.road_status != RoadStatus.BLOCKED:
            return False, "ROAD_STATUS"
        if vehicle.vehicle_type == VehicleType.HELICOPTER and item.item_class != ItemClass.LIFE_SAVING:
            return False, "ITEM_CLASS"
        return True, ""

    def speed_for(self, zone, item):
        if zone.road_status in (RoadStatus.OPEN, RoadStatus.PARTIAL):
            return 30.0
        speeds = [20.0]
        if item.item_class == ItemClass.LIFE_SAVING:
            speeds.append(120.0)
        return max(speeds)

    def arrival_eta(self, depot_id, camp_id, item_id, depart_ts):
        """Earliest allowed ETA, including the one-hour load/unload allowance."""
        zone = self._zone(camp_id)
        distance = self._distance(depot_id, camp_id)
        if distance == inf:
            return None
        speed = self.speed_for(zone, self.items[item_id])
        return depart_ts + timedelta(hours=1 + distance / speed)

    def _can_deliver_after_daily_reset(self, batch, managed, cycle_ts, vehicle, distance):
        """Keep long-lived stock eligible when a vehicle is only duty-limited today."""
        if batch.expiry_date - cycle_ts <= timedelta(hours=48) or vehicle.is_grounded:
            return False
        round_trip = 2 * distance / vehicle.speed_kmph + 1
        if round_trip > vehicle.MAX_DUTY_HOURS:
            return False
        camp_id = managed.request.camp_id
        item_id = managed.request.item_id
        weight = self.items[item_id].unit_weight_kg
        zone = self._zone(camp_id)
        capacity = vehicle.capacity_kg / (2 if vehicle.vehicle_type == VehicleType.TRUCK
                                          and zone.road_status == RoadStatus.PARTIAL else 1)
        if weight > capacity:
            return False
        next_cycle = cycle_ts + self.WINDOW
        while next_cycle.date() == cycle_ts.date():
            next_cycle += self.WINDOW
        depart = max(next_cycle, self.available_at.get(vehicle.vehicle_id, next_cycle))
        eta = depart + timedelta(hours=1 + distance / vehicle.speed_kmph)
        return batch.expiry_date > eta

    def can_deliver_before_expiry(self, batch, managed, cycle_ts):
        """Use current feasible vehicle ETA for allocation expiry eligibility."""
        camp_id = managed.request.camp_id
        item_id = managed.request.item_id
        depot_id = self._zone(camp_id).serving_depot_id
        self._reset_day(cycle_ts)
        for key, rows in list(self.outstanding.items()):
            for row, allocation_ts, item_id in rows:
                if cycle_ts - allocation_ts >= timedelta(hours=self.ESCALATION_HOURS[self.items[item_id].item_class]):
                    row["escalated"] = True
        distance = self._distance(depot_id, camp_id)
        if distance == inf:
            return False
        for vehicle in self.vehicles.values():
            if vehicle.depot_id != depot_id:
                continue
            compatible, _ = self._compatible(vehicle, camp_id, item_id)
            if not compatible:
                continue
            if vehicle.vehicle_type == VehicleType.HELICOPTER and not vehicle.has_sorties_available:
                if self._can_deliver_after_daily_reset(batch, managed, cycle_ts, vehicle, distance):
                    return True
                continue
            depart = max(cycle_ts, self.available_at.get(vehicle.vehicle_id, cycle_ts))
            round_trip = 2 * distance / vehicle.speed_kmph + 1
            if not vehicle.can_complete_trip(round_trip):
                if self._can_deliver_after_daily_reset(batch, managed, cycle_ts, vehicle, distance):
                    return True
                continue
            weight = self.items[item_id].unit_weight_kg
            cap = vehicle.capacity_kg / (2 if vehicle.vehicle_type == VehicleType.TRUCK and self._zone(camp_id).road_status == RoadStatus.PARTIAL else 1)
            if weight > cap:
                continue
            eta = depart + timedelta(hours=1 + distance / vehicle.speed_kmph)
            if batch.expiry_date <= eta:
                continue
            remaining = batch.expiry_date - cycle_ts
            if remaining <= timedelta(hours=48):
                # The sample README defines this restriction using trucks on
                # OPEN/PARTIAL roads and boats in BLOCKED zones.
                if vehicle.vehicle_type not in (VehicleType.TRUCK, VehicleType.BOAT) or round_trip > 12:
                    continue
            return True
        return False

    def plan(self, cycle_ts, allocations=()):
        if cycle_ts.tzinfo is None:
            raise ValueError("Cycle timestamp must be timezone-aware.")
        self._reset_day(cycle_ts)
        known = {id(line.allocation) for line in self.pending}
        for allocation in allocations:
            if id(allocation) not in known:
                self.pending.append(PendingLine(allocation, allocation.qty))
        class_order = {ItemClass.LIFE_SAVING: 0, ItemClass.FOOD: 1, ItemClass.SHELTER: 2}
        end = cycle_ts + self.WINDOW
        self.pending.sort(key=lambda line: (
            not self._escalated(line.allocation, cycle_ts),
            class_order[self.items[line.allocation.item_id].item_class],
            -line.allocation.score, line.allocation.camp_id,
            line.allocation.item_id, line.allocation.batch_id))
        start = len(self.manifests)
        for line in list(self.pending):
            if line.remaining <= 0:
                if line in self.pending:
                    self.pending.remove(line)
                continue
            allocation = line.allocation
            batch = self.inventory.batches.get(allocation.batch_id) if self.inventory is not None else None
            if batch is not None and batch.expiry_date <= cycle_ts:
                self.refusals.append({"cycle_ts": cycle_ts, "allocation_line": self._line_id(allocation),
                    "vehicle_id": "", "reason": "BATCH_EXPIRED"})
                line.remaining = 0
                self.pending.remove(line)
                continue
            camp_id, item_id = allocation.camp_id, allocation.item_id
            depot_id = self._zone(camp_id).serving_depot_id
            if not depot_id:
                self._refuse(cycle_ts, allocation, [], "NO_SERVING_DEPOT")
                continue
            candidates = [v for v in self.vehicles.values() if v.depot_id == depot_id]
            feasible = []
            failures = []
            for vehicle in candidates:
                okay, reason = self._compatible(vehicle, camp_id, item_id)
                if not okay:
                    failures.append((vehicle, reason))
                    continue
                cap = vehicle.capacity_kg / (2 if vehicle.vehicle_type == VehicleType.TRUCK and self._zone(camp_id).road_status == RoadStatus.PARTIAL else 1)
                if self.items[item_id].unit_weight_kg > cap:
                    failures.append((vehicle, "CAPACITY"))
                    continue
                if vehicle.vehicle_type == VehicleType.HELICOPTER and not vehicle.has_sorties_available:
                    failures.append((vehicle, "SORTIE_LIMIT"))
                    continue
                ready_at = self.available_at.get(vehicle.vehicle_id, cycle_ts)
                depart = max(cycle_ts, ready_at)
                if depart >= end:
                    failures.append((vehicle, "WINDOW"))
                    continue
                dist = self._distance(depot_id, camp_id)
                if dist == inf:
                    failures.append((vehicle, "NO_ROUTE"))
                    continue
                hours = 2 * dist / vehicle.speed_kmph + 1
                if not vehicle.can_complete_trip(hours):
                    failures.append((vehicle, "DUTY_LIMIT"))
                    continue
                feasible.append((depart, vehicle.vehicle_id, vehicle, cap))
            if not feasible:
                self._refuse(cycle_ts, allocation, failures, "NO_AVAILABLE_VEHICLE")
                continue
            if failures:
                self._refuse(cycle_ts, allocation, failures, "VEHICLE_UNAVAILABLE")
            _, _, vehicle, cap = min(feasible, key=lambda x: (x[0], x[1]))
            trip_lines = self._consolidate(line, vehicle, cycle_ts, end, cap)
            self._create_trip(cycle_ts, vehicle, depot_id, trip_lines)
            for used in trip_lines:
                if used.remaining <= 0 and used in self.pending:
                    self.pending.remove(used)
        return self.manifests[start:]

    def _escalated(self, allocation, at):
        item_class = self.items[allocation.item_id].item_class
        limit = self.ESCALATION_HOURS[item_class]
        return at - allocation.cycle_ts >= timedelta(hours=limit)

    def _refuse(self, cycle_ts, allocation, failures, default):
        if not failures:
            failures = [(None, default)]
        for vehicle, reason in failures:
            self.refusals.append({"cycle_ts": cycle_ts, "allocation_line": self._line_id(allocation),
                                  "vehicle_id": vehicle.vehicle_id if vehicle else "", "reason": reason or default})

    @staticmethod
    def _line_id(allocation):
        return f"{allocation.request_id}:{allocation.item_id}:{allocation.batch_id}"

    def _consolidate(self, seed, vehicle, cycle_ts, window_end, capacity):
        selected = [seed]
        seed_item = self.items[seed.allocation.item_id]
        seed_qty = seed.remaining if seed_item.unit_weight_kg == 0 else min(seed.remaining, int(capacity // seed_item.unit_weight_kg))
        seed._trip_qty = seed_qty
        weight = seed_qty * seed_item.unit_weight_kg
        first = seed.allocation.camp_id
        for candidate in self.pending:
            if candidate is seed or candidate.remaining <= 0:
                continue
            a = candidate.allocation
            if self._zone(a.camp_id).serving_depot_id != vehicle.depot_id:
                continue
            if self._distance(first, a.camp_id) > 10:
                continue
            okay, _ = self._compatible(vehicle, a.camp_id, a.item_id)
            if not okay:
                continue
            item_weight = self.items[a.item_id].unit_weight_kg
            candidate_partial = vehicle.vehicle_type == VehicleType.TRUCK and (
                self._zone(a.camp_id).road_status == RoadStatus.PARTIAL or
                any(self._zone(x.allocation.camp_id).road_status == RoadStatus.PARTIAL for x in selected))
            effective_capacity = min(capacity, vehicle.capacity_kg / (2 if candidate_partial else 1))
            if weight > effective_capacity:
                continue
            possible = min(candidate.remaining, int((effective_capacity - weight) // item_weight)) if item_weight else candidate.remaining
            if possible > 0:
                candidate._trip_qty = possible
                tentative = selected + [candidate]
                camps = list(dict.fromkeys(x.allocation.camp_id for x in tentative))
                nodes = [vehicle.depot_id] + camps + [vehicle.depot_id]
                duration = sum(self._distance(x, y) for x, y in zip(nodes, nodes[1:])) / vehicle.speed_kmph + 1
                depart = max(cycle_ts, self.available_at.get(vehicle.vehicle_id, cycle_ts))
                if not vehicle.can_complete_trip(duration) or depart >= window_end:
                    del candidate._trip_qty
                    continue
                selected.append(candidate)
                weight += possible * item_weight
        return selected

    def _create_trip(self, cycle_ts, vehicle, depot_id, lines):
        depart = max(cycle_ts, self.available_at.get(vehicle.vehicle_id, cycle_ts))
        while lines:
            camps = list(dict.fromkeys(line.allocation.camp_id for line in lines))
            nodes = [depot_id] + camps + [depot_id]
            total_km = sum(self._distance(a, b) for a, b in zip(nodes, nodes[1:]))
            hours = total_km / vehicle.speed_kmph + 1
            return_ts = depart + timedelta(hours=hours)
            route = ">".join(nodes)
            elapsed_km = 0.0
            eta_by_camp = {}
            for index, camp_id in enumerate(camps):
                elapsed_km += self._distance(nodes[index], nodes[index + 1])
                eta_by_camp[camp_id] = depart + timedelta(hours=1 + elapsed_km / vehicle.speed_kmph)
            if self.inventory is None:
                break
            expired = [line for line in lines
                       if (batch := self.inventory.batches.get(line.allocation.batch_id)) is not None
                       and batch.expiry_date <= eta_by_camp[line.allocation.camp_id]]
            if not expired:
                break
            for line in expired:
                self.refusals.append({"cycle_ts": cycle_ts, "allocation_line": self._line_id(line.allocation),
                    "vehicle_id": vehicle.vehicle_id, "reason": "BATCH_EXPIRES_BEFORE_ARRIVAL"})
                del line._trip_qty
            lines = [line for line in lines if line not in expired]
        if not lines:
            return
        vehicle.record_duty(hours)
        if vehicle.vehicle_type == VehicleType.HELICOPTER:
            vehicle.record_sortie()
        self.available_at[vehicle.vehicle_id] = return_ts
        self.trip_counts[vehicle.vehicle_id] += 1
        trip_id = f"{vehicle.vehicle_id}-T{self.trip_counts[vehicle.vehicle_id]}"
        for line in lines:
            a = line.allocation
            self.manifests.append({"trip_id": trip_id, "vehicle_id": vehicle.vehicle_id,
                "depot_id": depot_id, "depart_ts": depart, "return_ts": return_ts,
                "trip_hours": hours, "route": route, "camp_id": a.camp_id,
                "item_id": a.item_id, "batch_id": a.batch_id, "qty": line._trip_qty,
                "eta_ts": eta_by_camp[a.camp_id], "escalated": self._escalated(a, depart)})
            self.outstanding.setdefault((trip_id, a.camp_id, a.item_id, a.batch_id), []).append(
                (self.manifests[-1], a.cycle_ts, a.item_id))
            line.remaining -= line._trip_qty
            del line._trip_qty

    def mark_delivered(self, trip_id, camp_id, item_id, batch_id):
        self.outstanding.pop((trip_id, camp_id, item_id, batch_id), None)

from dataclasses import dataclass
from enum import Enum
import math

class VehicleType(Enum):
    TRUCK = "TRUCK"
    BOAT = "BOAT"
    HELICOPTER = "HELICOPTER"

@dataclass
class Vehicle:
    vehicle_id: str
    depot_id: str
    vehicle_type: VehicleType
    capacity_kg: float
    speed_kmph: float
    driver_name: str = ""
    duty_hours_today: float = 0.0
    sorties_today: int = 0
    discrepancy_count: int = 0

    MAX_DUTY_HOURS = 12.0
    MAX_HELICOPTER_SORTIES = 4
    MAX_DISCREPANCIES = 3

    def __post_init__(self):
        if not self.vehicle_id.strip() or not self.depot_id.strip():
            raise ValueError("Vehicle and depot IDs cannot be empty.")
        if not isinstance(self.vehicle_type, VehicleType):
            raise ValueError("Invalid vehicle type.")
        if not math.isfinite(self.capacity_kg) or self.capacity_kg <= 0:
            raise ValueError("Vehicle capacity must be positive and finite.")
        if not math.isfinite(self.speed_kmph) or self.speed_kmph <= 0:
            raise ValueError("Vehicle speed must be positive and finite.")
        expected = {VehicleType.TRUCK: (5000, 30), VehicleType.BOAT: (1000, 20), VehicleType.HELICOPTER: (2000, 120)}
        cap, speed = expected[self.vehicle_type]
        if self.capacity_kg != cap or self.speed_kmph != speed:
            raise ValueError(f"{self.vehicle_type.value} must have capacity {cap} kg and speed {speed} km/h.")
        if not math.isfinite(self.duty_hours_today) or not 0 <= self.duty_hours_today <= 12:
            raise ValueError("Driver duty hours must be between 0 and 12.")
        if not isinstance(self.sorties_today, int) or isinstance(self.sorties_today, bool) or not 0 <= self.sorties_today <= 4:
            raise ValueError("Sorties must be a whole number between 0 and 4.")
        if not isinstance(self.discrepancy_count, int) or isinstance(self.discrepancy_count, bool) or self.discrepancy_count < 0:
            raise ValueError("Discrepancy count must be a non-negative integer.")

    @property
    def capacity_tonnes(self):
        return self.capacity_kg / 1000

    @property
    def is_grounded(self):
        return self.discrepancy_count >= self.MAX_DISCREPANCIES

    @property
    def remaining_duty_hours(self):
        return self.MAX_DUTY_HOURS - self.duty_hours_today

    @property
    def has_sorties_available(self):
        return self.vehicle_type == VehicleType.HELICOPTER and self.sorties_today < self.MAX_HELICOPTER_SORTIES

    def can_complete_trip(self, trip_hours):
        return math.isfinite(trip_hours) and trip_hours >= 0 and not self.is_grounded and self.duty_hours_today + trip_hours <= 12

    def record_duty(self, trip_hours):
        if not self.can_complete_trip(trip_hours):
            raise ValueError("Vehicle cannot complete this trip.")
        self.duty_hours_today += trip_hours

    def record_sortie(self):
        if self.vehicle_type != VehicleType.HELICOPTER or not self.has_sorties_available:
            raise ValueError("Helicopter sortie limit reached or vehicle is not a helicopter.")
        self.sorties_today += 1

    def record_discrepancy(self):
        self.discrepancy_count += 1

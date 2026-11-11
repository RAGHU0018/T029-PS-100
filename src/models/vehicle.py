
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
    capacity_tonnes: float
    speed_kmph: float | None
    duty_hours_today: float = 0.0
    sorties_today: int = 0
    discrepancy_count: int = 0

    MAX_DUTY_HOURS = 12.0
    MAX_HELICOPTER_SORTIES = 4
    MAX_DISCREPANCIES = 3

    def __post_init__(self):
        if not self.vehicle_id.strip():
            raise ValueError("Vehicle ID cannot be empty.")

        if not self.depot_id.strip():
            raise ValueError("Depot ID cannot be empty.")

        if not isinstance(self.vehicle_type, VehicleType):
            raise ValueError("Invalid vehicle type.")

        if not math.isfinite(self.capacity_tonnes) or self.capacity_tonnes <= 0:
            raise ValueError("Vehicle capacity must be positive and finite.")

        if not math.isfinite(self.duty_hours_today):
            raise ValueError("Duty hours must be finite.")

        if not 0 <= self.duty_hours_today <= self.MAX_DUTY_HOURS:
            raise ValueError("Driver duty hours must be between 0 and 12.")

        if not isinstance(self.sorties_today, int) or isinstance(self.sorties_today, bool):
            raise ValueError("Sorties must be a whole number.")

        if not 0 <= self.sorties_today <= self.MAX_HELICOPTER_SORTIES:
            raise ValueError("Sorties must be between 0 and 4.")

        if not isinstance(self.discrepancy_count, int) or isinstance(self.discrepancy_count, bool):
            raise ValueError("Discrepancy count must be a whole number.")

        if self.discrepancy_count < 0:
            raise ValueError("Discrepancy count cannot be negative.")

        specifications = {
            VehicleType.TRUCK: (5.0, 30.0),
            VehicleType.BOAT: (1.0, 20.0),
            VehicleType.HELICOPTER: (2.0, None)
        }

        expected_capacity, expected_speed = specifications[self.vehicle_type]

        if self.capacity_tonnes != expected_capacity:
            raise ValueError(
                f"{self.vehicle_type.value} capacity must be "
                f"{expected_capacity} tonnes."
            )

        if self.speed_kmph != expected_speed:
            raise ValueError(
                f"Invalid speed for {self.vehicle_type.value}."
            )

    @property
    def is_grounded(self) -> bool:
        return self.discrepancy_count >= self.MAX_DISCREPANCIES

    @property
    def remaining_duty_hours(self) -> float:
        return self.MAX_DUTY_HOURS - self.duty_hours_today

    @property
    def has_sorties_available(self) -> bool:
        if self.vehicle_type != VehicleType.HELICOPTER:
            return False

        return self.sorties_today < self.MAX_HELICOPTER_SORTIES

    def can_complete_trip(self, trip_hours: float) -> bool:
        if not math.isfinite(trip_hours) or trip_hours < 0:
            return False

        return (
            not self.is_grounded
            and self.duty_hours_today + trip_hours <= self.MAX_DUTY_HOURS
        )

    def record_duty(self, trip_hours: float) -> None:
        if not self.can_complete_trip(trip_hours):
            raise ValueError("Vehicle cannot complete this trip.")

        self.duty_hours_today += trip_hours

    def record_sortie(self) -> None:
        if self.vehicle_type != VehicleType.HELICOPTER:
            raise ValueError("Only helicopters can record sorties.")

        if not self.has_sorties_available:
            raise ValueError("Daily helicopter sortie limit reached.")

        self.sorties_today += 1

    def record_discrepancy(self) -> None:
        self.discrepancy_count += 1

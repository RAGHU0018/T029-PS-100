
from dataclasses import dataclass, field
from enum import Enum


class RoadStatus(Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


@dataclass
class Zone:
    zone_id: str
    population: int
    severity_level: int
    road_status: RoadStatus
    depot_distances: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if not self.zone_id.strip():
            raise ValueError("Zone ID cannot be empty.")

        if self.population < 0:
            raise ValueError("Population cannot be negative.")

        if not 1 <= self.severity_level <= 5:
            raise ValueError("Severity level must be between 1 and 5.")

        if not isinstance(self.road_status, RoadStatus):
            raise ValueError("Invalid road status.")

        for depot_id, distance in self.depot_distances.items():
            if not depot_id.strip():
                raise ValueError("Depot ID cannot be empty.")

            if distance < 0:
                raise ValueError("Depot distance cannot be negative.")

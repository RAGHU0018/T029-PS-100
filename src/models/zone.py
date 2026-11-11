from dataclasses import dataclass, field
from enum import Enum

class RoadStatus(Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"

@dataclass
class Zone:
    zone_id: str
    population: int = 0
    severity_level: int = 1
    road_status: RoadStatus = RoadStatus.OPEN
    depot_distances: dict[str, float] = field(default_factory=dict)
    zone_name: str = ""
    serving_depot_id: str = ""

    def __post_init__(self):
        if not isinstance(self.zone_id, str) or not self.zone_id.strip():
            raise ValueError("Zone ID cannot be empty.")
        if not isinstance(self.population, int) or isinstance(self.population, bool) or self.population < 0:
            raise ValueError("Population must be a non-negative integer.")
        if not isinstance(self.severity_level, int) or not 1 <= self.severity_level <= 5:
            raise ValueError("Severity level must be between 1 and 5.")
        if not isinstance(self.road_status, RoadStatus):
            raise ValueError("Invalid road status.")
        if not isinstance(self.zone_name, str) or not isinstance(self.serving_depot_id, str):
            raise ValueError("Zone name and serving depot ID must be strings.")
        for depot_id, distance in self.depot_distances.items():
            if not depot_id.strip() or distance < 0:
                raise ValueError("Depot IDs must be non-empty and distances non-negative.")

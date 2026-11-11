
from dataclasses import dataclass


@dataclass
class Camp:
    camp_id: str
    zone_id: str
    capacity: int
    occupancy: int
    vulnerable_count: int

    def __post_init__(self):
        if not self.camp_id.strip():
            raise ValueError("Camp ID cannot be empty.")

        if not self.zone_id.strip():
            raise ValueError("Zone ID cannot be empty.")

        if self.capacity <= 0:
            raise ValueError("Camp capacity must be greater than zero.")

        if self.occupancy < 0:
            raise ValueError("Occupancy cannot be negative.")

        if self.vulnerable_count < 0:
            raise ValueError("Vulnerable count cannot be negative.")

        if self.vulnerable_count > self.occupancy:
            raise ValueError(
                "Vulnerable count cannot exceed occupancy."
            )

    @property
    def occupancy_percentage(self) -> float:
        return (self.occupancy / self.capacity) * 100

    @property
    def is_overflow(self) -> bool:
        return self.occupancy_percentage > 120

    @property
    def requires_redirection(self) -> bool:
        return self.occupancy_percentage > 150

    @property
    def excess_occupancy(self) -> int:
        if self.is_overflow:
            return self.occupancy - self.capacity

        return 0

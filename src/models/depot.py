
from dataclasses import dataclass, field


@dataclass
class Depot:
    depot_id: str
    name: str
    location: str
    stock_batch_ids: list[str] = field(default_factory=list)
    vehicle_ids: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.depot_id.strip():
            raise ValueError("Depot ID cannot be empty.")

        if not self.name.strip():
            raise ValueError("Depot name cannot be empty.")

        if not self.location.strip():
            raise ValueError("Depot location cannot be empty.")

        if len(self.stock_batch_ids) != len(set(self.stock_batch_ids)):
            raise ValueError("Duplicate stock batch IDs are not allowed.")

        if len(self.vehicle_ids) != len(set(self.vehicle_ids)):
            raise ValueError("Duplicate vehicle IDs are not allowed.")

        if any(not batch_id.strip() for batch_id in self.stock_batch_ids):
            raise ValueError("Stock batch IDs cannot be empty.")

        if any(not vehicle_id.strip() for vehicle_id in self.vehicle_ids):
            raise ValueError("Vehicle IDs cannot be empty.")

    def add_stock_batch(self, batch_id: str) -> None:
        if not batch_id.strip():
            raise ValueError("Batch ID cannot be empty.")

        if batch_id in self.stock_batch_ids:
            raise ValueError("Stock batch already registered.")

        self.stock_batch_ids.append(batch_id)

    def add_vehicle(self, vehicle_id: str) -> None:
        if not vehicle_id.strip():
            raise ValueError("Vehicle ID cannot be empty.")

        if vehicle_id in self.vehicle_ids:
            raise ValueError("Vehicle already registered.")

        self.vehicle_ids.append(vehicle_id)

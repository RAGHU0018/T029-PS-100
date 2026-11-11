from dataclasses import dataclass, field

@dataclass
class Depot:
    depot_id: str
    name: str
    location: str = ""
    stock_batch_ids: list[str] = field(default_factory=list)
    vehicle_ids: list[str] = field(default_factory=list)
    depot_name: str = ""

    def __post_init__(self):
        if not self.depot_id.strip():
            raise ValueError("Depot ID cannot be empty.")
        if not self.name.strip() and not self.depot_name.strip():
            raise ValueError("Depot name cannot be empty.")
        if not self.name:
            self.name = self.depot_name
        if not self.depot_name:
            self.depot_name = self.name
        if not isinstance(self.location, str):
            raise ValueError("Depot location must be a string.")
        if len(self.stock_batch_ids) != len(set(self.stock_batch_ids)):
            raise ValueError("Duplicate stock batch IDs are not allowed.")
        if len(self.vehicle_ids) != len(set(self.vehicle_ids)):
            raise ValueError("Duplicate vehicle IDs are not allowed.")
        if any(not x.strip() for x in self.stock_batch_ids + self.vehicle_ids):
            raise ValueError("Registered IDs cannot be empty.")

    def add_stock_batch(self, batch_id: str) -> None:
        if not batch_id.strip() or batch_id in self.stock_batch_ids:
            raise ValueError("Invalid or duplicate stock batch ID.")
        self.stock_batch_ids.append(batch_id)

    def add_vehicle(self, vehicle_id: str) -> None:
        if not vehicle_id.strip() or vehicle_id in self.vehicle_ids:
            raise ValueError("Invalid or duplicate vehicle ID.")
        self.vehicle_ids.append(vehicle_id)

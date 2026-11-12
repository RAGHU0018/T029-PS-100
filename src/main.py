"""PS-100 application entry point: python -m src.main."""
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.engines.allocation_engine import AllocationEngine
from src.engines.cycle_engine import CycleEngine
from src.engines.dispatch_engine import DispatchEngine
from src.engines.priority_engine import PriorityEngine
from src.engines.reconciliation_engine import ReconciliationEngine
from src.engines.reporting_engine import ReportingEngine
from src.models.camp import Camp
from src.models.depot import Depot
from src.models.item import Item, ItemClass
from src.models.vehicle import Vehicle, VehicleType
from src.models.zone import RoadStatus, Zone
from src.services.command_processor import CommandProcessor, CommandProcessorError
from src.services.data_loader import CSVDataLoader
from src.services.delivery_processor import DeliveryProcessor
from src.services.inventory_manager import InventoryManager
from src.services.overflow_manager import OverflowManager
from src.services.request_manager import RequestManager


IST = ZoneInfo("Asia/Kolkata")


def parse_ts(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)


def run_application(input_dir="data/input", output_dir="data/output"):
    loader = CSVDataLoader(input_dir)
    data = loader.load_all()
    depots = {r["depot_id"]: Depot(r["depot_id"], r["depot_name"]) for r in data["depots"]}
    zones = {r["zone_id"]: Zone(r["zone_id"], severity_level=int(r["severity"]),
        road_status=RoadStatus(r["road_status"]), zone_name=r["zone_name"],
        serving_depot_id=r["serving_depot_id"]) for r in data["zones"]}
    camps = {r["camp_id"]: Camp(r["camp_id"], r["zone_id"], int(r["capacity"]),
        int(r["occupancy"]), camp_name=r["camp_name"], children=int(r["children"]),
        elderly=int(r["elderly"]), pregnant=int(r["pregnant"]), opened_ts=parse_ts(r["opened_ts"]))
        for r in data["camps"]}
    items = {r["item_id"]: Item(r["item_id"], r["item_name"], r["unit"],
        float(r["daily_norm_per_person"]), int(r["shelf_life_days"]),
        ItemClass(r["priority_class"]), r["medicine"].lower() == "true",
        float(r["unit_weight_kg"])) for r in data["items"]}
    vehicles = {r["vehicle_id"]: Vehicle(r["vehicle_id"], r["depot_id"],
        VehicleType(r["vehicle_type"]), float(r["capacity_kg"]), float(r["speed_kmph"]),
        r["driver_name"], float(r["duty_hours_used"])) for r in data["vehicles"]}
    distances = {}
    for row in data["distances"]:
        distances[(row["from_id"], row["to_id"])] = float(row["km"])

    inventory = InventoryManager()
    for item in items.values():
        inventory.register_item(item)
    inventory.load_opening_batches(data["stock_batches"])
    requests = RequestManager(camps, items)
    reconciliation = ReconciliationEngine(inventory, vehicles)
    priority = PriorityEngine(camps, zones, reconciliation.last_deliveries)
    dispatch = DispatchEngine(vehicles, camps, zones, items, distances, inventory_manager=inventory)
    allocation = AllocationEngine(inventory, requests, priority, camps, zones, items,
                                  reachability_check=dispatch.can_deliver_before_expiry)
    cycle = CycleEngine(inventory, allocation, dispatch, reconciliation)
    overflow = OverflowManager(camps, items, requests, distances)
    delivery = DeliveryProcessor(data["deliveries"], dispatch, reconciliation)
    processor = CommandProcessor(request_rows=data["requests"], camps=camps, items=items,
        inventory_manager=inventory, receipt_rows=data["stock_receipts"], zones=zones,
        request_manager=requests, overflow_manager=overflow, cycle_engine=cycle,
        delivery_processor=delivery)

    errors = []
    for index, raw in enumerate(loader.load_commands(), start=1):
        try:
            processor.execute_command(raw)
        except (CommandProcessorError, ValueError, KeyError) as exc:
            parts = raw.split("|")
            if len(parts) == 2 and parts[0] == "REQUEST" and parts[1] in requests.rejected:
                continue
            errors.append({"command_index": index, "command": raw, "error": str(exc)})

    output_files = ReportingEngine().write(output_dir, allocation, dispatch, reconciliation, requests)
    return {"output_files": output_files, "command_errors": errors, "cycles": cycle.cycles,
            "processor": processor, "components": {"inventory": inventory, "requests": requests,
            "priority": priority, "allocation": allocation, "dispatch": dispatch,
            "reconciliation": reconciliation, "delivery": delivery}}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the PS-100 relief allocation engine")
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--output-dir", default="data/output")
    args = parser.parse_args(argv)
    result = run_application(args.input_dir, args.output_dir)
    print(f"Completed {len(result['cycles'])} cycles; wrote {len(result['output_files'])} reports.")
    for error in result["command_errors"]:
        print(f"Command {error['command_index']} ({error['command']}): {error['error']}")
    return 1 if result["command_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

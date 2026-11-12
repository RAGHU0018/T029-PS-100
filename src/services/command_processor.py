
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from src.services.inventory_manager import InventoryManager, InventoryError
from src.models.request import Request, Urgency
from src.models.zone import RoadStatus


class CommandProcessorError(Exception):
    """Raised when a command is invalid or cannot be processed."""


@dataclass
class ParsedCommand:
    command_type: str
    arguments: list[str]
    line_number: int | None = None


class CommandProcessor:
    """Parses and validates PS-100 input commands."""

    REQUIRED_ARGUMENTS = {
        "REQUEST": 1,
        "RECEIVE": 1,
        "VERIFY": 2,
        "ARRIVAL": 3,
        "ROAD_STATUS": 3,
        "CYCLE": 1,
        "DELIVERY": 1,
        "PRINT_ALLOCATIONS": 0,
        "PRINT_MANIFESTS": 0,
        "PRINT_RECONCILIATION": 0,
    }

    def __init__(
        self,
        request_rows=None,
        camps=None,
        items=None,
        inventory_manager=None,
        receipt_rows=None,
        zones=None
    ):
        if isinstance(request_rows, dict):
            self.request_rows = request_rows.copy()
        else:
            self.request_rows = {
                row["request_id"]: row
                for row in (request_rows or [])
            }

        if isinstance(receipt_rows, dict):
            self.receipt_rows = receipt_rows.copy()
        else:
            self.receipt_rows = {
                row["receipt_id"]: row
                for row in (receipt_rows or [])
            }

        self.camps = camps or {}
        self.items = items or {}
        self.zones = zones or {}
        self.inventory_manager = inventory_manager

        self.request_history = []
        self.active_requests = {}
        self.processed_request_ids = set()

        self.arrival_history = []
        self.road_status_history = []

    def parse_command(
        self,
        raw_command: str,
        line_number: int | None = None
    ) -> ParsedCommand:
        """Parse one command and validate its argument count."""

        if not isinstance(raw_command, str) or not raw_command.strip():
            raise CommandProcessorError("Command cannot be empty.")

        parts = [part.strip() for part in raw_command.split("|")]

        command_type = parts[0].upper()
        arguments = parts[1:]

        if command_type not in self.REQUIRED_ARGUMENTS:
            raise CommandProcessorError(
                f"Unknown command: {command_type}"
            )

        expected = self.REQUIRED_ARGUMENTS[command_type]
        received = len(arguments)

        if received != expected:
            raise CommandProcessorError(
                f"{command_type} expects {expected} argument(s), "
                f"but received {received}."
            )

        if any(argument == "" for argument in arguments):
            raise CommandProcessorError(
                f"{command_type} contains an empty argument."
            )

        return ParsedCommand(
            command_type=command_type,
            arguments=arguments,
            line_number=line_number
        )

    def parse_commands(
        self,
        commands: list[str]
    ) -> list[ParsedCommand]:
        """Parse commands while preserving their original order."""

        parsed_commands = []

        for line_number, raw_command in enumerate(commands, start=1):
            if not raw_command.strip():
                continue

            if raw_command.strip().startswith("#"):
                continue

            parsed_commands.append(
                self.parse_command(raw_command, line_number)
            )

        return parsed_commands

    @staticmethod
    def _parse_timestamp(value):
        try:
            timestamp = datetime.strptime(
                value, "%Y-%m-%d %H:%M:%S"
            )
        except (ValueError, TypeError) as exc:
            raise CommandProcessorError(
                f"Invalid timestamp: {value}"
            ) from exc

        return timestamp.replace(
            tzinfo=ZoneInfo("Asia/Kolkata")
        )

    def execute_request(self, request_id):
        """Create and register a request from requests.csv."""

        if request_id in self.processed_request_ids:
            raise CommandProcessorError(
                f"Request '{request_id}' was already processed."
            )

        row = self.request_rows.get(request_id)

        if row is None:
            raise CommandProcessorError(
                f"Request '{request_id}' not found in requests.csv."
            )

        camp_id = row["camp_id"]
        item_id = row["item_id"]

        if camp_id not in self.camps:
            raise CommandProcessorError(
                f"Unknown camp: {camp_id}"
            )

        if item_id not in self.items:
            raise CommandProcessorError(
                f"Unknown item: {item_id}"
            )

        try:
            request = Request(
                request_id=request_id,
                camp_id=camp_id,
                item_id=item_id,
                quantity=int(row["qty"]),
                urgency=Urgency(row["urgency"]),
                stock_on_hand=int(row["stock_on_hand"]),
                requested_at=self._parse_timestamp(
                    row["request_ts"]
                )
            )

        except (ValueError, KeyError) as exc:
            raise CommandProcessorError(
                f"Invalid request '{request_id}': {exc}"
            ) from exc

        request_key = (camp_id, item_id)

        self.active_requests[request_key] = request
        self.request_history.append(request)
        self.processed_request_ids.add(request_id)

        return request

    def execute_receive(self, receipt_id):
        """Process a stock receipt using InventoryManager."""

        if self.inventory_manager is None:
            raise CommandProcessorError(
                "Inventory manager is not configured."
            )

        receipt = self.receipt_rows.get(receipt_id)

        if receipt is None:
            raise CommandProcessorError(
                f"Unknown receipt ID: {receipt_id}"
            )

        try:
            return self.inventory_manager.process_receipt(receipt)

        except InventoryError as exc:
            raise CommandProcessorError(str(exc)) from exc

    def execute_verify(self, batch_id, timestamp):
        """Verify a donated medicine batch."""

        if self.inventory_manager is None:
            raise CommandProcessorError(
                "Inventory manager is not configured."
            )

        try:
            self.inventory_manager.verify_batch(
                batch_id,
                timestamp
            )

            return self.inventory_manager.batches[batch_id]

        except InventoryError as exc:
            raise CommandProcessorError(str(exc)) from exc

    def execute_arrival(self, camp_id, timestamp, persons):
        """Register arriving persons at a relief camp."""

        camp = self.camps.get(camp_id)

        if camp is None:
            raise CommandProcessorError(
                f"Unknown camp: {camp_id}"
            )

        try:
            arrival_time = self._parse_timestamp(timestamp)
        except CommandProcessorError:
            raise

        try:
            persons = int(persons)
        except (ValueError, TypeError) as exc:
            raise CommandProcessorError(
                "Arrival persons must be a positive integer."
            ) from exc

        if isinstance(persons, bool) or persons <= 0:
            raise CommandProcessorError(
                "Arrival persons must be a positive integer."
            )

        previous_occupancy = camp.occupancy
        camp.occupancy += persons

        arrival_record = {
            "camp_id": camp_id,
            "timestamp": arrival_time,
            "persons": persons,
            "previous_occupancy": previous_occupancy,
            "new_occupancy": camp.occupancy,
            "is_overflow": camp.is_overflow,
            "requires_redirection": camp.requires_redirection,
        }

        self.arrival_history.append(arrival_record)

        return arrival_record

    def execute_road_status(self, zone_id, timestamp, status):
        """Update the road status of a zone."""

        zone = self.zones.get(zone_id)

        if zone is None:
            raise CommandProcessorError(
                f"Unknown zone: {zone_id}"
            )

        road_time = self._parse_timestamp(timestamp)

        try:
            new_status = RoadStatus(status.upper())
        except (ValueError, AttributeError) as exc:
            raise CommandProcessorError(
                f"Invalid road status: {status}. "
                "Expected OPEN, PARTIAL or BLOCKED."
            ) from exc

        previous_status = zone.road_status
        zone.road_status = new_status

        status_record = {
            "zone_id": zone_id,
            "timestamp": road_time,
            "previous_status": previous_status,
            "new_status": new_status,
        }

        self.road_status_history.append(status_record)

        return status_record

    def execute_command(self, command):
        """Dispatch a parsed command to its execution handler."""

        if isinstance(command, str):
            command = self.parse_command(command)

        if not isinstance(command, ParsedCommand):
            raise CommandProcessorError(
                "Invalid parsed command."
            )

        command_type = command.command_type
        arguments = command.arguments

        if command_type == "REQUEST":
            return self.execute_request(arguments[0])

        elif command_type == "RECEIVE":
            return self.execute_receive(arguments[0])

        elif command_type == "VERIFY":
            return self.execute_verify(
                arguments[0],
                arguments[1]
            )

        elif command_type == "ARRIVAL":
            return self.execute_arrival(
                arguments[0],
                arguments[1],
                arguments[2]
            )

        elif command_type == "ROAD_STATUS":
            return self.execute_road_status(
                arguments[0],
                arguments[1],
                arguments[2]
            )

        else:
            raise CommandProcessorError(
                f"Execution handler for '{command_type}' "
                "has not been implemented yet."
            )

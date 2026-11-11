
import csv
from pathlib import Path


class DataLoaderError(Exception):
    """Raised when an input data file is missing or invalid."""


class CSVDataLoader:
    """Loads and validates the official PS-100 CSV input files."""

    REQUIRED_COLUMNS = {
        "depots.csv": [
            "depot_id", "depot_name"
        ],
        "zones.csv": [
            "zone_id", "zone_name", "severity",
            "road_status", "serving_depot_id"
        ],
        "camps.csv": [
            "camp_id", "zone_id", "camp_name", "capacity",
            "occupancy", "children", "elderly", "pregnant",
            "opened_ts"
        ],
        "distances.csv": [
            "from_id", "to_id", "km"
        ],
        "items.csv": [
            "item_id", "item_name", "unit", "unit_weight_kg",
            "daily_norm_per_person", "shelf_life_days",
            "priority_class", "medicine"
        ],
        "vehicles.csv": [
            "vehicle_id", "depot_id", "vehicle_type",
            "capacity_kg", "speed_kmph", "driver_name",
            "duty_hours_used"
        ],
        "stock_batches.csv": [
            "batch_id", "depot_id", "item_id", "qty",
            "expiry_ts", "source", "verified"
        ],
        "stock_receipts.csv": [
            "receipt_id", "batch_id", "depot_id", "item_id",
            "qty", "expiry_ts", "source", "received_ts"
        ],
        "requests.csv": [
            "request_id", "camp_id", "item_id", "qty",
            "urgency", "stock_on_hand", "request_ts"
        ],
        "deliveries.csv": [
            "delivery_id", "trip_id", "camp_id", "item_id",
            "batch_id", "delivered_qty", "returned_qty",
            "delivered_ts"
        ],
    }

    def __init__(self, input_dir: str | Path):
        self.input_dir = Path(input_dir)

        if not self.input_dir.exists():
            raise DataLoaderError(
                f"Input directory does not exist: {self.input_dir}"
            )

        if not self.input_dir.is_dir():
            raise DataLoaderError(
                f"Input path is not a directory: {self.input_dir}"
            )

    def load_csv(self, filename: str) -> list[dict[str, str]]:
        """Load one CSV file and validate its column names."""

        if filename not in self.REQUIRED_COLUMNS:
            raise DataLoaderError(
                f"Unsupported input file: {filename}"
            )

        file_path = self.input_dir / filename

        if not file_path.is_file():
            raise DataLoaderError(
                f"Required file not found: {filename}"
            )

        try:
            with file_path.open(
                mode="r",
                encoding="utf-8-sig",
                newline=""
            ) as file:
                reader = csv.DictReader(file)

                if reader.fieldnames is None:
                    raise DataLoaderError(
                        f"{filename} is empty or has no header."
                    )

                actual_columns = [
                    column.strip() for column in reader.fieldnames
                ]

                expected_columns = self.REQUIRED_COLUMNS[filename]

                if actual_columns != expected_columns:
                    raise DataLoaderError(
                        f"Invalid columns in {filename}.\n"
                        f"Expected: {expected_columns}\n"
                        f"Received: {actual_columns}"
                    )

                rows = []

                for row_number, row in enumerate(reader, start=2):
                    if None in row:
                        raise DataLoaderError(
                            f"Unexpected extra columns in "
                            f"{filename}, row {row_number}."
                        )

                    cleaned_row = {
                        key: value.strip() if value is not None else ""
                        for key, value in row.items()
                    }

                    if all(value == "" for value in cleaned_row.values()):
                        raise DataLoaderError(
                            f"Blank row found in {filename}, "
                            f"row {row_number}."
                        )

                    rows.append(cleaned_row)

                return rows

        except UnicodeDecodeError as exc:
            raise DataLoaderError(
                f"Unable to decode {filename}: {exc}"
            ) from exc

        except csv.Error as exc:
            raise DataLoaderError(
                f"CSV parsing error in {filename}: {exc}"
            ) from exc

    def load_all(self) -> dict[str, list[dict[str, str]]]:
        """Load all ten official CSV files."""

        data = {}

        for filename in self.REQUIRED_COLUMNS:
            data[filename.removesuffix(".csv")] = self.load_csv(
                filename
            )

        return data

    def load_commands(self) -> list[str]:
        """Load commands while ignoring comments and blank lines."""

        file_path = self.input_dir / "commands.txt"

        if not file_path.is_file():
            raise DataLoaderError("commands.txt not found.")

        commands = []

        with file_path.open(
            mode="r",
            encoding="utf-8-sig"
        ) as file:
            for line_number, line in enumerate(file, start=1):
                command = line.strip()

                if not command or command.startswith("#"):
                    continue

                commands.append(command)

        return commands
